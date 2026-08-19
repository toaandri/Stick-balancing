"""Phase 3 dashboard: compare PID / LQR / MPC at the same N and save plots.

Runs each controller from the same initial perturbation, computes the standard
metrics, prints a comparison table, and saves timeseries + comparison plots
under results/dashboard/.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import load_defaults, load_controller_defaults
from experiments import compare_controllers, print_table, run_experiment
from visualization.plots import plot_comparison, plot_timeseries


def main() -> None:
    parser = argparse.ArgumentParser(description="Controller comparison dashboard")
    parser.add_argument("--N", type=int, default=3)
    parser.add_argument("--theta-deg", type=float, default=2.0)
    parser.add_argument("--time", type=float, default=10.0)
    parser.add_argument("--out", type=str, default="results/dashboard")
    args = parser.parse_args()

    p = load_defaults()
    p.N = args.N
    p.sim_time = args.time

    configs = []
    for ctype in ("pid", "lqr", "mpc"):
        cp = load_controller_defaults()
        cp.type = ctype
        configs.append((ctype, cp))

    rows = compare_controllers(p, configs, N=args.N, theta_deg=args.theta_deg)
    print_table(rows)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    results = [
        run_experiment(p, cp, theta_deg=[args.theta_deg] + [0.0] * (args.N - 1))
        for _, cp in configs
    ]
    plot_comparison(results, [name for name, _ in configs], str(out / "comparison.png"))
    for name, res in zip([name for name, _ in configs], results):
        plot_timeseries(res, str(out / f"timeseries_{name}.png"))
    print(f"saved dashboard plots to {out}")


if __name__ == "__main__":
    main()