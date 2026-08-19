"""Tests for robustness, stability-limit and scalability experiments (Task 2.3)."""

import pytest

from config import ControllerParams, load_defaults, load_controller_defaults
from experiments import (
    sweep_initial_angle,
    sweep_friction,
    sweep_noise,
    sweep_delay,
    bisect_angle,
    step_time_ms,
    scalability_rows,
)


@pytest.fixture
def n1_params():
    p = load_defaults()
    p.N = 1
    p.sim_time = 4.0
    return p


@pytest.fixture
def pid():
    cp = load_controller_defaults()
    cp.type = "pid"
    return cp


def test_sweep_initial_angle(n1_params, pid):
    rows = sweep_initial_angle(n1_params, pid, angles_deg=[0.5, 5.0], N=1)
    assert len(rows) == 2
    assert [r["theta_deg"] for r in rows] == [0.5, 5.0]
    assert rows[0]["success"] is True
    assert rows[1]["success"] is False


def test_sweep_friction(n1_params, pid):
    rows = sweep_friction(n1_params, pid, friction_values=[0.0, 0.1], N=1, theta_deg=1.0)
    assert len(rows) == 2
    assert [r["friction"] for r in rows] == [0.0, 0.1]


def test_sweep_noise(n1_params, pid):
    rows = sweep_noise(n1_params, pid, noise_values=[0.0, 0.5], N=1, theta_deg=1.0, seeds=(0, 1))
    assert len(rows) == 2
    assert [r["noise_sigma"] for r in rows] == [0.0, 0.5]
    assert 0.0 <= rows[0]["success"] <= 1.0


def test_sweep_delay(n1_params, pid):
    rows = sweep_delay(n1_params, pid, delay_values=[0, 2], N=1, theta_deg=1.0)
    assert len(rows) == 2
    assert [r["delay_steps"] for r in rows] == [0, 2]


def test_bisect_angle(n1_params, pid):
    critical, iters, last = bisect_angle(n1_params, pid, lo=0.5, hi=5.0, tol=0.2)
    assert iters <= 25
    assert 0.5 <= critical <= 5.0
    # 0.5 deg must still stabilize, 5.0 deg must fail
    assert critical >= 0.5


def test_step_time_ms_positive(n1_params, pid):
    ms = step_time_ms(n1_params, pid, N=1, n_steps=50)
    assert ms > 0.0


def test_scalability_rows(n1_params):
    cp = load_controller_defaults()
    cp.type = "lqr"
    rows = scalability_rows(n1_params, cp, Ns=[1, 2], theta_deg=1.0)
    assert len(rows) == 2
    assert [r["N"] for r in rows] == [1, 2]
    assert all(r["step_ms"] > 0 for r in rows)
    assert all(r["success"] for r in rows)  # 1 deg is inside the LQR basin at N=1,2