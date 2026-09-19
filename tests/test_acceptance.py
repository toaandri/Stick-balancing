"""Cahier des charges: physical behavior and reproducible experimental evidence."""
from dataclasses import replace
import json

import mujoco
import numpy as np
import pytest

from analysis import success, settling_time
from config import SystemParams, ControllerParams, PerturbationSpec
from controllers.base_controller import BaseController
from experiments import run_experiment, save_result, load_result, make_A_B
from simulation.mujoco_model import compile_model
from simulation.simulator import Simulator
from visualization.realtime import controller_step


class ConstantForce(BaseController):
    def compute(self, state, t):
        return 7.0


def test_command_delay_is_a_force_fifo_and_reset_clears_it():
    p = SystemParams(sim_time=0.05, command_delay_steps=2)
    model, data = compile_model(1, p)
    sim = Simulator(model, data)
    r = sim.run_headless(ConstantForce(), p, ControllerParams(type='none'), theta_deg=[0])
    np.testing.assert_array_equal(r.u_applied[:-1], [0, 0, 7, 7, 7])
    np.testing.assert_allclose(r.t, np.arange(6) * p.ctrl_dt, atol=1e-12)
    assert data.time == pytest.approx(p.sim_time)
    sim.reset()
    assert sim.step(7) == 0


def test_seed_override_and_configured_initial_conditions():
    p = SystemParams(sim_time=0.1, noise_sigma=0.01)
    cp = ControllerParams(type='pid')
    a = run_experiment(p, cp, seed=12)
    b = run_experiment(p, cp, seed=12)
    c = run_experiment(p, cp, seed=13)
    np.testing.assert_array_equal(a.states, b.states)
    assert not np.array_equal(a.states, c.states)
    assert p.seed == 42
    assert a.params['seed'] == 12
    assert a.theta[0, 0] != 0


def test_measurement_noise_does_not_corrupt_physics_logs():
    p = SystemParams(sim_time=0.1, initial_condition='vertical', noise_sigma=1)
    r = run_experiment(p, ControllerParams(type='none'))
    np.testing.assert_array_equal(r.states, np.zeros_like(r.states))


def test_opposing_and_cumulative_angles_cannot_hide_a_failure():
    for degrees in ([[20, 20], [-20, -20]], [[0.7, 0.7], [0.7, 0.7]]):
        theta = np.deg2rad(degrees)
        assert not success(theta, np.zeros(2))
        assert settling_time(theta, np.array([0, 1])) is None
    assert not success(np.array([[np.nan]]), np.zeros(1))


@pytest.mark.parametrize('N,controller,angle', [(1, 'pid', 5), (1, 'lqr', 5), (2, 'lqr', 2), (3, 'lqr', 1), (2, 'mpc', 2), (3, 'mpc', 1)])
def test_reference_plant_recovers_and_stays_upright(N, controller, angle):
    p = SystemParams(N=N, sim_time=10, joint_frictionloss=0)
    r = run_experiment(p, ControllerParams(type=controller), theta_deg=[angle] + [0] * (N - 1))
    absolute = np.rad2deg(np.cumsum(r.theta, axis=0))
    assert np.max(np.abs(absolute[:, -101:])) < 1, 'every segment must stay upright for the last second'
    assert np.max(np.abs(r.x)) < 5
    assert np.max(np.abs(r.u_applied)) <= p.cart_max_force
    assert np.all(np.isfinite(r.states))
    assert r.success


@pytest.mark.parametrize('N', [1, 2, 3, 5, 10, 20])
def test_configurable_chain_and_vertical_equilibrium(N):
    p = SystemParams(N=N, sim_time=0.1, initial_condition='vertical')
    r = run_experiment(p, ControllerParams(type='none'))
    assert r.states.shape == (2 * N + 2, 11)
    np.testing.assert_allclose(r.states, 0, atol=1e-12)


def test_dynamic_impulse_reaches_the_physics_engine():
    p = SystemParams(sim_time=0.2, initial_condition='vertical')
    r = run_experiment(p, ControllerParams(type='none'), perturbations=[PerturbationSpec(time=0.05, force=[10, 0, 0], duration=0.02)])
    np.testing.assert_allclose(r.states[:, :6], 0, atol=1e-12)
    assert abs(r.xdot[-1]) > 0.01


def test_saved_trial_preserves_all_reproduction_parameters(tmp_path):
    r = run_experiment(SystemParams(sim_time=0.1), ControllerParams(type='lqr'), theta_deg=[2], seed=17)
    file = save_result(r, tmp_path)
    loaded = load_result(file)
    assert loaded.params == r.params == json.loads((tmp_path / 'params.json').read_text())
    assert loaded.success == r.success
    np.testing.assert_array_equal(loaded.states, r.states)


def test_realtime_step_uses_interleaved_state_and_actual_time():
    p = SystemParams(N=2)
    model, data = compile_model(2, p)
    sim = Simulator(model, data)
    sim.set_state(np.array([0.1, 0.2, 0.3]), np.array([0.4, 0.5, 0.6]))
    class Spy(ConstantForce):
        def compute(self, state, t):
            self.state, self.t = state, t
            return 0
    ctrl = Spy()
    controller_step(sim, ctrl)
    np.testing.assert_array_equal(ctrl.state, [0.1, 0.4, 0.2, 0.5, 0.3, 0.6])
    controller_step(sim, ctrl)
    assert ctrl.t == pytest.approx(p.ctrl_dt)


@pytest.mark.parametrize('field,value', [('N', 1.5), ('cart_mass', float('nan')), ('joint_damping', -1), ('command_delay_steps', -1), ('ctrl_dt', 0.003), ('sim_time', 0.001), ('explicit_theta_deg', [1, 2])])
def test_invalid_physical_configuration_fails_before_simulation(field, value):
    with pytest.raises(ValueError):
        run_experiment(replace(SystemParams(), **{field: value}), ControllerParams())


@pytest.mark.parametrize('field,value', [('R', 0), ('mpc_horizon', 0), ('Q', [-1, 1, 1, 1]), ('pid_weights', [0])])
def test_invalid_controller_configuration_fails_early(field, value):
    with pytest.raises(ValueError):
        replace(ControllerParams(), **{field: value}).validate()


def test_analytic_design_matches_mujoco_capsule_without_inertia_override():
    from dynamics.linearization import linearize_mujoco
    p = SystemParams(N=3, segment_radius=0.07)
    model, data = compile_model(3, p)
    a, b = make_A_B(p)
    am, bm = linearize_mujoco(model, data)
    np.testing.assert_allclose(a, am, atol=1e-9)
    np.testing.assert_allclose(b, bm, atol=1e-9)


def test_design_includes_armature_and_damping_without_mutating_mujoco_state():
    from dynamics.linearization import linearize_mujoco
    p = SystemParams(N=2, joint_armature=0.03, joint_damping=0.1)
    model, data = compile_model(2, p)
    data.qpos[:] = [0.1, 0.2, 0.3]
    original = data.qpos.copy()
    a, b = make_A_B(p)
    am, bm = linearize_mujoco(model, data)
    np.testing.assert_allclose(a, am, atol=1e-9)
    np.testing.assert_allclose(b, bm, atol=1e-9)
    np.testing.assert_array_equal(data.qpos, original)


def test_realtime_loop_matches_headless_physics(monkeypatch):
    """Exercise the complete realtime loop with only the window substituted."""
    from contextlib import nullcontext
    from visualization import realtime
    p = SystemParams(N=2, sim_time=0.03)
    cp = ControllerParams(type='lqr')
    reference = run_experiment(p, cp, theta_deg=[1, 0])
    captured = []
    class Viewer:
        def __init__(self, model, data):
            self.data = data
            self.calls = 0
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def lock(self):
            return nullcontext()
        def is_running(self):
            self.calls += 1
            return self.calls <= 3
        def sync(self):
            captured.append(self.data.qpos.copy())
    monkeypatch.setattr(realtime.mujoco.viewer, 'launch_passive', Viewer)
    monkeypatch.setattr(realtime.time, 'sleep', lambda _: None)
    realtime.run_realtime(p, cp, theta_deg=1)
    np.testing.assert_allclose(np.array(captured).T, reference.states[0::2, 1:], atol=1e-12)


def test_batch_saves_trials_and_reports_invalid_config(tmp_path):
    from scripts.run_batch import run_batch
    source = tmp_path / 'experiments.yaml'
    source.write_text('experiments:\n  - name: valid\n    system: {sim_time: 0.02, initial_condition: vertical}\n    controller: {type: none}\n  - name: invalid\n    system: {N: 0}\n', encoding='utf-8')
    rows = run_batch(source, tmp_path / 'runs')
    assert rows[0]['status'] == 'completed' and rows[0]['success']
    assert rows[1]['status'] == 'error'
    assert (tmp_path / 'runs/valid/params.json').is_file()
    assert (tmp_path / 'runs/summary.json').is_file()


def test_mass_sweep_keeps_the_nominal_design(monkeypatch):
    from experiments import robustness
    original = robustness.run_experiment
    designs = []
    def capture(*args, **kwargs):
        designs.append(kwargs['design_params'].segment_mass)
        return original(*args, **kwargs)
    monkeypatch.setattr(robustness, 'run_experiment', capture)
    rows = robustness.sweep_parameter(SystemParams(sim_time=0.1), ControllerParams(type='lqr'), 'segment_mass', [0.4, 0.6])
    assert designs == [0.5, 0.5]
    assert [r['segment_mass'] for r in rows] == [0.4, 0.6]
