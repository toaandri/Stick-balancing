"""Programmatic MJCF model generation for a cart + N-link inverted pendulum chain.

The model is fully generated from configuration: the number of segments N is a
parameter, never hard-coded. MuJoCo is the physics engine; Python only generates
the model, reads state and applies commands.

Coordinate convention
---------------------
* Cart slides along the world +x axis (slide joint).
* Hinge joints rotate around the world +y axis => the chain moves in the x-z plane.
* Joint angle theta = 0 means the segment points straight up (vertical equilibrium).
* qpos = [x, theta_1, ..., theta_N], qvel = [xdot, thetadot_1, ..., thetadot_N].
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import mujoco

from config import SystemParams

MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "generated"


def _segments_nested(N: int, params: SystemParams, z_parent: float) -> str:
    """Build the chain as nested bodies: segment_{i} contains segment_{i+1}."""
    m = params.segment_mass
    L = params.segment_length
    r = params.segment_radius
    lines: list[str] = []
    for i in range(1, N + 1):
        indent = "  " * i
        range_attr = ""
        if params.joint_range_deg:
            lo, hi = params.joint_range_deg
            rad = 3.141592653589793 / 180.0
            range_attr = f' range="{lo * rad:g} {hi * rad:g}"'
        lines.append(
            f'{indent}<body name="segment_{i}" pos="0 0 {z_parent if i == 1 else L:g}">'
        )
        lines.append(
            f'{indent}  <joint name="hinge_{i}" type="hinge" axis="0 1 0"'
            f' damping="{params.joint_damping:g}"'
            f' frictionloss="{params.joint_frictionloss:g}"'
            f' armature="{params.joint_armature:g}"{range_attr}/>'
        )
        lines.append(
            f'{indent}  <geom name="segment_{i}" type="capsule"'
            f' pos="0 0 {L / 2:g}"'
            f' size="{r:g} {L / 2:g}"'
            f' mass="{m:g}"'
            f' rgba="0.15 0.45 0.85 1"/>'
        )
        lines.append(
            f'{indent}  <site name="tip_{i}" pos="0 0 {L:g}" size="0.012"/>'
        )
    # close all bodies (innermost first)
    for i in range(N, 0, -1):
        lines.append("  " * i + "</body>")
    return "\n".join(lines)


def generate_mjcf(N: int, params: SystemParams) -> str:
    """Generate the MJCF XML string for a cart + N-link inverted pendulum chain.

    Args:
        N: number of pendulum segments (>= 1).
        params: physical and numerical parameters.

    Returns:
        Complete MJCF document as a string.
    """
    if N < 1:
        raise ValueError("N must be >= 1")

    cart_h = params.cart_height
    cart_w = params.cart_width
    cart_l = params.cart_length
    rgba_cart = "0.75 0.55 0.2 1"
    m_cart = params.cart_mass

    segments = _segments_nested(N, params, z_parent=cart_h)

    xml = f"""<mujoco model="cart_pendulum_N{N}">
  <compiler angle="radian" autolimits="true"/>
  <option timestep="{params.physics_dt:g}" iterations="50" solver="Newton"/>

  <asset>
    <texture name="grid" type="2d" builtin="checker" rgb1="0.85 0.85 0.85" rgb2="0.75 0.75 0.75"
             width="512" height="512"/>
    <material name="floor" texrepeat="8 8" texuniform="true" reflectance="0.1"/>
  </asset>

  <worldbody>
    <light pos="2 4 6" dir="0 -1 -1" diffuse="0.8 0.8 0.8"/>
    <geom name="floor" type="plane" pos="0 0 0" size="12 6 0.1" material="floor"
          contype="0" conaffinity="0"/>

    <body name="cart" pos="0 0 0">
      <joint name="cart_slide" type="slide" axis="1 0 0"
             damping="{params.cart_friction:g}" frictionloss="{params.cart_friction:g}"/>
      <geom name="cart_geom" type="box" pos="0 0 {cart_h / 2:g}"
            size="{cart_w / 2:g} {cart_l / 2:g} {cart_h / 2:g}"
            mass="{m_cart:g}"
            rgba="{rgba_cart}" contype="0" conaffinity="0"/>
      <site name="cart_top" pos="0 0 {cart_h:g}" size="0.01"/>
{segments}
    </body>
  </worldbody>

  <actuator>
    <motor name="cart_force" joint="cart_slide" gear="1"
           ctrlrange="{-params.cart_max_force:g} {params.cart_max_force:g}"/>
  </actuator>
</mujoco>"""
    return xml


def compile_model(N: int, params: SystemParams) -> Tuple[mujoco.MjModel, mujoco.MjData]:
    """Generate and compile the MJCF into a MuJoCo model/data pair."""
    xml = generate_mjcf(N, params)
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    return model, data


def save_mjcf(xml: str, N: int) -> Path:
    """Write the generated MJCF to models/generated/pendulum_N.xml."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    path = MODEL_DIR / f"pendulum_{N}.xml"
    path.write_text(xml, encoding="utf-8")
    return path