"""Validation of the recursive analytical dynamics against MuJoCo (Phase 1).

The MuJoCo model is the source of truth: data.M (via mj_fullM) and
data.qfrc_bias. The recursive Newton-Euler model must reproduce both to
machine precision for any N and any (q, qd).
"""

import numpy as np
import pytest

import mujoco

from config import load_defaults
from dynamics.recursive_model import RecursivePendulumChain
from simulation.mujoco_model import compile_model


def _make(N: int):
    p = load_defaults()
    p.N = N
    m, d = compile_model(N, p)
    rec = RecursivePendulumChain(
        cart_mass=2.0,
        segment_mass=0.5,
        segment_length=1.0,
        cart_height=0.2,
        segment_inertia=float(m.body_inertia[2, 1]),
    )
    rec.set_N(N)
    return m, d, rec


def _assert_close(a, b, tol, what, N):
    err = np.max(np.abs(a - b))
    assert err < tol, f"N={N} {what}: max abs diff = {err:.2e}"


@pytest.mark.parametrize("N", [1, 2, 3, 5, 10])
def test_mass_matrix_matches_mujoco(N):
    m, d, rec = _make(N)
    rng = np.random.default_rng(N)
    q = np.concatenate([[0.3], rng.uniform(-0.4, 0.4, N)])
    d.qpos[:] = q
    mujoco.mj_forward(m, d)
    Md = np.zeros((m.nv, m.nv))
    mujoco.mj_fullM(m, d, Md)
    M_an = rec.mass_matrix(q)
    _assert_close(M_an, Md, 1e-9, "M(q)", N)
    _assert_close(M_an, M_an.T, 1e-10, "M symmetry", N)


@pytest.mark.parametrize("N", [1, 2, 3, 5, 10])
def test_bias_matches_mujoco(N):
    m, d, rec = _make(N)
    rng = np.random.default_rng(100 + N)
    q = np.concatenate([[0.3], rng.uniform(-0.4, 0.4, N)])
    qd = np.concatenate([[0.5], rng.uniform(-0.5, 0.5, N)])
    d.qpos[:] = q
    d.qvel[:] = qd
    mujoco.mj_forward(m, d)
    _assert_close(rec.bias(q, qd), d.qfrc_bias, 1e-9, "h(q,qd)", N)


@pytest.mark.parametrize("N", [2, 3, 6])
def test_gravity_matches_mujoco_at_rest(N):
    m, d, rec = _make(N)
    rng = np.random.default_rng(200 + N)
    q = np.concatenate([[0.0], rng.uniform(-1.0, 1.0, N)])
    d.qpos[:] = q
    d.qvel[:] = 0.0
    mujoco.mj_forward(m, d)
    _assert_close(rec.gravity(q), d.qfrc_bias, 1e-9, "G(q)", N)


@pytest.mark.parametrize("N", [1, 3])
def test_matches_at_large_angles_and_speeds(N):
    m, d, rec = _make(N)
    rng = np.random.default_rng(300 + N)
    q = np.concatenate([[rng.uniform(-1, 1)], rng.uniform(-2.0, 2.0, N)])
    qd = np.concatenate([[rng.uniform(-2, 2)], rng.uniform(-2.0, 2.0, N)])
    d.qpos[:] = q
    d.qvel[:] = qd
    mujoco.mj_forward(m, d)
    Md = np.zeros((m.nv, m.nv))
    mujoco.mj_fullM(m, d, Md)
    _assert_close(rec.mass_matrix(q), Md, 1e-8, "M(q)", N)
    _assert_close(rec.bias(q, qd), d.qfrc_bias, 1e-8, "h(q,qd)", N)


def test_mass_matrix_at_vertical_known_values():
    m, d, rec = _make(3)
    q = np.zeros(4)
    d.qpos[:] = q
    mujoco.mj_forward(m, d)
    Md = np.zeros((m.nv, m.nv))
    mujoco.mj_fullM(m, d, Md)
    M_an = rec.mass_matrix(q)
    assert abs(M_an[0, 1] - Md[0, 1]) < 1e-12
    # at vertical: M[0,0] = m_cart + N*m ; M[0,1] = m * sum_{k=0}^{N-1} (k*L + L/2)
    assert abs(M_an[0, 0] - (2.0 + 3 * 0.5)) < 1e-12
    assert abs(M_an[0, 1] - 0.5 * (0.5 + 1.5 + 2.5)) < 1e-12
