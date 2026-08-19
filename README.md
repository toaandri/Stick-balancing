# N-DOF Inverted Pendulum on a Cart (MuJoCo)

Physics-driven study of stabilizing a chain of `N` frictionless joints
mounted on a 1-D cart. MuJoCo is the ground-truth physics engine; a recursive
Newton–Euler model (validated to machine precision), a sympy symbolic model,
and analytic linearizations provide the design models used by the controllers.

## Project status

- **Phase 0** ✅ N=1 cart-pendulum with a PID controller.
- **Phase 1** ✅ General-N recursive & symbolic dynamics, analytic + MuJoCo
  linearization, state-space helpers, LQR controller (diagonal `Q`).
- **Phase 2** ✅ Metrics/comparison module, experiment runner, benchmark
  (`sweep_n`, `compare_controllers`, `sweep_qr`), robustness sweeps (initial
  angle, joint friction, measurement noise, command delay), stability-limit
  bisection, scalability timing.
- **Phase 3** ✅ Plotting module, realtime passive-viewer + tkinter control
  panel, MPC controller (finite-horizon LQR via Riccati recursion), comparison
  dashboard, this README + report skeleton.

All 111+ tests pass (`python -m pytest tests/ -q`).

## Installation

```bash
pip install -r requirements.txt
```

Requires Python ≥ 3.10. Tested with Python 3.14, mujoco 3.11.

## Quick start

Run a single N=1 PID stabilization and save plots:

```bash
python scripts/run_pid_n1.py --N 1 --theta-deg 5.0 --time 10.0
```

Compare PID / LQR / MPC at N=2:

```bash
python scripts/run_dashboard.py --N 2 --theta-deg 2.0 --time 10.0
```

Interactive realtime simulation with a control panel (pause, speed, target
angle):

```bash
python scripts/run_gui.py --N 3 --controller lqr --theta-deg 5.0
```

## Model

- `qpos = [x, θ₁ … θ_N]`, `qvel = [ẋ, θ̇₁ … θ̇_N]`; θ = 0 is the unstable
  upright equilibrium (chain vertical, cart at origin).
- `N` identical segments of length `L` hinged at the cart; segment `i`'s world
  axis is `e(θ₁ + … + θ_i)` (absolute/cumulative angles).
- Controller state ordering `X = [x, ẋ, θ₁, θ̇₁, …, θ_N, θ̇_N]`.

## Dynamics (Phase 1)

| Module | What it provides |
| --- | --- |
| `dynamics/recursive_model.py` | Recursive Newton–Euler: `mass_matrix`, `bias`, `gravity`, `inv_dyn`, `kinematics`. Validated vs MuJoCo to ~1e-13 for N = 1,2,3,5,10. |
| `dynamics/symbolic_model.py` | Sympy derivation + lambdified `M`, `h` for N ≤ 3, validated to <1e-10. |
| `dynamics/linearization.py` | Analytic linearization `dX = A X + B u` at the equilibrium (FD Jacobian of the bias), plus `linearize_mujoco` (MuJoCo-consistent, ~1e-13). |
| `dynamics/state_space.py` | `mujoco_to_state` / `state_to_mujoco`, `discretize_continuous`, diagonal `build_lqr_Q`. |

## Controllers

- **PID** (`controllers/pid.py`): per-joint angle errors + cart regulation.
- **LQR** (`controllers/lqr.py`): continuous ARE on the analytic (A, B);
  `Q` is block-diagonal by construction. Note: the ARE becomes ill-conditioned
  for N ≥ 4 (gains ~2e4 at N=5); closed-loop validation therefore runs on the
  *frictionless* design model.
- **MPC** (`controllers/mpc.py`): finite-horizon LQR solved by backward Riccati
  recursion (default horizon 200). Avoids the continuous ARE and remains stable
  for the nonlinear plant at N ≤ 3.

## Experiments (Phase 2)

```python
from config import load_defaults, load_controller_defaults
from experiments import compare_controllers, sweep_qr, bisect_angle, print_table

p = load_defaults(); p.N = 2
cp = load_controller_defaults(); cp.type = "lqr"
rows = compare_controllers(p, [("lqr", cp)], N=2, theta_deg=2.0)
print_table(rows)
critical = bisect_angle(p, cp, lo=0.5, hi=20.0)   # largest stabilizing angle
```

All experiment functions live in `experiments/` and accept `SystemParams` /
`ControllerParams` directly, so they compose with the YAML config
(`config/default.yaml`).

## Repository layout

```
analysis/        metrics + result-table formatting
config/          dataclass schema + YAML loader
controllers/     passive / pid / lqr / mpc + factory
dynamics/        recursive & symbolic models, linearization, state space
experiments/     runner, benchmark, robustness, stability limit, scalability
scripts/         run_pid_n1 / run_dashboard / run_gui demos
simulation/      MuJoCo MJCF generator + headless simulator + perturbations
tests/           pytest suite (one file per module)
visualization/   static plots + realtime passive viewer
docs/report/     final report skeleton
```

## Report

See `docs/report/n-dof-inverted-pendulum.md` for the report structure and the
exact commands that regenerate every figure and table.