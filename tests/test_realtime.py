"""Tests for visualization.realtime helpers (Task 3.2)."""

from config import load_defaults, load_controller_defaults
from visualization.realtime import ViewerSettings, _make_controller
from controllers.lqr import LQRController
from controllers.pid import PIDController


def test_viewer_settings_roundtrip():
    s = ViewerSettings()
    assert s.running
    assert not s.paused
    s.toggle_pause()
    assert s.paused
    s.toggle_pause()
    assert not s.paused
    s.set_speed(2.5)
    assert s.speed == 2.5
    s.set_target_angle(3.0)
    assert s.target_theta_deg[0] == 3.0
    s.stop()
    assert not s.running


def test_make_controller_lqr():
    p = load_defaults()
    p.N = 2
    cp = load_controller_defaults()
    cp.type = "lqr"
    assert isinstance(_make_controller(p, cp), LQRController)


def test_make_controller_pid():
    p = load_defaults()
    p.N = 1
    cp = load_controller_defaults()
    cp.type = "pid"
    assert isinstance(_make_controller(p, cp), PIDController)