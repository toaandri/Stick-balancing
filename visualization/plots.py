"""Static (publication-style) plots for simulation results."""

from __future__ import annotations

from typing import Sequence

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


def plot_angles_heatmap(res: SimulationResult, path: str | None = None) -> plt.Figure:
    """Angle of every joint vs time as a heatmap (works for any N)."""
    fig, ax = plt.subplots(figsize=(10, 6))
    ang = _deg(res.theta)
    im = ax.imshow(
        ang,
        aspect="auto",
        extent=[res.t[0], res.t[-1], 0.5, ang.shape[0] + 0.5],
        origin="lower",
        cmap="RdBu_r",
        vmin=-np.max(np.abs(ang)),
        vmax=np.max(np.abs(ang)),
    )
    ax.set_xlabel("time [s]")
    ax.set_ylabel("joint index")
    fig.colorbar(im, ax=ax, label="angle [deg]")
    fig.suptitle(f"N={ang.shape[0]} joint-angle heatmap")
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=120)
    return fig


def plot_control_effort(res: SimulationResult, path: str | None = None) -> plt.Figure:
    """Cumulative control energy int|u|dt and the instantaneous force."""
    dt = float(np.diff(res.t)[0]) if len(res.t) > 1 else 0.01
    cum = np.cumsum(np.abs(res.u_applied)) * dt
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    axes[0].plot(res.t, res.u_applied, label="u")
    axes[0].axhline(0, color="k", lw=0.5)
    axes[0].set_ylabel("force [N]")
    axes[0].legend(loc="best", fontsize=8)
    axes[1].plot(res.t, cum, label="energy")
    axes[1].set_xlabel("time [s]")
    axes[1].set_ylabel("$\\int |u| dt$ [N s]")
    axes[1].legend(loc="best", fontsize=8)
    fig.suptitle(f"N={res.theta.shape[0]} control effort")
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=120)
    return fig


def plot_comparison(
    results: Sequence[SimulationResult],
    labels: Sequence[str],
    path: str | None = None,
) -> plt.Figure:
    """Weighted-mean angle over time for several runs (controller comparison)."""
    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    for res, label in zip(results, labels):
        mean = np.mean(res.theta, axis=0)
        axes[0].plot(res.t, _deg(mean), label=label)
        axes[1].plot(res.t, res.u_applied, label=label, lw=0.8)
    axes[0].set_ylabel("mean angle [deg]")
    axes[0].legend(loc="best", fontsize=8)
    axes[1].set_xlabel("time [s]")
    axes[1].set_ylabel("force [N]")
    axes[1].legend(loc="best", fontsize=8)
    fig.suptitle("controller comparison")
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=120)
    return fig


def plot_stability_limit(
    angles_deg: Sequence[float],
    successes: Sequence[bool],
    path: str | None = None,
) -> plt.Figure:
    """Stabilization success vs initial angle (step plot)."""
    angles = np.asarray(angles_deg)
    succ = np.asarray(successes, dtype=float)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.step(angles, succ, where="post", lw=2)
    ax.set_xlabel("initial angle [deg]")
    ax.set_ylabel("success")
    ax.set_ylim(-0.05, 1.05)
    ax.set_yticks([0, 1])
    ax.set_title("stability limit")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=120)
    return fig