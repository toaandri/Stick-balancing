"""Tests for MJCF model generation (Phase 0, Task 1.1 general-N)."""

import numpy as np
import mujoco
import pytest

from config import load_defaults
from simulation.mujoco_model import generate_mjcf, compile_model


def test_generate_n1_compiles():
    params = load_defaults()
    params.N = 1
    xml = generate_mjcf(1, params)
    model = mujoco.MjModel.from_xml_string(xml)
    assert model.nq == 2
    assert model.nv == 2
    assert model.nu == 1


def test_compile_n1_structure():
    params = load_defaults()
    params.N = 1
    model, data = compile_model(1, params)
    assert data.qpos.shape[0] == 2
    assert data.qvel.shape[0] == 2
    names = [
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, i)
        for i in range(model.njnt)
    ]
    assert names == ["cart_slide", "hinge_1"]
    body_names = [
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)
        for i in range(model.nbody)
    ]
    assert body_names == ["world", "cart", "segment_1"]
    act_names = [
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i)
        for i in range(model.nu)
    ]
    assert act_names == ["cart_force"]


def test_vertical_equilibrium():
    params = load_defaults()
    params.N = 1
    model, data = compile_model(1, params)
    # qpos0 = [0, 0] -> cart at origin, pendulum perfectly vertical
    assert np.allclose(data.qpos, 0.0)
    mujoco.mj_forward(model, data)
    # At the exact unstable equilibrium with zero velocity, no acceleration.
    assert np.allclose(data.qacc, 0.0, atol=1e-6)


def test_masses_configurable():
    params = load_defaults()
    params.N = 1
    params.cart_mass = 3.0
    params.segment_mass = 0.7
    model, _ = compile_model(1, params)
    assert abs(model.body_mass[1] - 3.0) < 1e-9
    assert abs(model.body_mass[2] - 0.7) < 1e-9


def test_angle_sign_positive_toward_positive_x():
    """Positive hinge angle must tilt the segment toward +x."""
    params = load_defaults()
    params.N = 1
    model, data = compile_model(1, params)
    data.qpos[1] = 0.5  # 0.5 rad
    mujoco.mj_forward(model, data)
    tip = data.site_xpos[1]
    assert tip[0] > 0.0  # tilted toward +x
    assert tip[2] > 0.0  # still above the base


@pytest.mark.parametrize("N", [2, 3, 10])
def test_generate_n_general_structure(N):
    params = load_defaults()
    params.N = N
    model, data = compile_model(N, params)
    assert model.nq == N + 1
    assert model.nv == N + 1
    assert model.nu == 1
    assert model.nbody == N + 2
    assert model.njnt == N + 1
    assert data.qpos.shape[0] == N + 1
    assert data.qvel.shape[0] == N + 1
    joint_names = [
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, i)
        for i in range(model.njnt)
    ]
    assert joint_names == ["cart_slide"] + [f"hinge_{i}" for i in range(1, N + 1)]
    body_names = [
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)
        for i in range(model.nbody)
    ]
    assert body_names == ["world", "cart"] + [f"segment_{i}" for i in range(1, N + 1)]


@pytest.mark.parametrize("N", [2, 3, 10])
def test_vertical_equilibrium_general(N):
    params = load_defaults()
    params.N = N
    model, data = compile_model(N, params)
    assert np.allclose(data.qpos, 0.0)  # cart at origin, chain perfectly vertical
    mujoco.mj_forward(model, data)
    # Exact unstable equilibrium: zero acceleration with zero velocity.
    assert np.allclose(data.qacc, 0.0, atol=1e-6)


@pytest.mark.parametrize("N", [2, 3, 10])
def test_chain_vertical_geometry(N):
    params = load_defaults()
    params.N = N
    model, data = compile_model(N, params)
    mujoco.mj_forward(model, data)
    tip = data.site_xpos[model.nsite - 1]
    assert np.allclose(tip[:2], 0.0, atol=1e-9)
    assert np.allclose(tip[2], params.cart_height + N * params.segment_length, atol=1e-9)