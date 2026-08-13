"""PID controller for the cart + pendulum chain.

The control law is a sum of two PD loops plus an integral on the angle error:

    u = Kp_a * e_a + Kd_a * e_a_dot + Kp_x * x + Kd_x * x_dot + Ki * integral(e_a)

where e_a = sum_i w_i * theta_i is a weighted combination of the joint angles
(default: uniform weights) and x is the cart position. This separates the fast
angle-stabilization gains from the gentle cart-regulating gains, which is much
better conditioned than a single PID on a weighted sum.
"""

from __future__ import annotations

import numpy as np

from config import ControllerParams
from controllers.base_controller import BaseController


class PIDController(BaseController):
    def __init__(
        self,
        cparams: ControllerParams,
        N: int,
        u_max: float = 100.0,
    ) -> None:
        super().__init__(u_max)
        self.kp_angle = float(cparams.kp)
        self.kd_angle = float(cparams.kd)
        self.ki = float(cparams.ki)
        self.kp_cart = float(cparams.kp_cart)
        self.kd_cart = float(cparams.kd_cart)
        if cparams.pid_weights is not None:
            w = np.asarray(cparams.pid_weights, dtype=float)
            if w.shape[0] != N:
                raise ValueError("pid_weights must have one entry per joint")
            self.w = w / w.sum()
        else:
            self.w = np.full(N, 1.0 / N)
        self._integral = 0.0
        self._prev_angle = None
        self._prev_t = None

    def _angle_error(self, state: np.ndarray) -> float:
        N = self.w.shape[0]
        angles = state[2::2][:N]
        return float(np.dot(self.w, angles))

    def compute(self, state: np.ndarray, t: float) -> float:
        e_a = self._angle_error(state)
        x = state[0]
        xd = state[1]
        if self._prev_t is None:
            dt = 0.0
        else:
            dt = max(t - self._prev_t, 1e-6)
        self._integral += e_a * dt
        if self._prev_angle is None:
            e_a_dot = 0.0
        else:
            e_a_dot = (e_a - self._prev_angle) / dt
        u = (
            self.kp_angle * e_a
            + self.kd_angle * e_a_dot
            + self.ki * self._integral
            + self.kp_cart * x
            + self.kd_cart * xd
        )
        self._prev_angle = e_a
        self._prev_t = t
        return self.saturate(u)

    def reset(self) -> None:
        self._integral = 0.0
        self._prev_angle = None
        self._prev_t = None