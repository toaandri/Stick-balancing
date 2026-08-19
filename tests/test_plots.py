"""Tests for visualization.plots (Task 3.1)."""

import numpy as np
import pytest

from config import load_defaults, load_controller_defaults
from experiments import run_experiment
from simulation.simulator import SimulationResult
from visualization.plots import (
    plot_timeseries,
    plot_angles_heatmap,
    plot_control_effort,
    plot_comparison,
    plot_stability_limit,
)


@pytest.fixture
def n3_result():
    p = load_defaults()
    p.N = 3
    p.sim_time = 2.0
    cp = load_controller_defaults()
    cp.type = "lqr"
    return run_experiment(p, cp, theta_deg=[1.0, 0.0, 0.0])


def test_plot_timeseries_saves(n3_result, tmp_path):
    out = tmp_path / "ts.png"
    fig = plot_timeseries(n3_result, str(out))
    assert out.exists()
    assert fig is not None
    import matplotlib.pyplot as plt

    plt.close(fig)


def test_plot_angles_heatmap_saves(n3_result, tmp_path):
    out = tmp_path / "hm.png"
    fig = plot_angles_heatmap(n3_result, str(out))
    assert out.exists()
    import matplotlib.pyplot as plt

    plt.close(fig)


def test_plot_control_effort_saves(n3_result, tmp_path):
    out = tmp_path / "ce.png"
    fig = plot_control_effort(n3_result, str(out))
    assert out.exists()
    import matplotlib.pyplot as plt

    plt.close(fig)


def test_plot_comparison_saves(n3_result, tmp_path):
    out = tmp_path / "cmp.png"
    fig = plot_comparison([n3_result, n3_result], ["a", "b"], str(out))
    assert out.exists()
    import matplotlib.pyplot as plt

    plt.close(fig)


def test_plot_stability_limit_saves(tmp_path):
    out = tmp_path / "sl.png"
    fig = plot_stability_limit([0.5, 1.0, 2.0, 5.0], [True, True, False, False], str(out))
    assert out.exists()
    import matplotlib.pyplot as plt

    plt.close(fig)


def test_plot_timeseries_handles_large_n():
    # synthetic result, no physics needed
    N, steps = 10, 50
    t = np.linspace(0, 5, steps)
    theta = np.linspace(0.1, 0.0, steps)[None, :] + 0.01 * np.arange(N)[:, None]
    res = SimulationResult(
        t=t,
        x=np.zeros(steps),
        xdot=np.zeros(steps),
        theta=theta,
        thetadot=np.zeros((N, steps)),
        u=np.zeros(steps),
        u_applied=np.zeros(steps),
        states=np.zeros((2 * N + 2, steps)),
    )
    fig = plot_timeseries(res)
    import matplotlib.pyplot as plt

    plt.close(fig)