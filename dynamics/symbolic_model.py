"""Symbolic (sympy) analytical dynamics of a cart + N-link pendulum.

Derives the mass matrix M(q) and bias vector h(q, qd) = C(q,qd) qd + G(q)
from the Lagrangian L = T - V using sympy, then evaluates them numerically via
lambdify. Used to cross-check the recursive Newton-Euler model for N = 1..3.

Convention (identical to MuJoCo / recursive_model): q = [x, th1..thN],
qd = [xd, thd1..thdN]. Segment i's world axis is e(theta_1+...+theta_i).
"""

from __future__ import annotations

import sympy as sp


def _e(phi: sp.Expr) -> tuple[sp.Expr, sp.Expr]:
    return (sp.sin(phi), sp.cos(phi))


def _t(phi: sp.Expr) -> tuple[sp.Expr, sp.Expr]:
    return (sp.cos(phi), -sp.sin(phi))


class SymbolicPendulumChain:
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
            self.I = self.m * self.L * self.L / 12.0 + self.m * self.r * self.r / 4.0
        else:
            self.I = float(segment_inertia)
        self._cache: dict[int, tuple[callable, callable]] = {}

    # ------------------------------------------------------------ build
    def _expressions(self, N: int) -> tuple[callable, callable]:
        """Build lambdified M(q) and h(q, qd) callables for given N."""
        if N in self._cache:
            return self._cache[N]

        x = sp.Symbol("x")
        xd = sp.Symbol("xd")
        th = sp.symbols(f"th1:{N + 1}")
        thd = sp.symbols(f"thd1:{N + 1}")
        q = (x,) + th
        qd = (xd,) + thd

        phi = [sum(th[: i + 1]) for i in range(N)]        # absolute angles
        phid = [sum(thd[: i + 1]) for i in range(N)]      # absolute rates

        # CM position/velocity of each segment (x, z)
        c = []
        cd = []
        for i in range(N):
            e_i = _e(phi[i])
            t_i = _t(phi[i])
            cx = x + self.L * sum(_e(phi[k])[0] for k in range(i)) + (self.L / 2) * e_i[0]
            cz = self.L * sum(_e(phi[k])[1] for k in range(i)) + (self.L / 2) * e_i[1]
            c.append((cx, cz))
            cdx = xd + self.L * sum(phid[k] * _t(phi[k])[0] for k in range(i)) \
                + (self.L / 2) * phid[i] * t_i[0]
            cdz = self.L * sum(phid[k] * _t(phi[k])[1] for k in range(i)) \
                + (self.L / 2) * phid[i] * t_i[1]
            cd.append((cdx, cdz))

        # kinetic + potential energy
        T = sp.Rational(1, 2) * self.m_c * xd ** 2
        for i in range(N):
            T += sp.Rational(1, 2) * self.m * (cd[i][0] ** 2 + cd[i][1] ** 2)
            T += sp.Rational(1, 2) * self.I * phid[i] ** 2
        V = 0
        for i in range(N):
            V += self.m * self.g * (self.h + c[i][1])

        # M_ij = d^2T / dqd_i dqd_j
        M = sp.Matrix(N + 1, N + 1, lambda i, j: sp.diff(T, qd[i], qd[j]))

        # h_j = sum_k d(dT/dqd_j)/dq_k * qd_k - dT/dq_j + dV/dq_j
        h = sp.zeros(N + 1, 1)
        for j in range(N + 1):
            dT_qd = sp.diff(T, qd[j])
            cor = sum(sp.diff(dT_qd, q[k]) * qd[k] for k in range(N + 1))
            h[j] = sp.simplify(cor - sp.diff(T, q[j]) + sp.diff(V, q[j]))

        f_M = sp.lambdify((q,), M, modules="numpy")
        f_h = sp.lambdify((q, qd), [h[i, 0] for i in range(N + 1)], modules="numpy")
        self._cache[N] = (f_M, f_h)
        return f_M, f_h

    # ----------------------------------------------------------- evaluate
    def mass_matrix(self, N: int, q: list[float]) -> object:
        """Numeric M(q) as a numpy-like matrix (lambdified)."""
        f_M, _ = self._expressions(N)
        return f_M(tuple(q))

    def bias(self, N: int, q: list[float], qd: list[float]) -> object:
        """Numeric h(q, qd) = C qd + G as a vector (lambdified)."""
        _, f_h = self._expressions(N)
        return f_h(tuple(q), tuple(qd))
