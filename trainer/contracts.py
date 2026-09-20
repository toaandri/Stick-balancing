"""Versioned scientific contract, testable without Unity or a training runtime.

This module does not integrate physics or train a policy.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
import math


@dataclass(frozen=True)
class TaskConfig:
    schema_version: int = 1
    segments: int = 1
    cart_mass: float = 2.0
    segment_mass: float = 0.5
    segment_length: float = 1.0
    force_limit: float = 100.0
    rail_half_length: float = 2.5
    physics_dt: float = 0.002
    decision_steps: int = 5
    horizon_seconds: float = 30.0
    hold_seconds: float = 5.0
    angle_tolerance_deg: float = 10.0
    speed_tolerance: float = 0.5
    seed: int = 42

    def validate(self):
        if self.schema_version != 1:
            raise ValueError('unsupported task schema')
        for key, low, high in [('segments', 1, 3), ('decision_steps', 1, 100), ('seed', 0, 2**31-1)]:
            value = getattr(self, key)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f'invalid {key}')
        for key, value in asdict(self).items():
            if key not in ('schema_version', 'segments', 'decision_steps', 'seed'):
                if not math.isfinite(value) or value <= 0:
                    raise ValueError(f'{key} must be finite and positive')
        if self.hold_seconds >= self.horizon_seconds or self.angle_tolerance_deg >= 90:
            raise ValueError('invalid success window')

    @property
    def observation_size(self):
        return 2 + 3 * self.segments

    def fingerprint(self):
        self.validate()
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class SuccessMonitor:
    """Periodic absolute orientations, absolute speeds, consecutive hold time."""
    def __init__(self, config):
        config.validate()
        self.config = config
        self.reset()

    def reset(self):
        self.held = 0.0
        self.elapsed = 0.0
        self.finished = None

    def step(self, cart, relative_angles, relative_speeds):
        if self.finished:
            raise RuntimeError('episode is already finished')
        c = self.config
        if len(relative_angles) != c.segments or len(relative_speeds) != c.segments:
            raise ValueError('state dimension mismatch')
        if not all(math.isfinite(v) for v in [cart, *relative_angles, *relative_speeds]):
            self.finished = 'physics_error'
            return self.finished
        self.elapsed += c.physics_dt
        angle = speed = 0.0
        upright = True
        for q, qd in zip(relative_angles, relative_speeds):
            angle += q
            speed += qd
            error = math.atan2(math.sin(angle), math.cos(angle))
            upright &= abs(error) < math.radians(c.angle_tolerance_deg) and abs(speed) < c.speed_tolerance
        if abs(cart) >= c.rail_half_length:
            self.finished = 'rail_exit'
        else:
            self.held = self.held + c.physics_dt if upright else 0.0
            if self.held + 1e-12 >= c.hold_seconds:
                self.finished = 'success'
            elif self.elapsed + 1e-12 >= c.horizon_seconds:
                self.finished = 'time_limit'
        return self.finished
