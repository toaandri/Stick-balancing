"""Tests for experiments/runner.py and experiments/benchmark.py (Task 2.2)."""

import numpy as np
import pytest

from analysis import success
from config import ControllerParams, load_defaults, load_controller_defaults
from experiments import (
    run_experiment,
    save_result,
    load_result,
    make_A_B,
    compare_controllers,
    sweep_n,
    sweep_qr,
    print_table,
)
from simulation.simulator import SimulationResult


@pytest.fixture
def n1_params():
    p = load_defaults()
    p.N = 1
    p.sim_time = 3.0
    return p


def test_run_experiment_pid_stabilizes(n1_params):
    cp = load_controller_defaults()
    cp.type = "pid"
    res = run_experiment(n1_params, cp, theta_deg=[5.0])
    assert success(res.theta, res.x)
    assert np.rad2deg(res.theta[0, -1]) < 1.0


def test_run_experiment_none_diverges(n1_params):
    cp = ControllerParams(type="none")
    res = run_experiment(n1_params, cp, theta_deg=[5.0])
    assert not success(res.theta, res.x)


def test_run_experiment_lqr_stabilizes(n1_params):
    cp = load_controller_defaults()
    cp.type = "lqr"
    res = run_experiment(n1_params, cp, theta_deg=[5.0])
    assert success(res.theta, res.x)


def test_make_A_B_dims():
    p = load_defaults()
    p.N = 3
    A, B = make_A_B(p)
    assert A.shape == (8, 8)
    assert B.shape == (8, 1)


def test_save_load_roundtrip(n1_params, tmp_path):
    cp = load_controller_defaults()
    cp.type = "pid"
    res = run_experiment(n1_params, cp, theta_deg=[5.0])
    path = save_result(res, tmp_path / "run")
    loaded = load_result(path)
    assert isinstance(loaded, SimulationResult)
    assert np.allclose(loaded.t, res.t)
    assert np.allclose(loaded.states, res.states)
    assert np.allclose(loaded.theta, res.theta)


def test_compare_controllers_rows(n1_params):
    cp = load_controller_defaults()
    cp.type = "pid"
    cpl = load_controller_defaults()
    cpl.type = "lqr"
    rows = compare_controllers(
        n1_params, [("pid", cp), ("lqr", cpl)], N=1, theta_deg=5.0
    )
    assert len(rows) == 2
    assert {r["name"] for r in rows} == {"pid", "lqr"}
    assert all(r["N"] == 1 for r in rows)
    assert all(r["success"] for r in rows)


def test_sweep_n_rows(n1_params):
    cp = load_controller_defaults()
    cp.type = "pid"
    rows = sweep_n(n1_params, cp, Ns=[1, 2], theta_deg=5.0)
    assert len(rows) == 2
    assert [r["N"] for r in rows] == [1, 2]


def test_sweep_qr_rows(n1_params):
    rows = sweep_qr(n1_params, N=1, theta_deg=5.0, qa_values=(10.0, 100.0), R_values=(0.1, 1.0))
    assert len(rows) == 4
    assert {r["name"] for r in rows} == {"qa=10,R=0.1", "qa=10,R=1", "qa=100,R=0.1", "qa=100,R=1"}


def test_print_table_renders(n1_params):
    cp = load_controller_defaults()
    cp.type = "pid"
    rows = compare_controllers(n1_params, [("pid", cp)], N=1, theta_deg=5.0)
    table = print_table(rows)
    assert "pid" in table
    assert "N" in table