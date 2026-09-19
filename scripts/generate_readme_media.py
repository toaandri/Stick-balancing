"""Regenerate README GIFs from real MuJoCo trajectories (no OpenGL needed)."""
from pathlib import Path
import json
import platform
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.patches import Rectangle
import numpy as np
import mujoco

from config import SystemParams, ControllerParams
from experiments import run_experiment, save_result
from analysis import summarize
from controllers.lqr import LQRController


def animate(results, labels, path):
    fig, axes = plt.subplots(1, len(results), figsize=(9.6, 4.2), squeeze=False)
    fig.patch.set_facecolor('#101b2e')
    artists = []
    for ax, res, label in zip(axes[0], results, labels):
        N = res.theta.shape[0]
        ax.set_facecolor('#101b2e')
        ax.set(xlim=(-2.2, 2.2), ylim=(-N-0.3, N+0.6), aspect='equal')
        ax.set_title(label, color='white', fontsize=12, pad=12)
        ax.axhline(0, color='#62728c', lw=2)
        ax.set_xticks([-2, 0, 2]); ax.tick_params(colors='#cbd5e1')
        ax.set_xlabel('x [m]', color='#cbd5e1')
        for spine in ax.spines.values():
            spine.set_visible(False)
        line, = ax.plot([], [], '-o', color='#56d9ed', lw=4, markersize=6)
        cart = Rectangle((-.2, 0), .4, .2, color='#fbbf24')
        ax.add_patch(cart)
        text = ax.text(.03, .03, '', transform=ax.transAxes, color='white', fontsize=9)
        artists.append((line, cart, text))
    fig.suptitle('MuJoCo trajectories | frictionless reference | 1x speed', color='white', fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, .91))
    fps = 15
    frames = np.linspace(0, len(results[0].t)-1, int(results[0].t[-1]*fps)+1, dtype=int)
    def update(i):
        for res, (line, cart, text) in zip(results, artists):
            phi = np.cumsum(res.theta[:, i])
            length = res.params['system']['segment_length']
            xs = np.r_[res.x[i], res.x[i] + np.cumsum(length*np.sin(phi))]
            zs = np.r_[.2, .2 + np.cumsum(length*np.cos(phi))]
            line.set_data(xs, zs)
            cart.set_x(res.x[i]-.2)
            text.set_text(f't = {res.t[i]:.2f} s | max angle = {np.max(np.abs(np.rad2deg(phi))):.1f} deg\nforce = {res.u_applied[i]:+.1f} N')
        return []
    animation = FuncAnimation(fig, update, frames=frames, interval=1000/fps, blit=False)
    animation.save(path, writer=PillowWriter(fps=fps), dpi=80)
    plt.close(fig)


def main():
    out = Path(__file__).resolve().parents[1] / 'docs' / 'assets'
    out.mkdir(parents=True, exist_ok=True)
    manifest = {'python': platform.python_version(), 'mujoco': mujoco.__version__, 'numpy': np.__version__, 'scenarios': {}}
    for filename, N, angle, types in [('control-comparison.gif', 1, 5, ['none', 'pid', 'lqr']), ('chain-n3.gif', 3, 1, ['lqr', 'mpc'])]:
        results = []
        for ctype in types:
            p = SystemParams(N=N, sim_time=6, joint_frictionloss=0, seed=42)
            cp = ControllerParams(type=ctype)
            res = run_experiment(p, cp, theta_deg=[angle] + [0]*(N-1))
            results.append(res)
            name = f'N{N}-{ctype}'
            save_result(res, Path('results/readme') / name)
            metrics = summarize(res, p.ctrl_dt, LQRController._build_q(cp, N), np.array([[cp.R]]))
            metrics = {k: v if not isinstance(v, float) or np.isfinite(v) else None for k,v in metrics.items()}
            manifest['scenarios'][name] = {'params': res.params, 'metrics': metrics}
        animate(results, [f'N={N} | {t.upper()}' for t in types], out / filename)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding='utf-8')
    print(f'GIFs and manifest written to {out}')


if __name__ == '__main__':
    main()
