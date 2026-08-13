"""LQR controller (Phase 1, Task 1.5).

Builds the state-feedback gain from the continuous-time linearization
(A, B) about the upright equilibrium and the cost matrices Q, R:

    min  int_0^inf (X' Q X + u' R u) dt
    u   = -K X

Q is built from the block-diagonal weights (q_pos, q_vel, q_angle,
q_angle_vel) unless an explicit Q matrix is supplied.
"""

from __future__ import annotations

import numpy as np
import scipy.linalg

from config import ControllerParams
from controllers.base_controller import BaseController
from dynamics.state_space import build_lqr_Q


class LQRController(BaseController):
    def __init__(
        self,
        cparams: ControllerParams,
        A: np.ndarray,
        B: np.ndarray,
        u_max: float = 100.0,
    ) -> None:
        super().__init__(u_max)
        A = np.asarray(A, dtype=float)
        B = np.asarray(B, dtype=float)
        n = A.shape[0]
        self.N = (n - 2) // 2
        self.Q = self._build_q(cparams, self.N)
        self.R = np.array([[float(cparams.R)]])
        self.P = scipy.linalg.solve_continuous_are(A, B, self.Q, self.R)
        self.K = np.linalg.solve(self.R, B.T @ self.P).reshape(1, n)
        self._closed_loop_eigs = np.linalg.eigvals(A - B @ self.K)

    @staticmethod
    def _build_q(cparams: ControllerParams, N: int) -> np.ndarray:
        if cparams.Q is not None:
            Q = np.asarray(cparams.Q, dtype=float)
            if Q.shape != (2 * N + 2, 2 * N + 2):
                raise ValueError(f"Q must have shape {(2 * N + 2, 2 * N + 2)}")
            return Q
        return build_lqr_Q(
            N,
            q_pos=cparams.q_pos,
            q_vel=cparams.q_vel,
            q_angle=cparams.q_angle,
            q_angle_vel=cparams.q_angle_vel,
        )

    def compute(self, state: np.ndarray, t: float) -> float:
        return self.saturate(float(-(self.K @ np.asarray(state, dtype=float))[0]))

    @property
    def gain(self) -> np.ndarray:
        """The state-feedback gain K (1 x (2N+2))."""
        return self.K
