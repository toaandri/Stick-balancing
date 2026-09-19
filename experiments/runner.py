"""Experiment runner: assemble model + controller + simulator (Phase 2, Task 2.2).

Provides the `run_experiment` convenience wrapper used by the benchmark,
robustness and scalability scripts, plus npz save/load helpers for
`SimulationResult`.
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import replace
import json

import numpy as np

from config import ControllerParams, SystemParams, PerturbationSpec
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
    A, B, info = linearize_around_vertical(rm)
    mass = info['M0'] + np.diag([0.0] + [params.joint_armature] * params.N)
    A[1::2, 0::2] = -np.linalg.solve(mass, info['dG'])
    A[1::2, 1::2] = -np.linalg.solve(mass, np.diag([params.cart_friction] + [params.joint_damping] * params.N))
    B[1::2, 0] = np.linalg.solve(mass, np.eye(params.N + 1)[:, 0])
    return A, B


def run_experiment(
    params: SystemParams,
    cparams: ControllerParams,
    theta_deg: np.ndarray | list[float] | None = None,
    seed: int | None = None,
    perturbations: list[PerturbationSpec] | None = None,
    design_params: SystemParams | None = None,
) -> SimulationResult:
    """Compile the model, build the controller and run one headless trial.

    Args:
        params: system parameters (N, forces, friction, ...).
        cparams: controller parameters (type + tuning).
        theta_deg: initial joint angles in degrees; defaults to the configured IC.
        seed: RNG seed for the simulator's perturbation noise.

    Returns:
        The recorded SimulationResult.
    """
    params = replace(params, seed=params.seed if seed is None else seed)
    params.validate()
    cparams.validate()
    model, data = compile_model(params.N, params)
    sim = Simulator(model, data, ctrl_dt=params.ctrl_dt, physics_dt=params.physics_dt)
    if seed is not None:
        sim._rng = np.random.default_rng(seed)

    A = B = None
    if cparams.type in ("lqr", "mpc"):
        design = design_params or params
        design.validate()
        if design.N != params.N:
            raise ValueError('design and plant must have the same N')
        A, B = make_A_B(design)
    controller = make_controller(
        cparams, params.N, u_max=params.cart_max_force, A=A, B=B, dt=params.ctrl_dt
    )
    result = sim.run_headless(controller, params, cparams, theta_deg=theta_deg, perturbations=perturbations)
    if design_params is not None:
        from dataclasses import asdict
        result.params['design_system'] = asdict(design_params)
    return result


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
        params_json=json.dumps(res.params, allow_nan=False),
    )
    (path / 'params.json').write_text(json.dumps(res.params, indent=2, allow_nan=False), encoding='utf-8')
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
        params=json.loads(str(data['params_json'])) if 'params_json' in data else {},
    )
