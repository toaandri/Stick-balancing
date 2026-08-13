"""Initial conditions and dynamic perturbations for experiments."""

from __future__ import annotations

import numpy as np

from config import SystemParams


def random_angles(N: int, theta_max_deg: float, seed: int | None = None) -> np.ndarray:
    """Uniformly random initial angles within [-theta_max, theta_max] degrees."""
    rng = np.random.default_rng(seed)
    return rng.uniform(-theta_max_deg, theta_max_deg, size=N)


def small_angles(N: int) -> np.ndarray:
    """A deterministic small perturbation, alternating sign per joint (degrees)."""
    return np.array([((-1.0) ** i) * (1.0 + i * 0.5) for i in range(N)])


def vertical_angles(N: int) -> np.ndarray:
    """Perfectly vertical equilibrium: all angles zero."""
    return np.zeros(N)


def initial_angles(params: SystemParams, rng: np.random.Generator | None = None) -> np.ndarray:
    """Resolve the configured initial condition into an angle vector (radians).

    Uses `params.explicit_theta_deg` if given, otherwise the configured mode:
    vertical / small / random (seeded via params.seed if no rng is provided).
    """
    if params.explicit_theta_deg is not None:
        return np.deg2rad(np.asarray(params.explicit_theta_deg, dtype=float))
    mode = params.initial_condition
    if mode == "vertical":
        return np.zeros(params.N)
    if mode == "small":
        return np.deg2rad(small_angles(params.N))
    if mode == "random":
        rng = rng if rng is not None else np.random.default_rng(params.seed)
        return np.deg2rad(rng.uniform(-params.theta_max_deg, params.theta_max_deg, size=params.N))
    raise ValueError(f"unknown initial_condition {mode!r}")