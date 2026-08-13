"""Tests for the linearization module (Task 1.4)."""

import numpy as np
import pytest

from config import load_defaults
from dynamics.linearization import compare_linearizations, linearize_around_vertical
from dynamics.recursive_model import RecursivePendulumChain
from simulation.mujoco_model import compile_model


@pytest.mark.parametrize("N", [1, 2, 3])
def test_dims(N):
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
    A, B, info = linearize_around_vertical(rec)
    assert A.shape == (2 * N + 2, 2 * N + 2)
    assert B.shape == (2 * N + 2, 1)


@pytest.mark.parametrize("N", [1, 2, 3])
def test_analytic_matches_mujoco(N):
    r = compare_linearizations(N)
    assert r["max_A_diff"] < 1e-3
    assert r["max_B_diff"] < 1e-3


@pytest.mark.parametrize("N", [1, 2, 3])
def test_n_unstable_poles(N):
    r = compare_linearizations(N)
    ev = np.linalg.eigvals(r["A_an"])
    assert np.sum(np.real(ev) > 1e-8) == N


@pytest.mark.parametrize("N", [1, 2, 3])
def test_controllable(N):
    r = compare_linearizations(N)
    A, B = r["A_an"], r["B_an"]
    n = A.shape[0]
    Ctrb = B
    for _ in range(n - 1):
        Ctrb = np.hstack([Ctrb, A @ Ctrb[:, -1:]])
    assert np.linalg.matrix_rank(Ctrb) == n


def test_n1_known_eigenvalue():
    r = compare_linearizations(1)
    ev = np.linalg.eigvals(r["A_an"])
    pos = np.max(ev[ev > 0])
    m, L, g, I = 0.5, 1.0, 9.81, 0.04520324
    M00, M01, M11 = 2.5, m * L / 2, m * (L / 2) ** 2 + I
    expected = np.sqrt((m * g * L / 2) / (M11 - M01**2 / M00))
    assert abs(pos - expected) < 1e-6
