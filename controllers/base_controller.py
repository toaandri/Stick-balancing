"""Abstract controller interface and saturation helper."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class BaseController(ABC):
    """Base class for all controllers.

    Controllers are decoupled from the simulator: they receive a state vector in
    the ordering X = [x, xdot, th1, th1dot, ..., thN, thNdot] and return a scalar
    control force u applied to the cart.
    """

    def __init__(self, u_max: float = 100.0) -> None:
        self.u_max = float(u_max)

    @abstractmethod
    def compute(self, state: np.ndarray, t: float) -> float:
        """Compute the control force at time t given the measured state."""

    def reset(self) -> None:
        """Reset internal controller state (integrators, buffers)."""

    def saturate(self, u: float) -> float:
        """Clamp u to [-u_max, u_max]."""
        return float(np.clip(u, -self.u_max, self.u_max))