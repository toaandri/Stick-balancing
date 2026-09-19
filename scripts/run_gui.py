"""Phase 3 demo: realtime stabilization with a tkinter control panel.

Launches the MuJoCo passive viewer (in a thread) plus a small tkinter window
with pause / speed / step / reset controls and live traces. The simulation loop runs on a
background thread so the viewer and the panel both stay responsive.

Usage:
    python scripts/run_gui.py --N 3 --controller lqr --theta-deg 5.0
"""

from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import load_defaults, load_controller_defaults
from visualization.realtime import ViewerSettings, run_realtime


def main() -> None:
    parser = argparse.ArgumentParser(description="Realtime cart-pendulum control GUI")
    parser.add_argument("--N", type=int, default=1)
    parser.add_argument("--controller", type=str, default="lqr", choices=["none", "pid", "lqr", "mpc"])
    parser.add_argument("--theta-deg", type=float, default=5.0)
    parser.add_argument("--time", type=float, default=30.0)
    args = parser.parse_args()

    p = load_defaults()
    p.N = args.N
    p.sim_time = args.time
    cp = load_controller_defaults()
    cp.type = args.controller
    p.validate()
    cp.validate()

    try:
        import tkinter as tk
    except ImportError:  # pragma: no cover
        print("tkinter not available; running viewer-only")
        run_realtime(p, cp, theta_deg=args.theta_deg)
        return

    settings = ViewerSettings()

    # Tk owns the main thread; the worker owns physics and viewer synchronization.
    errors = []
    def worker():
        try:
            run_realtime(p, cp, theta_deg=args.theta_deg, settings=settings)
        except Exception as exc:
            errors.append(str(exc))
        finally:
            settings.stop()

    thread = threading.Thread(target=worker, daemon=True)
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
    speed_slider = tk.Scale(root, from_=0.1, to=3.0, resolution=0.1, orient="horizontal", command=set_speed)
    speed_slider.set(1.0)
    speed_slider.pack(fill="x", padx=8)

    tk.Button(root, text="Step", command=settings.request_step).pack(fill="x", padx=8, pady=4)
    tk.Button(root, text="Reset", command=settings.request_reset).pack(fill="x", padx=8, pady=4)

    canvas = tk.Canvas(root, width=460, height=220, bg="#101b2e", highlightthickness=0)
    canvas.pack(padx=8, pady=8)

    def poll():
        if not settings.running:
            if errors:
                from tkinter import messagebox
                messagebox.showerror('Simulation error', errors[0])
            root.destroy()
        else:
            with settings._lock:
                history = list(settings.history)
            canvas.delete("all")
            if history:
                canvas.create_text(10, 12, anchor="w", fill="white", text=f"t={history[-1][0]:.2f} s | angle={history[-1][1]:.2f} deg | x={history[-1][2]:.2f} m | u={history[-1][3]:.1f} N")
                for column, label, color in [(1, "max angle [deg]", "#56d9ed"), (2, "cart [m]", "#fbbf24"), (3, "force [N]", "#86efac")]:
                    values = [row[column] for row in history]
                    scale = max(max(abs(v) for v in values), 0.01)
                    y0 = 55 + (column-1)*65
                    canvas.create_text(10, y0-20, anchor="w", fill=color, text=f"{label} (scale +/- {scale:.2f})")
                    points = [coord for i,v in enumerate(values) for coord in (10+440*i/max(1,len(values)-1), y0-v/scale*20)]
                    if len(points) >= 4:
                        canvas.create_line(*points, fill=color)
            btn_pause.config(text="Resume" if settings.paused else "Pause")
            root.after(100, poll)

    root.after(100, poll)

    def on_close():
        settings.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
