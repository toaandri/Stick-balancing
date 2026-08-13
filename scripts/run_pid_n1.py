"""Phase 0 demo: stabilize N=1 cart-pendulum from a 5 deg perturbation with PID.

Runs the MuJoCo simulation headlessly, saves the result and plots.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import load_defaults, load_controller_defaults
from controllers.factory import make_controller
from simulation.mujoco_model import compile_model
from simulation.simulator import Simulator
from visualization.plots import plot_timeseries


def main() -> None:
    parser = argparse.ArgumentParser(description="PID stabilization of N=1 cart-pendulum")
    parser.add_argument("--N", type=int, default=1)
    parser.add_argument("--theta-deg", type=float, default=5.0)
    parser.add_argument("--time", type=float, default=10.0)
    parser.add_argument("--out", type=str, default="results/pid_n1")
    args = parser.parse_args()

    p = load_defaults()
    p.N = args.N
    p.sim_time = args.time
    p.initial_condition = "vertical"

    cp = load_controller_defaults()
    cp.type = "pid"

    model, data = compile_model(p.N, p)
    sim = Simulator(model, data, ctrl_dt=p.ctrl_dt, physics_dt=p.physics_dt)
    controller = make_controller(cp, p.N, u_max=p.cart_max_force)

    theta_deg = np.array([args.theta_deg] + [0.0] * (p.N - 1))
    res = sim.run_headless(controller, p, cp, theta_deg=theta_deg)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    np.savez(
        out / "result.npz",
        t=res.t, x=res.x, xdot=res.xdot, theta=res.theta,
        thetadot=res.thetadot, u=res.u, u_applied=res.u_applied,
        states=res.states,
    )
    fig = plot_timeseries(res, str(out / "timeseries.png"))
    print(f"saved results to {out}")
    print(f"final angle: {np.rad2deg(res.theta[0, -1]):.3f} deg")
    print(f"max |x|: {np.max(np.abs(res.x)):.3f} m")
    print(f"max |u|: {np.max(np.abs(res.u_applied)):.2f} N")


if __name__ == "__main__":
    main()