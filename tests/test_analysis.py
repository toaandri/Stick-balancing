"""Tests for analysis/metrics.py and analysis/comparison.py (Task 2.1)."""

import numpy as np
import pytest

from analysis import (
    rmse,
    mae,
    max_abs,
    weighted_mean_angle,
    settling_time,
    control_effort,
    control_energy,
    cost_J,
    success,
    build_table,
    format_results,
)


def test_rmse_known_value():
    assert rmse([0.0, 3.0, 4.0]) == pytest.approx(5.0 / np.sqrt(3))


def test_mae_and_max_abs():
    assert mae([-2.0, 2.0, 4.0]) == pytest.approx(8.0 / 3.0)
    assert max_abs([-2.0, 2.0, 4.0]) == pytest.approx(4.0)


def test_weighted_mean_angle_averages_segments():
    theta = np.array([[0.0, 0.2], [0.1, 0.0], [0.2, 0.4]])  # (N, steps)
    mean = weighted_mean_angle(theta)
    assert mean.shape == (2,)
    assert np.allclose(mean, [0.1, 0.2])


def test_settling_time_returns_first_stable_index():
    t = np.linspace(0.0, 10.0, 11)
    theta = np.array([5.0, 3.0, 1.5, 0.5, 0.2, 0.0, -0.1, 0.0, 0.05, 0.0, 0.02])
    theta = np.deg2rad(theta)[None, :]
    st = settling_time(theta, t, threshold_deg=1.0)
    assert st is not None
    # everything from index 3 onward stays within 1.0+0.1 deg
    assert st == pytest.approx(t[3])


def test_settling_time_none_when_never_settles():
    t = np.linspace(0.0, 5.0, 6)
    theta = np.deg2rad(np.array([5.0, 6.0, 4.0, 7.0, 8.0, 9.0]))[None, :]
    assert settling_time(theta, t, threshold_deg=1.0) is None


def test_settling_time_small_perturbation():
    t = np.linspace(0.0, 5.0, 6)
    theta = np.deg2rad(np.array([0.5, 0.4, 0.3, 0.2, 0.1, 0.0]))[None, :]
    assert settling_time(theta, t, threshold_deg=1.0) == pytest.approx(t[0])


def test_control_effort_and_energy():
    u = np.array([1.0, 2.0, 2.0])
    assert control_effort(u, 0.5) == pytest.approx((1 + 4 + 4) * 0.5)
    assert control_energy(u, 0.5) == pytest.approx((1 + 2 + 2) * 0.5)


def test_cost_J():
    states = np.array(
        [
            [1.0, 0.0, 0.0],  # state 0 over 3 steps
            [0.0, 1.0, 0.0],  # state 1 over 3 steps
        ]
    )  # (2, 3)
    u = np.array([[1.0], [1.0], [1.0]])  # (3, 1)
    Q = np.eye(2)
    R = np.eye(1)
    dt = 0.5
    expected = ((1.0 + 0.0) + (0.0 + 1.0) + (0.0 + 0.0) + 3 * 1.0) * dt
    assert cost_J(states, u, Q, R, dt) == pytest.approx(expected)


def test_success_flags():
    theta = np.deg2rad(np.array([[0.1, 0.05, 0.0]]))
    x = np.array([0.1, 0.05, 0.0])
    assert success(theta, x, angle_tol_deg=1.0, max_cart=5.0)
    assert not success(np.deg2rad([[5.0, 4.0, 3.0]]), x)
    assert not success(theta, np.array([6.0, 5.0, 4.0]), max_cart=5.0)


def test_build_table_padding_and_alignment():
    rows = [
        {"name": "pid", "cost": 1.25, "ok": True},
        {"name": "lqr", "cost": 0.5, "ok": False},
    ]
    table = build_table(rows, ["name", "cost", "ok"])
    lines = table.splitlines()
    assert len(lines) == 4
    assert lines[0].startswith("name")
    assert "lqr" in lines[3]
    assert "yes" in lines[2]
    assert "no" in lines[3]


def test_format_results_handles_nan_and_none():
    rows = [{"a": float("nan"), "b": None, "c": "x"}]
    table = format_results(rows, ["a", "b", "c"])
    assert "n/a" in table
    assert "x" in table