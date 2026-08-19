"""Realtime rendering of the cart + N-link chain via the MuJoCo passive viewer.

`launch_passive` blocks on the main thread, so the simulation is advanced from
a background thread while the viewer keeps the GUI responsive. State shared
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
from dynamics.linearization import linearize_around_vertical
from dynamics.recursive_model import RecursivePendulumChain
from simulation.mujoco_model import compile_model


class ViewerSettings:
    """Thread-safe knobs the GUI can flip while the sim loop runs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.paused = False
        self.speed = 1.0
        self.target_theta_deg = np.zeros(1)
        self.running = True

    def toggle_pause(self) -> None:
        with self._lock:
            self.paused = not self.paused

    def set_speed(self, speed: float) -> None:
        with self._lock:
            self.speed = max(0.0, speed)

    def set_target_angle(self, angle_deg: float) -> None:
        with self._lock:
            self.target_theta_deg[0] = angle_deg

    def stop(self) -> None:
        with self._lock:
            self.running = False


def _make_controller(params: SystemParams, cparams: ControllerParams):
    A = B = None
    if cparams.type in ("lqr", "mpc"):
        rec = RecursivePendulumChain(
            cart_mass=params.cart_mass,
            segment_mass=params.segment_mass,
            segment_length=params.segment_length,
            cart_height=params.cart_height,
            segment_radius=params.segment_radius,
        )
        rec.set_N(params.N)
        A, B, _ = linearize_around_vertical(rec)
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
    model, data = compile_model(params.N, params)
    sim = _make_controller(params, cparams)

    data.qpos[1:] = np.deg2rad(theta_deg)
    data.qvel[:] = 0.0
    mujoco.mj_forward(model, data)

    settings = settings or ViewerSettings()
    if settings.target_theta_deg.size != params.N:
        settings.target_theta_deg = np.zeros(params.N)

    viewer = mujoco.viewer.launch_passive(model, data)

    def sim_loop() -> None:
        target = None
        while settings.running:
            with settings._lock:
                paused = settings.paused
                speed = settings.speed
                target = settings.target_theta_deg.copy()
            if paused:
                time.sleep(0.02)
                continue
            # re-target: nudge the top segment back toward the target angle
            err = target[0] - np.deg2rad(data.qpos[-1])
            if abs(err) > 1e-6:
                data.qpos[-1] += 0.05 * err
            mujoco.mj_forward(model, data)
            state = np.concatenate(
                [data.qpos[:1], data.qvel[:1], data.qpos[1:], data.qvel[1:]]
            )
            u = sim.compute(state, 0.0)
            u = float(np.clip(u, -params.cart_max_force, params.cart_max_force))
            data.ctrl[0] = u
            mujoco.mj_step(model, data)
            viewer.sync()
            time.sleep(0.005 / max(speed, 0.01))

    thread = threading.Thread(target=sim_loop, daemon=True)
    thread.start()
    try:
        while viewer.is_running():
            time.sleep(0.05)
    finally:
        settings.stop()
        viewer.close()
        thread.join(timeout=1.0)


if __name__ == "__main__":
    from config import load_defaults, load_controller_defaults

    p = load_defaults()
    cp = load_controller_defaults()
    run_realtime(p, cp)