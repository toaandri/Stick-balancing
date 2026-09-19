"""Robustness sweeps: initial angle, friction, noise, and command delay (Task 2.3).

Each sweep varies one disturbance channel while holding the rest at the
configured defaults and reports the standard metric rows (plus the swept
parameter) so results can be tabulated with `benchmark.print_table`.
"""

from __future__ import annotations

from collections.abc import Sequence

import copy

import numpy as np

from analysis import summarize
from config import ControllerParams, SystemParams
from dynamics.state_space import build_lqr_Q
from experiments.runner import run_experiment


def _row(sweep_key: str, sweep_value, res, cparams: ControllerParams, N: int) -> dict:
    dt = float(res.t[1] - res.t[0]) if len(res.t) > 1 else 0.01
    from controllers.lqr import LQRController
    Q = LQRController._build_q(cparams, N)
    m = summarize(res, dt, Q, np.array([[cparams.R]]))
    row = {sweep_key: sweep_value, "N": N}
    row.update(m)
    return row


def sweep_initial_angle(
    params: SystemParams,
    cparams: ControllerParams,
    angles_deg: Sequence[float],
    N: int,
    seed: int = 42,
) -> list[dict]:
    """Stabilization success vs initial angle of the first segment."""
    rows = []
    for ang in angles_deg:
        p = copy.copy(params)
        p.N = N
        res = run_experiment(p, cparams, theta_deg=[ang] + [0.0] * (N - 1), seed=seed)
        rows.append(_row("theta_deg", ang, res, cparams, N))
    return rows


def sweep_friction(
    params: SystemParams,
    cparams: ControllerParams,
    friction_values: Sequence[float],
    N: int,
    theta_deg: float = 5.0,
    seed: int = 42,
) -> list[dict]:
    """Stabilization success vs joint friction loss coefficient."""
    rows = []
    for mu in friction_values:
        p = copy.copy(params)
        p.N = N
        p.joint_frictionloss = mu
        res = run_experiment(p, cparams, theta_deg=[theta_deg] + [0.0] * (N - 1), seed=seed)
        rows.append(_row("friction", mu, res, cparams, N))
    return rows


def sweep_noise(
    params: SystemParams,
    cparams: ControllerParams,
    noise_values: Sequence[float],
    N: int,
    theta_deg: float = 5.0,
    seeds: Sequence[int] = (0, 1, 2),
) -> list[dict]:
    """Stabilization success vs measurement noise, averaged over seeds."""
    if not len(seeds):
        raise ValueError('at least one seed is required')
    rows = []
    for sigma in noise_values:
        p = copy.copy(params)
        p.N = N
        p.noise_sigma = sigma
        acc = {"success": 0}
        for seed in seeds:
            res = run_experiment(
                p, cparams, theta_deg=[theta_deg] + [0.0] * (N - 1), seed=seed
            )
            dt = float(res.t[1] - res.t[0]) if len(res.t) > 1 else 0.01
            acc["success"] += int(
                summarize(res, dt, np.eye(res.states.shape[0]), np.array([[cparams.R]]))["success"]
            )
        acc["success"] /= len(seeds)
        acc["noise_sigma"] = sigma
        acc["N"] = N
        rows.append(acc)
    return rows


def sweep_delay(
    params: SystemParams,
    cparams: ControllerParams,
    delay_values: Sequence[int],
    N: int,
    theta_deg: float = 5.0,
    seed: int = 42,
) -> list[dict]:
    """Stabilization success vs command delay (in control steps)."""
    rows = []
    for delay in delay_values:
        p = copy.copy(params)
        p.N = N
        p.command_delay_steps = delay
        res = run_experiment(p, cparams, theta_deg=[theta_deg] + [0.0] * (N - 1), seed=seed)
        rows.append(_row("delay_steps", delay, res, cparams, N))
    return rows


def sweep_parameter(params, cparams, parameter, values, theta_deg=2.0, seed=42):
    """Change the plant while keeping the nominal controller design fixed."""
    from dataclasses import replace
    if parameter not in ('cart_mass', 'segment_mass', 'segment_length', 'joint_damping', 'cart_max_force'):
        raise ValueError('unsupported robustness parameter')
    rows = []
    for value in values:
        plant = replace(params, **{parameter: value})
        res = run_experiment(plant, cparams, theta_deg=[theta_deg] + [0.0] * (plant.N-1), seed=seed, design_params=params)
        rows.append(_row(parameter, value, res, cparams, plant.N))
    return rows
