"""Cross-validation of the sympy symbolic model vs the recursive model (Task 1.3)."""

import numpy as np
import pytest

from dynamics.recursive_model import RecursivePendulumChain
from dynamics.symbolic_model import SymbolicPendulumChain

I_SEG = 0.04520324  # matches the MuJoCo rod inertia used in model tests


@pytest.mark.parametrize("N", [1, 2, 3])
def test_symbolic_matches_recursive(N):
    rec = RecursivePendulumChain(2.0, 0.5, 1.0, 0.2, 9.81, segment_inertia=I_SEG)
    sym = SymbolicPendulumChain(2.0, 0.5, 1.0, 0.2, 9.81, segment_inertia=I_SEG)
    rec.set_N(N)
    rng = np.random.default_rng(10 * N)
    q = np.concatenate([[0.3], rng.uniform(-0.4, 0.4, N)])
    qd = np.concatenate([[0.5], rng.uniform(-0.5, 0.5, N)])
    M_sym = np.asarray(sym.mass_matrix(N, list(q)), dtype=float)
    M_rec = rec.mass_matrix(q)
    h_sym = np.asarray(sym.bias(N, list(q), list(qd)), dtype=float)
    h_rec = rec.bias(q, qd)
    assert np.max(np.abs(M_sym - M_rec)) < 1e-10
    assert np.max(np.abs(h_sym - h_rec)) < 1e-10


def test_symbolic_mass_matrix_is_symmetric_and_positive():
    sym = SymbolicPendulumChain(2.0, 0.5, 1.0)
    N = 2
    M = np.asarray(sym.mass_matrix(N, [0.2, 0.1, -0.1]), dtype=float)
    assert np.allclose(M, M.T, atol=1e-12)
    assert np.all(np.linalg.eigvalsh(M) > 0)


def test_symbolic_vertical_gravity_torque():
    # single pendulum tilted by theta: hinge torque = -m g (L/2) sin(theta)
    sym = SymbolicPendulumChain(2.0, 0.5, 1.0, gravity=9.81)
    theta = 0.3
    h = np.asarray(sym.bias(1, [0.0, theta], [0.0, 0.0]), dtype=float)
    assert abs(h[1] - (-0.5 * 9.81 * 0.5 * np.sin(theta))) < 1e-12
