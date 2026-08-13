"""Tests for the LQR controller (Phase 1, Task 1.5)."""

import numpy as np
import pytest
import scipy.linalg

from config import ControllerParams, load_controller_defaults, load_defaults
from controllers.factory import make_controller
from controllers.lqr import LQRController
from dynamics.linearization import linearize_around_vertical
from dynamics.recursive_model import RecursivePendulumChain
from simulation.mujoco_model import compile_model
from simulation.simulator import Simulator


def _rec(N):
    params = load_defaults()
    params.N = N
    model, _ = compile_model(N, params)
    rec = RecursivePendulumChain(
        cart_mass=params.cart_mass,
        segment_mass=params.segment_mass,
        segment_length=params.segment_length,
        cart_height=params.cart_height,
        segment_inertia=float(model.body_inertia[2, 1]),
    )
    rec.set_N(N)
    A, B, _ = linearize_around_vertical(rec)
    return A, B


def test_closed_form_2state_pendulum():
    # Pendulum-only LQR: A=[[0,1],[a,0]], B=[[0],[b]]. Closed-form gains:
    #   k1 = (a + sqrt(a^2 + (b^2/r) q1)) / b
    #   k2 = sqrt((2 p2 + q3) / r),  p2 = (a + sqrt(a^2 + (b^2/r) q1)) / (b^2/r)
    a, b, r = 14.41, 1.0, 1.0
    q1, q3 = 1.0, 1.0
    A = np.array([[0.0, 1.0], [a, 0.0]])
    B = np.array([[0.0], [b]])
    Q = np.diag([q1, q3])
    P = scipy.linalg.solve_continuous_are(A, B, Q, np.array([[r]]))
    K = np.linalg.solve(np.array([[r]]), B.T @ P)
    kappa = b**2 / r
    p2 = (a + np.sqrt(a**2 + kappa * q1)) / kappa
    k1 = (a + np.sqrt(a**2 + kappa * q1)) / b
    k2 = np.sqrt((2 * p2 + q3) / r)
    assert abs(K[0, 0] - k1) < 1e-6
    assert abs(K[0, 1] - k2) < 1e-6


@pytest.mark.parametrize("N", [1, 2, 3])
def test_are_residual(N):
    A, B = _rec(N)
    cp = ControllerParams(type="lqr")
    lqr = LQRController(cp, A, B)
    n = A.shape[0]
    P = lqr.P
    residual = P @ A + A.T @ P - P @ B @ np.linalg.solve(lqr.R, B.T @ P) + lqr.Q
    assert np.max(np.abs(residual)) < 1e-8
    # K = R^{-1} B' P
    K_expected = np.linalg.solve(lqr.R, B.T @ P)
    assert np.max(np.abs(lqr.K - K_expected.reshape(1, n))) < 1e-8


@pytest.mark.parametrize("N", [1, 2, 3])
def test_closed_loop_stable_eigenvalues(N):
    A, B = _rec(N)
    cp = ControllerParams(type="lqr")
    lqr = LQRController(cp, A, B)
    assert np.all(np.real(lqr._closed_loop_eigs) < 0)


@pytest.mark.parametrize("N", [1, 3, 5])
def test_lqr_stabilizes_from_5deg(N):
    p = load_defaults()
    p.N = N
    p.sim_time = 10.0
    model, data = compile_model(N, p)
    A, B = _rec(N)
    cp = load_controller_defaults()
    cp.type = "lqr"
    sim = Simulator(model, data, ctrl_dt=p.ctrl_dt, physics_dt=p.physics_dt)
    controller = make_controller(cp, N, u_max=p.cart_max_force, A=A, B=B)
    theta = np.full(N, np.deg2rad(5.0))
    res = sim.run_headless(controller, p, cp, theta_deg=theta)
    # weighted mean angle goes to zero, cart bounded
    w = np.linspace(1.0, 1.0, N) / N
    angle = w @ res.theta  # res.theta is (N, n_steps)
    assert abs(np.rad2deg(angle[-1])) < 1.0
    assert np.max(np.abs(res.x)) < 5.0