"""Controller factory: build the controller selected by ControllerParams.type."""

from __future__ import annotations

import numpy as np

from config import ControllerParams
from controllers.base_controller import BaseController
from controllers.passive import PassiveController
from controllers.pid import PIDController

try:  # LQR added in Phase 1
    from controllers.lqr import LQRController
except ImportError:  # pragma: no cover
    LQRController = None

try:  # MPC is an optional extension
    from controllers.mpc import MPCController
except ImportError:  # pragma: no cover
    MPCController = None


def make_controller(
    cparams: ControllerParams,
    N: int,
    u_max: float = 100.0,
    A: np.ndarray | None = None,
    B: np.ndarray | None = None,
    dt: float = 0.01,
) -> BaseController:
    """Instantiate a controller of the configured type.

    Args:
        cparams: controller parameters.
        N: number of pendulum segments.
        u_max: actuator saturation limit.
        A, B: continuous linearized dynamics (required for lqr / mpc).
        dt: control period (used by mpc).
    """
    ctype = cparams.type
    if ctype == "none":
        return PassiveController(u_max=u_max)
    if ctype == "pid":
        return PIDController(cparams, N, u_max=u_max)
    if ctype == "lqr":
        if LQRController is None:
            raise RuntimeError("LQRController unavailable")
        if A is None or B is None:
            raise ValueError("lqr controller requires A and B matrices")
        return LQRController(cparams, A, B, u_max=u_max)
    if ctype == "mpc":
        if MPCController is None:
            raise RuntimeError("MPCController unavailable")
        if A is None or B is None:
            raise ValueError("mpc controller requires A and B matrices")
        return MPCController(cparams, A, B, dt=dt, u_max=u_max)
    raise ValueError(f"unknown controller type {ctype!r}")