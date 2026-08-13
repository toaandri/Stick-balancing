"""Tests for the PID controller (Phase 0)."""

import numpy as np

from config import ControllerParams
from controllers.pid import PIDController


def _pid(**kw):
    u_max = kw.pop("u_max", 100.0)
    defaults = {"kp": 0.0, "ki": 0.0, "kd": 0.0, "kp_cart": 0.0, "kd_cart": 0.0}
    defaults.update(kw)
    cp = ControllerParams(type="pid", **defaults)
    return PIDController(cp, N=1, u_max=u_max)


def test_proportional_output():
    pid = _pid(kp=10.0)
    state = np.array([0.0, 0.0, 0.1, 0.0])  # theta1 = 0.1 rad
    u = pid.compute(state, 0.0)
    assert abs(u - 1.0) < 1e-9


def test_cart_term():
    pid = _pid(kp_cart=4.0, kd_cart=0.0)
    state = np.array([0.5, 0.0, 0.0, 0.0])  # cart at 0.5 m
    u = pid.compute(state, 0.0)
    assert abs(u - 2.0) < 1e-9


def test_integral_accumulates():
    pid = _pid(ki=2.0)
    state = np.array([0.0, 0.0, 0.1, 0.0])
    pid.compute(state, 0.0)
    u = pid.compute(state, 0.5)
    # integral = 0.1 * 0.5 = 0.05 -> u = 2*0.05 = 0.1
    assert abs(u - 0.1) < 1e-9


def test_derivative_response():
    pid = _pid(kd=5.0)
    pid.compute(np.array([0.0, 0.0, 0.0, 0.0]), 0.0)
    u = pid.compute(np.array([0.0, 0.0, 0.1, 0.0]), 0.01)
    # derivative of 0.1 rad over 0.01 s = 10 -> u = 5*10 = 50
    assert abs(u - 50.0) < 1e-6


def test_saturation():
    pid = _pid(kp=100.0, u_max=100.0)
    state = np.array([0.0, 0.0, 2.0, 0.0])  # would give u = 200
    u = pid.compute(state, 0.0)
    assert abs(u - 100.0) < 1e-9


def test_reset_clears_integral():
    pid = _pid(ki=2.0)
    state = np.array([0.0, 0.0, 0.1, 0.0])
    pid.compute(state, 0.0)
    pid.compute(state, 0.5)
    pid.reset()
    assert pid.compute(state, 0.0) == 0.0


def test_weighted_multijoint_error():
    pid = _pid(kp=10.0)
    pid.w = np.array([0.5, 0.5])
    # error = 0.5*0.2 + 0.5*0.0 = 0.1 -> u = 1.0
    state = np.array([0.0, 0.0, 0.2, 0.0, 0.0, 0.0])
    assert abs(pid.compute(state, 0.0) - 1.0) < 1e-9