"""Configuration dataclasses and YAML loading helpers.

All physical parameters are configurable here and validated against a
whitelist of known fields so typos fail loudly instead of silently
changing behaviour.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Optional

import yaml
import numpy as np

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent


@dataclass
class SystemParams:
    """Physical and numerical parameters of the cart + chain system."""

    # Cart
    cart_mass: float = 2.0
    cart_width: float = 0.4
    cart_height: float = 0.2
    cart_length: float = 0.5
    cart_friction: float = 0.0
    cart_max_force: float = 100.0

    # Segments (applied uniformly unless overridden)
    N: int = 1
    segment_mass: float = 0.5
    segment_length: float = 1.0
    segment_radius: float = 0.03
    joint_damping: float = 0.0
    joint_frictionloss: float = 0.0
    joint_armature: float = 0.0
    joint_range_deg: Optional[list] = None

    # Simulation
    physics_dt: float = 0.002
    ctrl_dt: float = 0.01
    sim_time: float = 20.0
    seed: int = 42

    # Initial condition
    initial_condition: str = "random"  # "vertical" | "small" | "random"
    theta_max_deg: float = 5.0
    explicit_theta_deg: Optional[list] = None

    # Measurement / actuation realism
    noise_sigma: float = 0.0
    command_delay_steps: int = 0

    @property
    def n_state(self) -> int:
        return 2 * self.N + 2

    def validate(self) -> None:
        for name in ('N', 'seed', 'command_delay_steps'):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < (1 if name == 'N' else 0):
                raise ValueError(f'{name} must be an integer in its valid range')
        for name in ('cart_mass', 'cart_width', 'cart_height', 'cart_length',
                     'cart_max_force', 'segment_mass', 'segment_length',
                     'segment_radius', 'physics_dt', 'ctrl_dt', 'sim_time'):
            if not np.isfinite(getattr(self, name)) or getattr(self, name) <= 0:
                raise ValueError(f'{name} must be finite and positive')
        for name in ('cart_friction', 'joint_damping', 'joint_frictionloss',
                     'joint_armature', 'noise_sigma', 'theta_max_deg'):
            if not np.isfinite(getattr(self, name)) or getattr(self, name) < 0:
                raise ValueError(f'{name} must be finite and nonnegative')
        for a, b in ((self.ctrl_dt, self.physics_dt), (self.sim_time, self.ctrl_dt)):
            if not np.isclose(a / b, round(a / b), rtol=0, atol=1e-8):
                raise ValueError('ctrl_dt / physics_dt and sim_time / ctrl_dt must be integers')
        if self.explicit_theta_deg is not None:
            v = np.asarray(self.explicit_theta_deg, dtype=float)
            if v.shape != (self.N,) or not np.all(np.isfinite(v)):
                raise ValueError('explicit_theta_deg must contain N finite angles')
        if self.joint_range_deg is not None:
            v = np.asarray(self.joint_range_deg, dtype=float)
            if v.shape != (2,) or not np.all(np.isfinite(v)) or not v[0] < v[1]:
                raise ValueError('joint_range_deg must be [lower, upper]')
        if self.N < 1:
            raise ValueError("N must be >= 1")
        if self.segment_length <= 0 or self.cart_mass <= 0 or self.segment_mass <= 0:
            raise ValueError("masses and lengths must be positive")
        if self.cart_max_force <= 0:
            raise ValueError("cart_max_force must be positive")
        if self.initial_condition not in ("vertical", "small", "random"):
            raise ValueError(
                f"unknown initial_condition {self.initial_condition!r}"
            )
        if self.physics_dt <= 0 or self.ctrl_dt <= 0 or self.sim_time <= 0:
            raise ValueError("durations must be positive")
        if self.ctrl_dt < self.physics_dt:
            raise ValueError("ctrl_dt must be >= physics_dt")


@dataclass
class ControllerParams:
    """Controller selection and tuning."""

    type: str = "pid"  # "none" | "pid" | "lqr" | "mpc"

    # PID: separate gains for angle and cart regulation
    kp: float = 80.0
    ki: float = 4.0
    kd: float = 40.0
    pid_weights: Optional[list] = None  # per-joint angle weights; default all 1/N
    kp_cart: float = 3.0
    kd_cart: float = 8.0

    # LQR
    Q: Optional[list] = None  # diagonal weights for X = [x,xd,th1,th1d,...]
    R: float = 0.1
    q_pos: float = 10.0
    q_vel: float = 1.0
    q_angle: float = 100.0
    q_angle_vel: float = 1.0

    # MPC (optional)
    mpc_horizon: int = 200
    mpc_dt: float = 0.02

    def validate(self) -> None:
        if self.type not in ("none", "pid", "lqr", "mpc"):
            raise ValueError(f"unknown controller type {self.type!r}")
        for name in ('kp', 'ki', 'kd', 'kp_cart', 'kd_cart', 'q_pos', 'q_vel', 'q_angle', 'q_angle_vel', 'R', 'mpc_dt'):
            value = getattr(self, name)
            if not np.isfinite(value) or value < 0 or (name in ('R', 'mpc_dt') and value == 0):
                raise ValueError(f'invalid {name}')
        if isinstance(self.mpc_horizon, bool) or not isinstance(self.mpc_horizon, int) or self.mpc_horizon < 1:
            raise ValueError('mpc_horizon must be a positive integer')
        if self.pid_weights is not None:
            w = np.asarray(self.pid_weights, dtype=float)
            if w.ndim != 1 or not np.all(np.isfinite(w)) or np.isclose(w.sum(), 0):
                raise ValueError('pid_weights must be finite with nonzero sum')
        if self.Q is not None:
            q = np.asarray(self.Q, dtype=float)
            if q.ndim == 1:
                q = np.diag(q)
            if q.ndim != 2 or q.shape[0] != q.shape[1] or not np.all(np.isfinite(q)) or not np.allclose(q, q.T) or np.min(np.linalg.eigvalsh(q)) < -1e-10:
                raise ValueError('Q must be symmetric positive semidefinite')


@dataclass
class PerturbationSpec:
    """Dynamic perturbation: an impulse or torque applied at a given time."""

    kind: str = "impulse"  # "impulse" | "torque"
    body: str = "cart"  # "cart" | "segment_i"
    force: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    torque: float = 0.0
    time: float = 2.0
    duration: float = 0.1

    def validate(self) -> None:
        if self.kind not in ('impulse', 'torque'):
            raise ValueError('unknown perturbation kind')
        f = np.asarray(self.force, dtype=float)
        if f.shape != (3,) or not np.all(np.isfinite(f)):
            raise ValueError('force must contain three finite components')
        if not np.isfinite(self.time) or self.time < 0 or not np.isfinite(self.duration) or self.duration <= 0 or not np.isfinite(self.torque):
            raise ValueError('invalid perturbation time, duration or torque')


def load_yaml(path: Path | str) -> dict:
    """Load a YAML file into a plain dict."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError('configuration must be a YAML mapping')
    return data


def from_dict(cls: type, data: dict) -> Any:
    """Build a dataclass from a dict, rejecting unknown fields."""
    if not isinstance(data, dict):
        raise ValueError(f'{cls.__name__} configuration must be a mapping')
    known = {f.name for f in fields(cls)}
    unknown = set(data) - known
    if unknown:
        raise ValueError(f"unknown fields for {cls.__name__}: {sorted(unknown)}")
    return cls(**{k: v for k, v in data.items() if k in known})


def load_defaults(path: Path | str | None = None) -> SystemParams:
    """Load system parameters from YAML, falling back to dataclass defaults."""
    path = Path(path) if path else CONFIG_DIR / "default.yaml"
    raw = load_yaml(path)
    params = from_dict(SystemParams, raw.get("system", {}))
    params.validate()
    return params


def load_controller_defaults(path: Path | str | None = None) -> ControllerParams:
    """Load controller parameters from YAML, falling back to defaults."""
    path = Path(path) if path else CONFIG_DIR / "default.yaml"
    raw = load_yaml(path)
    params = from_dict(ControllerParams, raw.get("controller", {}))
    params.validate()
    return params
