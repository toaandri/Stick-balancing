"""Closed-loop stability tests (Phase 0 deliverable)."""

import numpy as np

from config import load_defaults, load_controller_defaults
from simulation.mujoco_model import compile_model
from simulation.simulator import Simulator
from controllers.factory import make_controller


def _run(params, cparams, theta_deg):
    model, data = compile_model(params.N, params)
    sim = Simulator(model, data, ctrl_dt=params.ctrl_dt, physics_dt=params.physics_dt)
    controller = make_controller(cparams, params.N, u_max=params.cart_max_force)
    th = None if theta_deg is None else np.asarray(theta_deg)
    return sim.run_headless(controller, params, cparams, theta_deg=th)


def test_n1_unstable_without_control():
    p = load_defaults()
    p.N = 1
    p.sim_time = 5.0
    cp = load_controller_defaults()
    cp.type = "none"
    res = _run(p, cp, [5.0])
    assert np.max(np.abs(np.rad2deg(res.theta))) > 45.0


def test_n1_pid_stabilizes_from_5deg():
    p = load_defaults()
    p.N = 1
    p.sim_time = 8.0
    cp = load_controller_defaults()
    assert cp.type == "pid"
    res = _run(p, cp, [5.0])
    deg = np.rad2deg(res.theta[0])
    # final angle near zero, never swung far, cart bounded
    assert abs(deg[-1]) < 0.5
    assert np.max(np.abs(deg)) < 15.0
    assert np.max(np.abs(res.x)) < 5.0


def test_n1_pid_stabilizes_from_10deg():
    p = load_defaults()
    p.N = 1
    p.sim_time = 8.0
    cp = load_controller_defaults()
    res = _run(p, cp, [10.0])
    deg = np.rad2deg(res.theta[0])
    assert abs(deg[-1]) < 0.5
    assert np.max(np.abs(deg)) < 20.0


def test_seeded_random_ic_is_reproducible():
    p = load_defaults()
    p.N = 1
    p.sim_time = 2.0
    p.initial_condition = "random"
    p.theta_max_deg = 5.0
    cp = load_controller_defaults()
    r1 = _run(p, cp, None)
    r2 = _run(p, cp, None)
    assert np.allclose(r1.theta, r2.theta)
    assert np.allclose(r1.u, r2.u)