"""Tests for the simulator and state handling (Phase 0)."""

import numpy as np
import mujoco

from config import load_defaults, ControllerParams
from dynamics.state_space import mujoco_to_state, state_to_mujoco
from simulation.mujoco_model import compile_model
from simulation.simulator import Simulator
from controllers.factory import make_controller


def _sim_n1(params=None):
    p = params or load_defaults()
    p.N = 1
    model, data = compile_model(1, p)
    return Simulator(model, data, ctrl_dt=p.ctrl_dt, physics_dt=p.physics_dt)


def test_state_ordering():
    sim = _sim_n1()
    qpos = np.array([1.5, 0.3])
    qvel = np.array([0.2, -0.4])
    sim.set_state(qpos, qvel)
    X = sim.get_state()
    assert X.shape == (4,)
    assert X[0] == 1.5  # x
    assert X[1] == 0.2  # xdot
    assert X[2] == 0.3  # theta1
    assert X[3] == -0.4  # thetadot1
    qpos2, qvel2 = state_to_mujoco(X)
    assert np.allclose(qpos2, qpos)
    assert np.allclose(qvel2, qvel)


def test_free_swing_falls_from_30deg():
    sim = _sim_n1()
    p = load_defaults()
    cp = ControllerParams(type="none")
    res = sim.run_headless(make_controller(cp, 1), p, cp, theta_deg=np.array([30.0]))
    assert np.max(np.abs(np.rad2deg(res.theta))) > 45.0


def test_impulse_changes_velocity():
    sim = _sim_n1()
    sim.reset()
    v0 = sim.data.qvel.copy()
    sim.apply_impulse("cart", np.array([50.0, 0.0, 0.0]), duration=0.1)
    for _ in range(100):
        sim.step(0.0)
    assert sim.data.qvel[0] != v0[0]


def test_vertical_stays_vertical_open_loop():
    sim = _sim_n1()
    p = load_defaults()
    p.initial_condition = "vertical"
    cp = ControllerParams(type="none")
    res = sim.run_headless(make_controller(cp, 1), p, cp)
    assert np.allclose(res.theta, 0.0, atol=1e-9)