"""Regenerate all report figures/tables (Phase 3, Task 3.4).

Runs the standard benchmark, robustness sweeps, stability-limit bisection and
scalability study, saving tables + plots under results/report/. Runtime is on
the order of a minute.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import load_defaults, load_controller_defaults
from experiments import (
    compare_controllers,
    sweep_initial_angle,
    sweep_friction,
    sweep_noise,
    sweep_delay,
    bisect_angle,
    scalability_rows,
    print_table,
)
from visualization.plots import (
    plot_comparison,
    plot_stability_limit,
    plot_timeseries,
)
from experiments import run_experiment


def main() -> None:
    out = Path("results/report")
    out.mkdir(parents=True, exist_ok=True)

    # ---- 1. Controller comparison (N=1, 2 deg) ----
    p = load_defaults()
    p.N = 1
    p.sim_time = 8.0
    configs = []
    for ctype in ("pid", "lqr", "mpc"):
        cp = load_controller_defaults()
        cp.type = ctype
        configs.append((ctype, cp))
    rows = compare_controllers(p, configs, N=1, theta_deg=2.0)
    with open(out / "comparison_table.txt", "w", encoding="utf-8") as fh:
        fh.write(print_table(rows))
    results = [run_experiment(p, cp, theta_deg=[2.0]) for _, cp in configs]
    plot_comparison(results, [n for n, _ in configs], str(out / "comparison.png"))

    # ---- 2. Stability limit (LQR N=3) ----
    p3 = load_defaults()
    p3.N = 3
    p3.sim_time = 8.0
    cp_lqr = load_controller_defaults()
    cp_lqr.type = "lqr"
    critical, iters, _ = bisect_angle(p3, cp_lqr, lo=0.5, hi=25.0, tol=0.1)
    with open(out / "stability_limit.txt", "w", encoding="utf-8") as fh:
        fh.write(f"LQR N=3 critical angle: {critical:.3f} deg ({iters} iterations)\n")
    angles = [1.0, 4.0, 8.0, 12.0, 16.0, 20.0, 25.0]
    sweep = sweep_initial_angle(p3, cp_lqr, angles_deg=angles, N=3)
    plot_stability_limit(
        angles, [bool(r["success"]) for r in sweep], str(out / "stability_limit.png")
    )

    # ---- 3. Robustness sweeps (PID N=1) ----
    cp_pid = load_controller_defaults()
    cp_pid.type = "pid"
    with open(out / "robustness.txt", "w", encoding="utf-8") as fh:
        fh.write("== initial angle ==\n")
        fh.write(print_table(sweep) + "\n\n")
        fh.write("== joint friction ==\n")
        fh.write(
            print_table(
                sweep_friction(p, cp_pid, [0.0, 0.01, 0.05, 0.1], N=1, theta_deg=2.0)
            )
            + "\n\n"
        )
        fh.write("== measurement noise ==\n")
        fh.write(
            print_table(
                sweep_noise(p, cp_pid, [0.0, 0.1, 0.5], N=1, theta_deg=2.0, seeds=(0, 1))
            )
            + "\n\n"
        )
        fh.write("== command delay ==\n")
        fh.write(
            print_table(
                sweep_delay(p, cp_pid, [0, 1, 5], N=1, theta_deg=2.0)
            )
            + "\n"
        )

    # ---- 4. Scalability (LQR) ----
    scal = scalability_rows(p, cp_lqr, Ns=[1, 2, 3, 5], theta_deg=1.0)
    with open(out / "scalability.txt", "w", encoding="utf-8") as fh:
        fh.write(print_table(scal))

    print("report artifacts written to results/report/")


if __name__ == "__main__":
    main()