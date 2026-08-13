"""Static (publication-style) plots for simulation results."""

from __future__ import annotations

import numpy as np
import matplotlib

matplotlib.use("Agg")  # headless-safe default; interactive apps override
import matplotlib.pyplot as plt

from simulation.simulator import SimulationResult


def _deg(a):
    return np.rad2deg(a)


def plot_timeseries(res: SimulationResult, path: str | None = None) -> plt.Figure:
    """Angles, cart motion and control force vs time for one run.

    For large N the angles are drawn as a colormapped heatmap instead of N
    overlapping lines to stay readable.
    """
    N = res.theta.shape[0]
    fig, axes = plt.subplots(3, 1, figsize=(10, 10), sharex=True)

    if N <= 6:
        for i in range(N):
            axes[0].plot(res.t, _deg(res.theta[i]), label=f"$\\theta_{i+1}$")
        axes[0].set_ylabel("angle [deg]")
        axes[0].legend(loc="best", fontsize=8)
    else:
        im = axes[0].imshow(
            _deg(res.theta),
            aspect="auto",
            extent=[res.t[0], res.t[-1], 0.5, N + 0.5],
            origin="lower",
            cmap="RdBu_r",
            vmin=-np.max(np.abs(_deg(res.theta))),
            vmax=np.max(np.abs(_deg(res.theta))),
        )
        axes[0].set_ylabel("joint index")
        fig.colorbar(im, ax=axes[0], label="angle [deg]")

    axes[1].plot(res.t, res.x, label="x")
    axes[1].plot(res.t, res.xdot, label="$\\dot x$")
    axes[1].set_ylabel("cart [m] / [m/s]")
    axes[1].legend(loc="best", fontsize=8)

    axes[2].plot(res.t, res.u_applied, label="u")
    axes[2].axhline(0, color="k", lw=0.5)
    axes[2].set_xlabel("time [s]")
    axes[2].set_ylabel("force [N]")
    axes[2].legend(loc="best", fontsize=8)

    fig.suptitle(f"N={N} controller={res.params.get('controller')}")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    if path:
        fig.savefig(path, dpi=120)
    return fig