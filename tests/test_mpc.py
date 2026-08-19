"""Tests for the MPC controller (Phase 3, Task 3.3)."""

import numpy as np
import pytest

from config import load_defaults, load_controller_defaults
from controllers.mpc import MPCController
from experiments import run_experiment, make_A_B
from analysis import success


@pytest.fixture
def n1_mpc():
    p = load_defaults()
    p.N = 1
    cp = load_controller_defaults()
    cp.type = "mpc"
    A, B = make_A_B(p)
    return p, cp, MPCController(cp, A, B, dt=p.ctrl_dt, u_max=100.0)


def test_mpc_horizon_default(n1_mpc):
    _, _, mpc = n1_mpc
    assert mpc.horizon >= 200  # large enough to stabilize the unstable mode


def test_mpc_discrete_matrices_dimensions(n1_mpc):
    _, _, mpc = n1_mpc
    assert mpc.Ad.shape == (4, 4)
    assert mpc.Bd.shape == (4, 1)


def test_mpc_closed_loop_stable_linear(n1_mpc):
    _, _, mpc = n1_mpc
    x = np.zeros(4)
    x[2] = np.deg2rad(2.0)
    for _ in range(5000):
        u = mpc.compute(x, 0.0)
        x = mpc.Ad @ x + (mpc.Bd * float(u)).ravel()
    assert np.linalg.norm(x) < 1e-3


def test_mpc_handles_column_state(n1_mpc):
    _, _, mpc = n1_mpc
    x = np.zeros((4, 1))
    x[2, 0] = np.deg2rad(1.0)
    u = mpc.compute(x, 0.0)
    assert isinstance(u, float)
    assert np.isfinite(u)


@pytest.mark.parametrize("N,angle", [(1, 5.0), (2, 2.0), (3, 1.0)])
def test_mpc_stabilizes_nonlinear(N, angle):
    p = load_defaults()
    p.N = N
    p.sim_time = 4.0
    cp = load_controller_defaults()
    cp.type = "mpc"
    res = run_experiment(p, cp, theta_deg=[angle] + [0.0] * (N - 1))
    assert success(res.theta, res.x)