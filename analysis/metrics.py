"""Quantitative metrics over simulation results (Phase 2, Task 2.1).

All functions operate on plain arrays (or a `SimulationResult`) so they are
easy to unit-test with known data and reusable outside the simulator.
Angles are in radians, time in seconds, force in Newtons.
"""

from __future__ import annotations

import numpy as np

from simulation.simulator import SimulationResult


def rmse(x: np.ndarray) -> float:
    """Root-mean-square error of a signal."""
    x = np.asarray(x, dtype=float)
    return float(np.sqrt(np.mean(np.square(x))))


def mae(x: np.ndarray) -> float:
    """Mean absolute error of a signal."""
    x = np.asarray(x, dtype=float)
    return float(np.mean(np.abs(x)))


def max_abs(x: np.ndarray) -> float:
    """Maximum absolute value of a signal."""
    x = np.asarray(x, dtype=float)
    return float(np.max(np.abs(x)))


def weighted_mean_angle(theta: np.ndarray) -> np.ndarray:
    """Weighted mean angle across segments (radians), shape (n_steps,).

    Weights are uniform across segments so the mean is comparable for any N.
    """
    theta = np.asarray(theta, dtype=float)
    return np.mean(theta, axis=0)


def settling_time(
    theta: np.ndarray,
    t: np.ndarray,
    threshold_deg: float = 1.0,
    tol_deg: float = 0.1,
) -> float | None:
    """First time (s) after which the weighted mean angle stays within a band.

    The angle is considered settled once, for all remaining samples, it stays
    inside `threshold_deg` (with a small tolerance for numerical noise). Returns
    None if the signal never settles.
    """
    theta = np.asarray(theta, dtype=float)
    t = np.asarray(t, dtype=float)
    ang = np.abs(np.rad2deg(weighted_mean_angle(theta)))
    thresh = threshold_deg + tol_deg
    if len(ang) == 0:
        return None
    # find the first index such that everything after is within the band
    for i in range(len(ang)):
        if np.all(ang[i:] <= thresh):
            return float(t[i])
    return None


def max_abs_cart(x: np.ndarray) -> float:
    """Maximum absolute cart position (m)."""
    return max_abs(x)


def control_effort(u: np.ndarray, dt: float) -> float:
    """Control effort int u^2 dt."""
    u = np.asarray(u, dtype=float)
    return float(np.sum(np.square(u)) * dt)


def control_energy(u: np.ndarray, dt: float) -> float:
    """Control energy int |u| dt (work-like proxy, N s)."""
    u = np.asarray(u, dtype=float)
    return float(np.sum(np.abs(u)) * dt)


def cost_J(
    states: np.ndarray,
    u: np.ndarray,
    Q: np.ndarray,
    R: np.ndarray,
    dt: float,
) -> float:
    """Quadratic cost sum_k (x_k' Q x_k + u_k' R u_k) dt."""
    states = np.asarray(states, dtype=float)
    u = np.asarray(u, dtype=float).reshape(-1, 1)
    Q = np.asarray(Q, dtype=float)
    R = np.asarray(R, dtype=float)
    n = min(states.shape[1], u.shape[0])
    x = states[:, :n]  # (n_state, n_steps)
    uu = u[:n]  # (n_steps, 1)
    state_cost = np.einsum("ik,jk,ij->k", x, x, Q)
    control_cost = np.einsum("ki,kj,ij->k", uu, uu, R)
    return float(np.sum(state_cost + control_cost) * dt)


def success(
    theta: np.ndarray,
    x: np.ndarray,
    angle_tol_deg: float = 1.0,
    max_cart: float = 5.0,
) -> bool:
    """True if the run settled: final mean angle small and cart bounded."""
    final = np.abs(np.rad2deg(weighted_mean_angle(theta[..., -1] if theta.ndim == 2 else theta)))
    return bool(final < angle_tol_deg and max_abs(x) < max_cart)


def summarize(res: SimulationResult, dt: float, Q: np.ndarray, R: np.ndarray) -> dict:
    """Compute the standard metrics dict for a SimulationResult."""
    if dt is None:
        dt = float(np.diff(res.t)[0]) if len(res.t) > 1 else 0.01
    settle = settling_time(res.theta, res.t)
    return {
        "rmse_theta": rmse(weighted_mean_angle(res.theta)),
        "rmse_x": rmse(res.x),
        "max_theta_deg": float(np.max(np.abs(np.rad2deg(res.theta)))),
        "max_x": max_abs_cart(res.x),
        "max_u": max_abs(res.u_applied),
        "settling_time": settle if settle is not None else float("nan"),
        "control_effort": control_effort(res.u_applied, dt),
        "control_energy": control_energy(res.u_applied, dt),
        "cost": cost_J(res.states, res.u_applied, Q, R, dt),
        "success": success(res.theta, res.x),
    }