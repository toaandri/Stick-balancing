"""Linearization of the cart + N-link pendulum about the upright equilibrium.

State ordering X = [x, xdot, th1, th1dot, ..., thN, thNdot] (2N+2 states), input
u = cart force. The MuJoCo dynamics M(q) qdd = h(q, qd) + B u (h includes
gravity, Coriolis and centrifugal; B = e_0 because the actuator is the cart
motor) is linearized about (q, qd) = (0, 0):

    dX/dt = A X + B u

with A_qq = M(0)^{-1} dG/dq (dG/dq = Jacobian of the gravity/bias vector with
respect to q at the equilibrium; the velocity-dependent part vanishes since
C(q, 0) = 0).
"""

from __future__ import annotations

from typing import Any

import numpy as np

import mujoco

from config import SystemParams
from simulation.mujoco_model import compile_model


def _interleave(A_qq: np.ndarray, B_qu: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Pack qdd = A_qq q + B_qu u into controller-state (X) form A, B."""
    nv = A_qq.shape[0]
    n = 2 * nv
    A = np.zeros((n, n))
    B = np.zeros((n, 1))
    for i in range(nv):
        A[2 * i, 2 * i + 1] = 1.0
        A[2 * i + 1, 0::2] = A_qq[i]
        B[2 * i + 1, 0] = B_qu[i]
    return A, B


def linearize_around_vertical(recursive_model: Any) -> tuple[np.ndarray, np.ndarray, dict]:
    """Analytic linearization via finite-difference Jacobians of the bias.

    Args:
        recursive_model: a RecursivePendulumChain with set_N() already applied.

    Returns:
        (A, B, info): continuous-time matrices in state ordering X, plus the
        equilibrium mass matrix / gravity Jacobian.
    """
    rec = recursive_model
    nv = rec.nv
    q = np.zeros(nv)
    qd = np.zeros(nv)

    M0 = rec.mass_matrix(q)
    G0 = rec.gravity(q)
    dG = np.zeros((nv, nv))
    eps = 1e-7
    for k in range(nv):
        qp = q.copy()
        qp[k] += eps
        qm = q.copy()
        qm[k] -= eps
        dG[:, k] = (rec.gravity(qp) - rec.gravity(qm)) / (2.0 * eps)

    Minv = np.linalg.inv(M0)
    # M dqdd = -dG dq + B_u du  (dG = d(qfrc_bias)/dq, the standard gravity bias)
    A_qq = -Minv @ dG
    B_qu = Minv @ np.eye(nv)[:, 0]
    A, B = _interleave(A_qq, B_qu)
    info = {"M0": M0, "G0": G0, "dG": dG}
    return A, B, info


def linearize_mujoco(model: mujoco.MjModel, data: mujoco.MjData) -> tuple[np.ndarray, np.ndarray]:
    """Numerical linearization straight from MuJoCo (finite differences of qfrc_bias)."""
    nv = model.nv
    data.qpos[:] = 0.0
    data.qvel[:] = 0.0
    mujoco.mj_forward(model, data)
    M0 = np.zeros((nv, nv))
    mujoco.mj_fullM(model, data, M0)
    bias0 = data.qfrc_bias.copy()

    dB = np.zeros((nv, nv))
    eps = 1e-7
    for k in range(nv):
        data.qpos[:] = 0.0
        data.qpos[k] += eps
        mujoco.mj_forward(model, data)
        bp = data.qfrc_bias.copy()
        data.qpos[:] = 0.0
        data.qpos[k] -= eps
        mujoco.mj_forward(model, data)
        bm = data.qfrc_bias.copy()
        dB[:, k] = (bp - bm) / (2.0 * eps)

    data.qpos[:] = 0.0
    mujoco.mj_forward(model, data)
    Minv = np.linalg.inv(M0)
    A_qq = -Minv @ dB
    B_qu = Minv @ np.eye(nv)[:, 0]
    A, B = _interleave(A_qq, B_qu)
    return A, B


def compare_linearizations(N: int, params: SystemParams | None = None) -> dict:
    """Max difference between analytic and MuJoCo A matrices for given N."""
    from dynamics.recursive_model import RecursivePendulumChain

    if params is None:
        from config import load_defaults

        params = load_defaults()
    params.N = N
    model, data = compile_model(N, params)
    rec = RecursivePendulumChain(
        cart_mass=params.cart_mass,
        segment_mass=params.segment_mass,
        segment_length=params.segment_length,
        cart_height=params.cart_height,
        segment_inertia=float(model.body_inertia[2, 1]),
    )
    rec.set_N(N)
    A_an, B_an, info = linearize_around_vertical(rec)
    A_mj, B_mj = linearize_mujoco(model, data)
    return {
        "N": N,
        "max_A_diff": float(np.max(np.abs(A_an - A_mj))),
        "max_B_diff": float(np.max(np.abs(B_an - B_mj))),
        "A_an": A_an,
        "B_an": B_an,
        "A_mj": A_mj,
        "B_mj": B_mj,
    }