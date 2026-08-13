"""Passive (open-loop) controller: no control action, for reference runs."""

from __future__ import annotations

import numpy as np

from controllers.base_controller import BaseController


class PassiveController(BaseController):
    def compute(self, state: np.ndarray, t: float) -> float:
        return 0.0