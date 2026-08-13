"""State-space helpers: ordering conventions and discretization.

Controller state ordering (the project spec): X = [x, xdot, th1, th1dot, ..., thN, thNdot].
MuJoCo ordering: qpos = [x, th1..thN], qvel = [xdot, th1dot..thNdot].
"""

from __future__ import annotations

import numpy as np
import scipy.linalg


def mujoco_to_state(qpos: np.ndarray, qvel: np.ndarray) -> np.ndarray:
    """Convert MuJoCo qpos/qvel vectors into controller state ordering X."""
    qpos = np.asarray(qpos, dtype=float)
    qvel = np.asarray(qvel, dtype=float)
    if qpos.shape[0] != qvel.shape[0]:
        raise ValueError("qpos and qvel must have the same dimension")
    nv = qpos.shape[0]
    N = nv - 1
    X = np.empty(2 * nv, dtype=float)
    X[0] = qpos[0]
    X[1] = qvel[0]
    X[2::2] = qpos[1:]
    X[3::2] = qvel[1:]
    return X


def state_to_mujoco(X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Convert controller state X back into MuJoCo qpos/qvel vectors."""
    X = np.asarray(X, dtype=float)
    n_state = X.shape[0]
    if n_state % 2 != 0:
        raise ValueError("state dimension must be even")
    nv = n_state // 2
    N = nv - 1
    qpos = np.empty(nv, dtype=float)
    qvel = np.empty(nv, dtype=float)
    qpos[0] = X[0]
    qvel[0] = X[1]
    qpos[1:] = X[2::2]
    qvel[1:] = X[3::2]
    return qpos, qvel


def build_lqr_Q(
    N: int,
    q_pos: float,
    q_vel: float,
    q_angle: float,
    q_angle_vel: float,
) -> np.ndarray:
    """Build the diagonal Q matrix for state X = [x, xd, th1, th1d, ...]."""
    n = 2 * N + 2
    Q = np.zeros((n, n))
    Q[0, 0] = q_pos
    Q[1, 1] = q_vel
    Q[2::2, 2::2] = q_angle
    Q[3::2, 3::2] = q_angle_vel
    return Q


def discretize_continuous(A: np.ndarray, B: np.ndarray, dt: float) -> tuple[np.ndarray, np.ndarray]:
    """Exact ZOH discretization of the continuous system xdot = Ax + Bu."""
    A = np.asarray(A, dtype=float)
    B = np.asarray(B, dtype=float)
    n = A.shape[0]
    M = np.block([[A, B], [np.zeros((1, n)), np.zeros((1, 1))]]) * dt
    expM = scipy.linalg.expm(M)
    Ad = expM[:n, :n]
    Bd = expM[:n, n:]
    return Ad, Bd