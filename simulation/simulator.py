"""Simulator wrapper around MuJoCo.

Owns the MjModel/MjData objects, steps the physics, reads state back in the
controller ordering X = [x, xdot, th1, th1d, ..., thN, thNd], applies control
commands and dynamic perturbations (impulses / torques). Rendering is optional;
the simulator itself is fully headless.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np
import mujoco

from config import ControllerParams, PerturbationSpec, SystemParams
from controllers.base_controller import BaseController
from dynamics.state_space import mujoco_to_state
from simulation import perturbations as pert_mod

logger = logging.getLogger(__name__)


@dataclass
class SimulationResult:
    """All recorded signals from one simulation run."""

    t: np.ndarray
    x: np.ndarray  # cart position (m)
    xdot: np.ndarray
    theta: np.ndarray  # (N, n_steps) radians
    thetadot: np.ndarray
    u: np.ndarray  # commanded force (N)
    u_applied: np.ndarray  # engine-clamped force (N)
    states: np.ndarray  # (n_state, n_steps) in X ordering
    params: dict = field(default_factory=dict)
    success: bool = False

    def __post_init__(self) -> None:
        self.t = np.asarray(self.t)
        self.x = np.asarray(self.x)
        self.xdot = np.asarray(self.xdot)
        self.theta = np.asarray(self.theta)
        self.thetadot = np.asarray(self.thetadot)
        self.u = np.asarray(self.u)
        self.u_applied = np.asarray(self.u_applied)
        self.states = np.asarray(self.states)


class Simulator:
    """Headless MuJoCo simulation loop with control-rate stepping."""

    def __init__(
        self,
        model: mujoco.MjModel,
        data: mujoco.MjData,
        ctrl_dt: float = 0.01,
        physics_dt: Optional[float] = None,
    ) -> None:
        self.model = model
        self.data = data
        self.physics_dt = model.opt.timestep if physics_dt is None else physics_dt
        self.ctrl_dt = ctrl_dt
        self._n_sub = max(1, round(self.ctrl_dt / self.physics_dt))

        self.nq = model.nq
        self.nv = model.nv
        self.N = model.nv - 1
        self.n_state = 2 * self.N + 2
        self._rng = np.random.default_rng(0)

        self._impulse_queue: list[dict] = []
        self._torque_queue: list[dict] = []
        self._noise_sigma = 0.0
        self._delay_buffer: list[np.ndarray] = []
        self._delay_steps = 0

    # ------------------------------------------------------------------ state
    def reset(self, seed: Optional[int] = None) -> None:
        """Reset the physics to the model defaults (vertical, cart at x=0)."""
        mujoco.mj_resetData(self.model, self.data)
        if seed is not None:
            self._rng = np.random.default_rng(seed)

    def set_state(self, qpos: np.ndarray, qvel: Optional[np.ndarray] = None) -> None:
        self.data.qpos[:] = qpos
        if qvel is not None:
            self.data.qvel[:] = qvel
        mujoco.mj_forward(self.model, self.data)

    def get_state(self) -> np.ndarray:
        """Return the state in controller ordering X = [x, xd, th, thd, ...]."""
        return mujoco_to_state(np.array(self.data.qpos), np.array(self.data.qvel))

    def get_measured_state(self) -> np.ndarray:
        """Return state with Gaussian measurement noise added (angles/velocities)."""
        X = self.get_state()
        if self._noise_sigma > 0:
            noise = self._rng.normal(0.0, self._noise_sigma, size=X.shape)
            noise[0:2] = 0.0  # cart position/velocity assumed perfect (noiseless rail encoder)
            X = X + noise
        return X

    # ---------------------------------------------------------- perturbations
    def configure_noise(self, sigma: float) -> None:
        self._noise_sigma = float(sigma)

    def configure_delay(self, steps: int) -> None:
        self._delay_steps = max(0, int(steps))
        self._delay_buffer = [np.zeros(self.n_state) for _ in range(self._delay_steps)]

    def apply_impulse(self, body_name: str, force: np.ndarray, duration: float = 0.05) -> None:
        """Apply a constant force (impulse) on a body for `duration` seconds."""
        body_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, body_name)
        if body_id < 0:
            raise ValueError(f"unknown body {body_name!r}")
        self._impulse_queue.append(
            {"body_id": body_id, "force": np.asarray(force, dtype=float), "remaining": duration}
        )

    def apply_joint_torque(self, joint_name: str, torque: float, duration: float = 0.05) -> None:
        """Apply a constant joint torque for `duration` seconds."""
        joint_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, joint_name)
        if joint_id < 0:
            raise ValueError(f"unknown joint {joint_name!r}")
        self._torque_queue.append(
            {"joint_id": joint_id, "torque": float(torque), "remaining": duration}
        )

    def clear_perturbations(self) -> None:
        self._impulse_queue.clear()
        self._torque_queue.clear()

    def _apply_scheduled(self, dt: float) -> None:
        """Apply queued perturbations for this substep and decrement their timers."""
        self.data.xfrc_applied[:] = 0.0
        self.data.qfrc_applied[:] = 0.0
        remaining: list[dict] = []
        for p in self._impulse_queue:
            self.data.xfrc_applied[p["body_id"], :3] += p["force"]
            p["remaining"] -= dt
            if p["remaining"] > 0:
                remaining.append(p)
        self._impulse_queue = remaining
        remaining = []
        for p in self._torque_queue:
            self.data.qfrc_applied[p["joint_id"]] += p["torque"]
            p["remaining"] -= dt
            if p["remaining"] > 0:
                remaining.append(p)
        self._torque_queue = remaining

    def step(self, ctrl: float = 0.0) -> float:
        """Advance physics by one control period applying `ctrl` (saturated)."""
        return self._physical_step(ctrl)

    # -------------------------------------------------------------- stepping
    def _physical_step(self, ctrl: float) -> float:
        """Step physics `_n_sub` times; return the engine-saturated ctrl."""
        applied = float(np.clip(ctrl, -self.model.actuator_ctrlrange[0, 1],
                                self.model.actuator_ctrlrange[0, 1]))
        self.data.ctrl[0] = applied
        for _ in range(self._n_sub):
            self._apply_scheduled(self.physics_dt)
            mujoco.mj_step(self.model, self.data)
        return applied

    def run_headless(
        self,
        controller: BaseController,
        params: SystemParams,
        cparams: ControllerParams,
        controller_delay_steps: Optional[int] = None,
        perturbations: Optional[list[PerturbationSpec]] = None,
        progress_cb: Optional[Callable[[int, int], None]] = None,
        theta_deg: Optional[np.ndarray] = None,
    ) -> SimulationResult:
        """Run a full closed-loop simulation.

        Args:
            controller: the controller to use.
            params: system parameters (duration, ICs, noise...).
            cparams: controller parameters.
            controller_delay_steps: override for command delay; falls back to params.
            perturbations: dynamic perturbations to schedule.
            progress_cb: optional callback(steps_done, steps_total).
            theta_deg: optional explicit initial angles (degrees); overrides IC logic.

        Returns:
            SimulationResult with recorded signals.
        """
        self.reset(params.seed)
        self.configure_noise(params.noise_sigma)
        delay = (
            params.command_delay_steps
            if controller_delay_steps is None
            else controller_delay_steps
        )
        self.configure_delay(delay)
        self.clear_perturbations()

        # Initial condition
        if theta_deg is not None:
            theta = np.deg2rad(np.asarray(theta_deg, dtype=float))
        else:
            theta = pert_mod.initial_angles(params, self._rng)
        qpos = np.concatenate([[0.0], theta])
        qvel = np.zeros(self.nv)
        self.set_state(qpos, qvel)
        mujoco.mj_forward(self.model, self.data)

        # Dynamic perturbations, sorted by trigger time
        pending = sorted((p for p in (perturbations or [])), key=lambda p: p.time)
        pending = [(p.time, p) for p in pending]
        controller.reset()

        n_steps = int(round(params.sim_time / self.ctrl_dt))
        t = np.zeros(n_steps + 1)
        x = np.zeros(n_steps + 1)
        xd = np.zeros(n_steps + 1)
        theta = np.zeros((self.N, n_steps + 1))
        thd = np.zeros((self.N, n_steps + 1))
        u = np.zeros(n_steps + 1)
        u_applied = np.zeros(n_steps + 1)
        states = np.zeros((self.n_state, n_steps + 1))

        sim_t = 0.0
        for i in range(n_steps + 1):
            measured = self.get_measured_state()
            states[:, i] = measured
            x[i] = measured[0]
            xd[i] = measured[1]
            theta[:, i] = measured[2::2]
            thd[:, i] = measured[3::2]
            t[i] = sim_t

            if i < n_steps:
                while pending and sim_t >= pending[0][0]:
                    _, spec = pending.pop(0)
                    self._trigger(spec)
                u[i] = controller.compute(measured, sim_t)
                u_applied[i] = self._physical_step(u[i])
                sim_t += self.ctrl_dt
            if progress_cb is not None and i % max(1, n_steps // 20) == 0:
                progress_cb(i, n_steps)

        self.data.ctrl[0] = 0.0
        return SimulationResult(
            t=t,
            x=x,
            xdot=xd,
            theta=theta,
            thetadot=thd,
            u=u,
            u_applied=u_applied,
            states=states,
            params={
                "N": self.N,
                "controller": cparams.type,
                "sim_time": params.sim_time,
                "ctrl_dt": self.ctrl_dt,
                "seed": params.seed,
            },
        )

    def _trigger(self, p: PerturbationSpec) -> None:
        """Apply a PerturbationSpec immediately (caller has checked trigger time)."""
        if p.kind == "impulse":
            if p.body != "cart" and not p.body.startswith("segment_"):
                raise ValueError(f"unknown perturbation body {p.body!r}")
            self.apply_impulse(p.body, np.asarray(p.force, dtype=float), p.duration)
        elif p.kind == "torque":
            if p.body.startswith("segment_"):
                joint = f"hinge_{int(p.body.replace('segment_', ''))}"
            else:
                joint = "cart_slide"
            self.apply_joint_torque(joint, p.torque, p.duration)
        else:
            raise ValueError(f"unknown perturbation kind {p.kind!r}")