"""Recursive (Newton-Euler) analytical dynamics of a cart + N-link pendulum.

Planar model: all motion happens in the x-z plane. Coordinates follow MuJoCo:
q = [x, theta_1, ..., theta_N], qd = [xdot, thetadot_1, ..., thetadot_N].
theta = 0 means the segment points straight up.

IMPORTANT geometric convention (matches MuJoCo): a child body is attached in
its parent's frame, so segment i's world-frame axis is e(theta_1+...+theta_i)
(absolute / cumulative angle), and joint i+1 sits at joint i + L e(absolute).

Implements the inverse dynamics tau(q, qd, qdd) (the force/torque each actuator
must apply to realize a given acceleration). From it we obtain:

    M(q)   : joint-space inertia matrix  (column j = inv_dyn(q, 0, e_j) - G)
    h(q,qd): bias force C(q,qd) qd + G(q) (inv_dyn(q, qd, 0))

The model is valid for any N. It is validated against MuJoCo (data.M via
mj_fullM and data.qfrc_bias) in the test suite.
"""

from __future__ import annotations

import numpy as np


class RecursivePendulumChain:
    def __init__(
        self,
        cart_mass: float,
        segment_mass: float,
        segment_length: float,
        cart_height: float = 0.2,
        gravity: float = 9.81,
        segment_inertia: float | None = None,
        segment_radius: float = 0.03,
    ) -> None:
        self.m_c = float(cart_mass)
        self.m = float(segment_mass)
        self.L = float(segment_length)
        self.h = float(cart_height)
        self.g = float(gravity)
        self.r = float(segment_radius)
        if segment_inertia is None:
            # rod + disk approximation about the y axis through the CM
            self.I = self.m * self.L * self.L / 12.0 + self.m * self.r * self.r / 4.0
        else:
            self.I = float(segment_inertia)
        self.N = 0
        self.nv = 0

    def set_N(self, N: int) -> None:
        self.N = int(N)
        self.nv = self.N + 1

    # ------------------------------------------------------------------ math
    def _theta(self, q: np.ndarray) -> np.ndarray:
        return np.asarray(q, dtype=float)[1:]

    def _theta_abs(self, q: np.ndarray) -> np.ndarray:
        """Absolute (world) orientation of each segment, i.e. cumulative sum.

        MuJoCo attaches a child body in its parent's frame, so segment i's
        axis direction in the world is e(theta_1 + ... + theta_i).
        """
        return np.cumsum(np.asarray(q, dtype=float)[1:])

    def kinematics(self, q: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Return base joints J_i, CMs c_i, axis e_i, tangent t_i (world frame).

        J_i: position of joint i (base of segment i), shape (N,3).
        c_i: center of mass of segment i, shape (N,3).
        e_i: unit vector along segment i (points up when theta=0).
        t_i: d(e_i)/d(theta_abs) = perpendicular direction.
        """
        th_abs = self._theta_abs(q)
        x = float(q[0])
        N = self.N
        e = np.stack([np.sin(th_abs), np.zeros(N), np.cos(th_abs)], axis=1)  # (N,3)
        t = np.stack([np.cos(th_abs), np.zeros(N), -np.sin(th_abs)], axis=1)
        J = np.empty((N, 3))
        c = np.empty((N, 3))
        J[0] = (x, 0.0, self.h)
        for i in range(N):
            c[i] = J[i] + (self.L / 2.0) * e[i]
            if i + 1 < N:
                J[i + 1] = J[i] + self.L * e[i]
        return J, c, e, t

    def cm_accel(self, q: np.ndarray, qd: np.ndarray, qdd: np.ndarray) -> np.ndarray:
        """Acceleration of each segment CM (N,3) given q, qd, qdd.

        The absolute angular rate of segment i is omega_i = sum_{k<=i} thd_k,
        and its absolute angular acceleration is omegadot_i = sum_{k<=i} thdd_k.
        d2(e_i)/dt2 = omegadot_i t_i - omega_i^2 e_i.
        """
        th_abs = self._theta_abs(q)
        thd = np.asarray(qd, dtype=float)[1:]
        thdd = np.asarray(qdd, dtype=float)[1:]
        xdd = float(qdd[0])
        N = self.N
        omega = np.cumsum(thd)
        omegadot = np.cumsum(thdd)
        Jdd = np.empty((N, 3))
        Jdd[0] = (xdd, 0.0, 0.0)
        a = np.empty((N, 3))
        for i in range(N):
            si, ci = np.sin(th_abs[i]), np.cos(th_abs[i])
            ti = np.array([ci, 0.0, -si])
            ei = np.array([si, 0.0, ci])
            # c_i = J_i + (L/2) e_i ; d2(c_i)/dt2 = Jdd_i
            #   + (L/2) (omegadot_i t_i - omega_i^2 e_i)
            a[i] = Jdd[i] + (self.L / 2.0) * (omegadot[i] * ti - omega[i] ** 2 * ei)
            if i + 1 < N:
                # J_{i+1} = J_i + L e_i ; d2/dt2 = Jdd_i + L (omegadot_i t_i - omega_i^2 e_i)
                Jdd[i + 1] = Jdd[i] + self.L * (omegadot[i] * ti - omega[i] ** 2 * ei)
        return a

    # ---------------------------------------------------------- inverse dyn
    def inv_dyn(self, q: np.ndarray, qd: np.ndarray, qdd: np.ndarray) -> np.ndarray:
        """Actuator forces tau for given motion: tau = M qdd + C qd + G.

        tau[0] is the cart force, tau[i] (i>=1) the torque at hinge i.
        """
        q = np.asarray(q, dtype=float)
        qd = np.asarray(qd, dtype=float)
        qdd = np.asarray(qdd, dtype=float)
        N = self.N
        _, c, e, _ = self.kinematics(q)
        a = self.cm_accel(q, qd, qdd)
        gvec = np.array([0.0, 0.0, -self.g])

        # net force each segment needs from the joints: m*(a - gvec)
        F = self.m * (a - gvec)
        # net moment each segment needs about its CM (y axis): I * alpha,
        # where alpha is the ABSOLUTE angular acceleration (cumulative sum).
        alpha = np.cumsum(np.asarray(qdd, dtype=float)[1:])
        tau = np.empty(self.nv)

        # Cart force: supports cart + all segments in x
        x_accel = np.asarray(qdd)[0]
        tau[0] = self.m_c * x_accel + float(F[:, 0].sum())

        # Hinge torques: subtree sum of (I*alpha + moment of F about joint i).
        # Standard cross product: (r x F)_y = r_z F_x - r_x F_z.
        for i in range(N):
            Ji = self._joint_pos(q, i)
            val = 0.0
            for k in range(i, N):
                rk = c[k] - Ji
                moment = rk[2] * F[k, 0] - rk[0] * F[k, 2]
                val += self.I * alpha[k] + moment
            tau[i + 1] = val
        return tau

    def _joint_pos(self, q: np.ndarray, i: int) -> np.ndarray:
        """World position of joint i (base of segment i), i in 0..N-1."""
        q = np.asarray(q, dtype=float)
        th_abs = self._theta_abs(q)
        if i == 0:
            return np.array([q[0], 0.0, self.h])
        pos = np.array([q[0], 0.0, self.h])
        for k in range(i):
            pos = pos + self.L * np.array([np.sin(th_abs[k]), 0.0, np.cos(th_abs[k])])
        return pos

    def mass_matrix(self, q: np.ndarray) -> np.ndarray:
        """Joint-space inertia matrix M(q), shape (nv, nv).

        inv_dyn(q, 0, e_j) = M e_j + G(q), so the gravity part G(q) is
        subtracted from each column.
        """
        q = np.asarray(q, dtype=float)
        G = self.gravity(q)
        M = np.empty((self.nv, self.nv))
        for j in range(self.nv):
            e = np.zeros(self.nv)
            e[j] = 1.0
            M[:, j] = self.inv_dyn(q, np.zeros(self.nv), e) - G
        return M

    def bias(self, q: np.ndarray, qd: np.ndarray) -> np.ndarray:
        """Bias force h = C(q,qd) qd + G(q).

        This matches MuJoCo's data.qfrc_bias directly.
        """
        return self.inv_dyn(q, qd, np.zeros(self.nv))

    def gravity(self, q: np.ndarray) -> np.ndarray:
        """Gravity torque vector G(q) (with zero velocity)."""
        return self.inv_dyn(q, np.zeros(self.nv), np.zeros(self.nv))

    def coriolis_and_gravity(self, q: np.ndarray, qd: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Decompose h = C(q,qd) qd + G(q) into (C_matrix, G).

        C is built from the Christoffel symbols of M(q):
            Gamma_ijk = 1/2 (dM_ij/dq_k + dM_ik/dq_j - dM_jk/dq_i),
            (C qd)_i = sum_jk Gamma_ijk qd_j qd_k,
        so that C(q,qd) qd + G(q) == h(q,qd) exactly.
        """
        q = np.asarray(q, dtype=float)
        qd = np.asarray(qd, dtype=float)
        G = self.gravity(q)
        M = self.mass_matrix(q)
        nv = self.nv
        eps = 1e-7
        dM = np.empty((nv, nv, nv))  # dM/dq_k
        for k in range(nv):
            qp = q.copy()
            qp[k] += eps
            qm = q.copy()
            qm[k] -= eps
            dM[:, :, k] = (self.mass_matrix(qp) - self.mass_matrix(qm)) / (2.0 * eps)
        C = np.zeros((nv, nv))
        for i in range(nv):
            for j in range(nv):
                s = 0.0
                for k in range(nv):
                    s += (dM[i, j, k] + dM[i, k, j] - dM[j, k, i]) * qd[k]
                C[i, j] = 0.5 * s
        return C, G