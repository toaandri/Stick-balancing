"""Realtime rendering of the cart + N-link chain via the MuJoCo passive viewer.

The passive viewer renders asynchronously; this function advances physics
at the configured control rate and synchronizes under the viewer lock. State shared
with the viewer (pause, speed) is guarded by a small thread-safe settings
object.
"""

from __future__ import annotations

import threading
import time

import mujoco
import mujoco.viewer
import numpy as np

from config import ControllerParams, SystemParams
from controllers.factory import make_controller
from simulation.mujoco_model import compile_model


class ViewerSettings:
    """Thread-safe knobs the GUI can flip while the sim loop runs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.paused = False
        self.speed = 1.0
        self.history = []
        self.running = True
        self.step_requested = False
        self.reset_requested = False

    def toggle_pause(self) -> None:
        with self._lock:
            self.paused = not self.paused

    def set_speed(self, speed: float) -> None:
        with self._lock:
            self.speed = max(0.0, speed)

    def request_step(self) -> None:
        with self._lock:
            self.paused = True
            self.step_requested = True

    def request_reset(self) -> None:
        with self._lock:
            self.reset_requested = True

    def stop(self) -> None:
        with self._lock:
            self.running = False


def _make_controller(params: SystemParams, cparams: ControllerParams):
    from experiments.runner import make_A_B
    A = B = None
    if cparams.type in ("lqr", "mpc"):
        A, B = make_A_B(params)
    return make_controller(cparams, params.N, u_max=params.cart_max_force, A=A, B=B, dt=params.ctrl_dt)



def run_realtime(
    params: SystemParams,
    cparams: ControllerParams,
    theta_deg: float = 5.0,
    seed: int = 0,
    settings: ViewerSettings | None = None,
) -> None:
    """Run the passive viewer with a live closed-loop simulation.

    Blocks until the viewer window is closed or the sim thread is stopped.

    Args:
        params, cparams: system and controller configuration.
        theta_deg: initial angle of the first segment (degrees).
        seed: RNG seed.
        settings: optional shared ViewerSettings; a fresh one is created if
            not given (e.g. when driven from the tkinter panel).
    """
    from simulation.simulator import Simulator

    params.validate()
    model, data = compile_model(params.N, params)
    controller = _make_controller(params, cparams)
    simulator = Simulator(model, data, ctrl_dt=params.ctrl_dt)
    simulator.configure_noise(params.noise_sigma)
    simulator.configure_delay(params.command_delay_steps)
    settings = settings or ViewerSettings()

    def reset():
        simulator.reset(seed)
        simulator.set_state(np.r_[0.0, np.deg2rad(theta_deg), np.zeros(params.N - 1)], np.zeros(params.N + 1))
        controller.reset()
        with settings._lock:
            settings.history.clear()

    reset()
    try:
        with mujoco.viewer.launch_passive(model, data) as viewer:
            while viewer.is_running() and settings.running:
                started = time.perf_counter()
                with settings._lock:
                    paused, speed = settings.paused, settings.speed
                    single_step, reset_requested = settings.step_requested, settings.reset_requested
                    settings.step_requested = settings.reset_requested = False
                with viewer.lock():
                    if reset_requested:
                        reset()
                    if (not paused and speed > 0) or single_step:
                        if data.time + params.ctrl_dt <= params.sim_time + 1e-9:
                            controller_step(simulator, controller)
                            with settings._lock:
                                angle = float(np.max(np.abs(np.rad2deg(np.cumsum(data.qpos[1:])))))
                                settings.history.append((float(data.time), angle, float(data.qpos[0]), float(data.ctrl[0])))
                                settings.history = settings.history[-500:]
                        else:
                            with settings._lock:
                                settings.paused = True
                viewer.sync()
                time.sleep(max(0.001, params.ctrl_dt / max(speed, 0.01) - (time.perf_counter() - started)))
    finally:
        settings.stop()


def controller_step(simulator, controller):
    """One real control period; shared state mapping, delay and physics stepping."""
    u = controller.compute(simulator.get_measured_state(), float(simulator.data.time))
    return simulator.step(u)


if __name__ == "__main__":
    from config import load_defaults, load_controller_defaults

    p = load_defaults()
    cp = load_controller_defaults()
    run_realtime(p, cp)