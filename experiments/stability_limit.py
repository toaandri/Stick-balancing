"""Stability-limit estimation via bisection (Phase 2, Task 2.3).

Finds the largest initial angle (degrees) from which a controller still
stabilizes the chain, using binary search on the stabilization outcome
(success metric). Success is a deterministic function of the initial angle for
a fixed seed, so bisection converges reliably.
"""

from __future__ import annotations

from config import ControllerParams, SystemParams
from experiments.runner import run_experiment


def _stabilizes(params: SystemParams, cparams: ControllerParams, angle_deg: float, seed: int) -> bool:
    from analysis import success

    p = params
    res = run_experiment(p, cparams, theta_deg=[angle_deg] + [0.0] * (p.N - 1), seed=seed)
    return success(res.theta, res.x)


def bisect_angle(
    params: SystemParams,
    cparams: ControllerParams,
    lo: float = 0.1,
    hi: float = 30.0,
    tol: float = 0.05,
    max_iter: int = 25,
    seed: int = 42,
) -> tuple[float, int, float]:
    """Binary-search the critical stabilizing angle.

    Args:
        params, cparams: system and controller configuration (params.N used).
        lo, hi: search interval in degrees (lo must stabilize, hi must fail).
        tol: target accuracy in degrees.
        max_iter: iteration budget.
        seed: RNG seed for reproducibility.

    Returns:
        (critical_deg, iterations, last_angle_tested). `critical_deg` is the
        largest angle at which the run still succeeded.
    """
    if not _stabilizes(params, cparams, lo, seed):
        raise ValueError(f"lo={lo} deg does not stabilize; increase lo")
    if _stabilizes(params, cparams, hi, seed):
        raise ValueError(f"hi={hi} deg still stabilizes; increase hi")

    good, bad = lo, hi
    for it in range(max_iter):
        mid = 0.5 * (good + bad)
        if _stabilizes(params, cparams, mid, seed):
            good = mid
        else:
            bad = mid
        if bad - good <= tol:
            break
    return good, it + 1, mid