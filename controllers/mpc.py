"""MPC controller: finite-horizon LQR solved by Riccati recursion (Phase 3, Task 3.3).

The fixed-model controller solves the discrete finite-horizon LQR problem

    min  sum_{k=0}^{H-1} (x_k' Q x_k + u_k' R u_k) + x_H' Q x_H

once via backward Riccati recursion and applies the first gain at each step.
Actuator clipping is applied afterward; this is not a constrained QP solver.
Large-N stability is not guaranteed.
"""

from __future__ import annotations

import numpy as np
import scipy.linalg

from config import ControllerParams
from controllers.base_controller import BaseController
from controllers.lqr import LQRController


class MPCController(BaseController):
    def __init__(
        self,
        cparams: ControllerParams,
        A: np.ndarray,
        B: np.ndarray,
        dt: float = 0.02,
        u_max: float = 100.0,
    ) -> None:
        super().__init__(u_max)
        cparams.validate()
        if not np.isfinite(dt) or dt <= 0:
            raise ValueError('dt must be finite and positive')
        A = np.asarray(A, dtype=float)
        B = np.asarray(B, dtype=float)
        n = A.shape[0]
        self.N = (n - 2) // 2
        self.dt = float(dt)
        self.horizon = int(cparams.mpc_horizon)

        self.Q = self._build_q(cparams, self.N)
        self.R = np.array([[float(cparams.R)]])

        # exact discretization of (A, B) at the control period
        m = A.shape[0]
        aug = np.zeros((m + 1, m + 1))
        aug[:m, :m] = A
        aug[:m, m] = B.ravel()
        exp_aug = scipy.linalg.expm(aug * self.dt)
        self.Ad = exp_aug[:m, :m]
        self.Bd = exp_aug[:m, m].reshape(m, 1)

        # terminal cost = finite-horizon Riccati terminal P_H
        self.Pf = self.Q.copy()
        self.K = self._gain()

    @staticmethod
    def _build_q(cparams: ControllerParams, N: int) -> np.ndarray:
        return LQRController._build_q(cparams, N)

    def _gain(self) -> np.ndarray:
        """The fixed model and horizon give a state-independent feedback gain."""
        Ad, Bd, Q, R, H = self.Ad, self.Bd, self.Q, self.R, self.horizon
        K_list = []
        P = self.Pf
        for _ in range(H):
            S = R + Bd.T @ P @ Bd
            K = np.linalg.solve(S, Bd.T @ P @ Ad)
            P = Q + Ad.T @ P @ Ad - Ad.T @ P @ Bd @ K
            K_list.append(K)
        # forward pass storing the trajectory of gains
        K0 = K_list[-1]
        return K0

    def _solve(self, x0: np.ndarray) -> float:
        u0 = -self.K @ x0
        return float(u0[0])

    def compute(self, state: np.ndarray, t: float) -> float:
        state = np.asarray(state, dtype=float).reshape(-1)
        return self.saturate(self._solve(state))
