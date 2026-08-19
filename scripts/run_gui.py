"""Phase 3 demo: realtime stabilization with a tkinter control panel.

Launches the MuJoCo passive viewer (in a thread) plus a small tkinter window
with pause / speed / target-angle controls. The simulation loop runs on a
background thread so the viewer and the panel both stay responsive.

Usage:
    python scripts/run_gui.py --N 3 --controller lqr --theta-deg 5.0
"""

from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import load_defaults, load_controller_defaults
from simulation.mujoco_model import compile_model
from visualization.realtime import ViewerSettings, run_realtime


def main() -> None:
    parser = argparse.ArgumentParser(description="Realtime cart-pendulum control GUI")
    parser.add_argument("--N", type=int, default=1)
    parser.add_argument("--controller", type=str, default="lqr", choices=["none", "pid", "lqr"])
    parser.add_argument("--theta-deg", type=float, default=5.0)
    parser.add_argument("--time", type=float, default=30.0)
    args = parser.parse_args()

    p = load_defaults()
    p.N = args.N
    p.sim_time = args.time
    cp = load_controller_defaults()
    cp.type = args.controller

    try:
        import tkinter as tk
    except ImportError:  # pragma: no cover
        print("tkinter not available; running viewer-only")
        run_realtime(p, cp, theta_deg=args.theta_deg)
        return

    model, data = compile_model(p.N, p)
    settings = ViewerSettings()
    settings.target_theta_deg = np.zeros(p.N)

    # run the viewer + sim loop in a background thread (launch_passive blocks)
    thread = threading.Thread(
        target=lambda: run_realtime(p, cp, theta_deg=args.theta_deg, settings=settings),
        daemon=True,
    )
    thread.start()

    root = tk.Tk()
    root.title("Cart-Pendulum Control Panel")

    tk.Label(root, text=f"N = {p.N}  controller = {cp.type}").pack(padx=8, pady=4)

    def toggle_pause():
        settings.toggle_pause()
        btn_pause.config(text="Resume" if settings.paused else "Pause")

    btn_pause = tk.Button(root, text="Pause", command=toggle_pause)
    btn_pause.pack(fill="x", padx=8, pady=4)

    def set_speed(val):
        settings.set_speed(float(val))

    tk.Label(root, text="Simulation speed").pack()
    tk.Scale(root, from_=0.1, to=3.0, resolution=0.1, orient="horizontal",
             command=set_speed).set(1.0)

    def set_angle(val):
        settings.set_target_angle(float(val))

    tk.Label(root, text="Target top angle [deg]").pack()
    tk.Scale(root, from_=-10, to=10, resolution=0.5, orient="horizontal",
             command=set_angle).set(0.0)

    def on_close():
        settings.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()