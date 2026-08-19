"""Benchmark helpers: sweeps over N, controller type, and LQR weights (Task 2.2)."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from analysis import summarize, build_table
from config import ControllerParams, SystemParams
from dynamics.state_space import build_lqr_Q
from experiments.runner import run_experiment

METRIC_COLUMNS = [
    "name",
    "N",
    "success",
    "settling_time",
    "rmse_theta",
    "max_theta_deg",
    "max_x",
    "max_u",
    "control_effort",
    "cost",
]


def _lqr_Q(N: int, cparams: ControllerParams) -> np.ndarray:
    return build_lqr_Q(
        N, cparams.q_pos, cparams.q_vel, cparams.q_angle, cparams.q_angle_vel
    )


def _metric_row(name: str, res, cparams: ControllerParams, N: int) -> dict:
    dt = float(np.diff(res.t)[0]) if len(res.t) > 1 else 0.01
    if cparams.type == "lqr":
        Q = _lqr_Q(N, cparams)
    else:
        Q = np.eye(res.states.shape[0])
    R = np.array([[cparams.R]])
    m = summarize(res, dt, Q, R)
    row = {"name": name, "N": N}
    row.update(m)
    return row


def sweep_n(
    params: SystemParams,
    cparams: ControllerParams,
    Ns: Sequence[int],
    theta_deg: float = 5.0,
    seed: int = 42,
) -> list[dict]:
    """Run one controller config over several N values; return metric rows."""
    rows = []
    for N in Ns:
        p = _with_N(params, N)
        res = run_experiment(p, cparams, theta_deg=[theta_deg] + [0.0] * (N - 1), seed=seed)
        rows.append(_metric_row(f"type={cparams.type}", res, cparams, N))
    return rows


def compare_controllers(
    params: SystemParams,
    configs: Sequence[tuple[str, ControllerParams]],
    N: int,
    theta_deg: float = 5.0,
    seed: int = 42,
) -> list[dict]:
    """Run several (name, cparams) configs at the same N; return metric rows."""
    rows = []
    for name, cparams in configs:
        p = _with_N(params, N)
        res = run_experiment(p, cparams, theta_deg=[theta_deg] + [0.0] * (N - 1), seed=seed)
        rows.append(_metric_row(name, res, cparams, N))
    return rows


def sweep_qr(
    params: SystemParams,
    N: int,
    theta_deg: float = 5.0,
    qa_values: Sequence[float] = (1.0, 10.0, 100.0),
    R_values: Sequence[float] = (0.1, 1.0, 10.0),
    seed: int = 42,
) -> list[dict]:
    """Grid sweep over LQR (q_angle, R); return metric rows."""
    rows = []
    for qa in qa_values:
        for R in R_values:
            cp = ControllerParams(type="lqr", q_angle=qa, R=R)
            p = _with_N(params, N)
            res = run_experiment(
                p, cp, theta_deg=[theta_deg] + [0.0] * (N - 1), seed=seed
            )
            row = _metric_row(f"qa={qa:g},R={R:g}", res, cp, N)
            rows.append(row)
    return rows


def _with_N(params: SystemParams, N: int) -> SystemParams:
    import copy

    p = copy.copy(params)
    p.N = N
    return p


def print_table(rows: Sequence[dict]) -> str:
    """Render metric rows as a table (returns the string and prints it)."""
    table = build_table(rows, METRIC_COLUMNS)
    print(table)
    return table