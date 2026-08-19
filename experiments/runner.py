"""Experiment runner: assemble model + controller + simulator (Phase 2, Task 2.2).

Provides the `run_experiment` convenience wrapper used by the benchmark,
robustness and scalability scripts, plus npz save/load helpers for
`SimulationResult`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from config import ControllerParams, SystemParams
from controllers.factory import make_controller
from dynamics.recursive_model import RecursivePendulumChain
from dynamics.linearization import linearize_around_vertical
from simulation.mujoco_model import compile_model
from simulation.simulator import Simulator, SimulationResult


def make_A_B(params: SystemParams) -> tuple[np.ndarray, np.ndarray]:
    """Analytic linearization for the configured cart-chain (A, B)."""
    rm = RecursivePendulumChain(
        cart_mass=params.cart_mass,
        segment_mass=params.segment_mass,
        segment_length=params.segment_length,
        cart_height=params.cart_height,
        segment_radius=params.segment_radius,
    )
    rm.set_N(params.N)
    A, B, _ = linearize_around_vertical(rm)
    return A, B


def run_experiment(
    params: SystemParams,
    cparams: ControllerParams,
    theta_deg: np.ndarray | list[float] | None = None,
    seed: int | None = None,
) -> SimulationResult:
    """Compile the model, build the controller and run one headless trial.

    Args:
        params: system parameters (N, forces, friction, ...).
        cparams: controller parameters (type + tuning).
        theta_deg: initial joint angles in degrees; defaults to `vertical`.
        seed: RNG seed for the simulator's perturbation noise.

    Returns:
        The recorded SimulationResult.
    """
    if theta_deg is None:
        theta_deg = [0.0] * params.N
    model, data = compile_model(params.N, params)
    sim = Simulator(model, data, ctrl_dt=params.ctrl_dt, physics_dt=params.physics_dt)
    if seed is not None:
        sim._rng = np.random.default_rng(seed)

    A = B = None
    if cparams.type in ("lqr", "mpc"):
        A, B = make_A_B(params)
    controller = make_controller(
        cparams, params.N, u_max=params.cart_max_force, A=A, B=B, dt=params.ctrl_dt
    )
    return sim.run_headless(controller, params, cparams, theta_deg=np.asarray(theta_deg))


def save_result(res: SimulationResult, path: Path | str) -> Path:
    """Persist a SimulationResult to `path/result.npz`."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    np.savez(
        path / "result.npz",
        t=res.t,
        x=res.x,
        xdot=res.xdot,
        theta=res.theta,
        thetadot=res.thetadot,
        u=res.u,
        u_applied=res.u_applied,
        states=res.states,
        success=res.success,
    )
    return path / "result.npz"


def load_result(path: Path | str) -> SimulationResult:
    """Load a SimulationResult saved with `save_result`."""
    data = np.load(Path(path))
    return SimulationResult(
        t=data["t"],
        x=data["x"],
        xdot=data["xdot"],
        theta=data["theta"],
        thetadot=data["thetadot"],
        u=data["u"],
        u_applied=data["u_applied"],
        states=data["states"],
        success=bool(data["success"]),
    )