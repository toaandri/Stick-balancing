"""Scalability study: per-N compile/step cost and stabilization behavior (Task 2.3).

Reports wall-clock time for the full closed-loop run at each N so the report
can show how the computational cost grows with the number of segments.
"""

from __future__ import annotations

import copy
import time
from collections.abc import Sequence

from config import ControllerParams, SystemParams
from experiments.runner import run_experiment


def step_time_ms(params: SystemParams, cparams: ControllerParams, N: int, n_steps: int = 100) -> float:
    """Time a short run and return the average physics+control time per step (ms)."""
    p = copy.copy(params)
    p.N = N
    p.sim_time = n_steps * p.ctrl_dt
    start = time.perf_counter()
    run_experiment(p, cparams, theta_deg=[0.1] * N)
    elapsed = time.perf_counter() - start
    return 1000.0 * elapsed / max(1, int(p.sim_time / p.ctrl_dt))


def scalability_rows(
    params: SystemParams,
    cparams: ControllerParams,
    Ns: Sequence[int],
    theta_deg: float = 5.0,
    seed: int = 42,
) -> list[dict]:
    """Run the configured controller at each N and return timing + success rows."""
    rows = []
    for N in Ns:
        p = copy.copy(params)
        p.N = N
        start = time.perf_counter()
        res = run_experiment(p, cparams, theta_deg=[theta_deg] + [0.0] * (N - 1), seed=seed)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        from analysis import success

        n_steps = max(1, int(p.sim_time / p.ctrl_dt))
        rows.append(
            {
                "name": cparams.type,
                "N": N,
                "run_ms": round(elapsed_ms, 3),
                "step_ms": round(elapsed_ms / n_steps, 4),
                "success": success(res.theta, res.x),
                "max_theta_deg": round(float(abs(res.theta).max() * 180.0 / 3.141592653589793), 3),
            }
        )
    return rows