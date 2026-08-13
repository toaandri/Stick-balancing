# Design Spec — N-DOF Inverted Pendulum Chain on a Cart (MuJoCo + LQR)

Date: 2026-08-13

## 1. Purpose

Build a real experimental control-engineering project: a horizontal cart carrying a
chain of N rigid segments (inverted pendulum chain), simulated in the **MuJoCo**
physics engine (the physical source of truth), stabilized by PID / LQR (MPC optional),
with analytics, benchmarks, robustness studies and an interactive GUI.

Python only generates the model, reads the physics state, computes control commands,
and post-processes results. All dynamics/forces/contacts are computed by MuJoCo.

## 2. Scope / non-goals

- MuJoCo is the truth for simulation; no fake Python integrator replaces it.
- The analytical model is a **design tool** for controllers, compared against MuJoCo
  (section 8/25 of the project brief).
- N must be configurable (1, 2, 3, 5, 10, ... 20), never hard-coded.
- MPC is an optional, guarded extension; LQR is the reference controller.

## 3. Architecture

Package root = repository root `D:\Ecole\Stick-balancing`.

```
config/            dataclasses + YAML loaders (default.yaml, experiments.yaml)
simulation/        mujoco_model.py, simulator.py, perturbations.py
dynamics/          recursive_model.py, symbolic_model.py, linearization.py, state_space.py
controllers/       base_controller.py, pid.py, lqr.py, mpc.py
experiments/       runner.py, benchmark.py, robustness.py, stability_limit.py, scalability.py
analysis/          metrics.py, comparison.py
visualization/     plots.py, realtime.py, dashboard.py
models/generated/  cached MJCF files
results/           per-experiment outputs + params.json
tests/             pytest suite
docs/              spec + plan + report skeleton
```

### Data flow

```
Parameters -> N-DOF MJCF generator -> MuJoCo (engine) -> state -> controller -> u
              ^                                                          |
              +---------------------- MuJoCo step <---------------------+
state -> raw data -> {plots, metrics} -> comparison -> final analysis
```

## 4. Physics model (MJCF)

Generated in `simulation/mujoco_model.py:generate_mjcf(N, params) -> str`.

- World: ground at z=0. Cart on a `slide` joint along +x with a `force` actuator
  (`ctrlrange=±u_max`).
- Segments: N `hinge` joints, axis along +y (motion in the x-z plane). Joint angle
  `θ=0` ⇔ segment points straight up (vertical equilibrium, matches spec θ=0).
- Geometry: capsule segments, body CM at z=L/2 in body frame; mass/inertia explicit.
- Joint `damping`, `frictionloss`, `armature` and optional `range` limits from config.
- MuJoCo ordering: `qpos=[x, θ1..θN]`, `qvel=[ẋ, θ̇1..θ̇N]`.

## 5. State & measurement

- Controller state (spec ordering): `X = [x, ẋ, θ1, θ̇1, ..., θN, θ̇N]`.
  Mapping helpers live in `dynamics/state_space.py` (qpos/qvel -> X and back).
- `simulation/simulator.py`: owns MjModel/MjData; steps physics at substep resolution,
  control loop at 100 Hz; supports headless mode; noise injection (Gaussian σ on
  measured angles/velocities); external impulses via `data.xfrc_applied` (bodies) and
  `data.qfrc_applied` (joint torques).
- `simulation/perturbations.py`: IC presets (perfect vertical, explicit vector,
  random within ±θmax, seeded) and scheduled dynamic perturbations.

## 6. Analytical dynamics (two approaches, compared)

- `dynamics/recursive_model.py`: general-N recursive Newton–Euler (numpy, O(n))
  producing M(q), h(q,q̇)=C(q,q̇)q̇+G(q). Workhorse for any N.
- `dynamics/symbolic_model.py`: sympy Lagrangian derivation (cart + N pendulums),
  used for report equations and to validate the recursive model on N=1..3.
- `dynamics/linearization.py`: linearizes around q=0,q̇=0:
  - analytic: from the recursive model,
  - physics: via MuJoCo `mj_computeODE` (fills `data.qM`, `data.qfrc_bias`),
  - produces continuous `ẋ = Ax + Bu`, cross-checked (section 25), controllability check.
- `dynamics/state_space.py`: ordering + exact discretization (`scipy.linalg.expm`).

## 7. Controllers

- `controllers/base_controller.py`: abstract `compute(state, t) -> u`, `reset()`,
  saturation helper.
- `controllers/pid.py`: PID on θ1 for N=1; for N>1 on a weighted combination of
  angles plus cart terms (weights configurable).
- `controllers/lqr.py`: LQR via continuous Riccati (`scipy.linalg.solve_continuous_are`),
  `u = -Kx`, saturation, configurable block-diagonal Q and R.
- `controllers/mpc.py`: optional linear MPC (finite horizon QP via scipy), guarded.

## 8. Experiments & analysis

- `experiments/runner.py`: one reproducible run -> `SimulationResult`.
- `experiments/benchmark.py`: N sweep (1..10); no-control/PID/LQR at N=3; Q/R influence.
- `experiments/robustness.py`: perturbation, mass/length variation, friction, noise σ,
  command delay, saturation, external impulses.
- `experiments/stability_limit.py`: θ_critical per N (bisection on initial angle).
- `experiments/scalability.py`: N=1..20 (state dim, compute time, settling, cost).
- `analysis/metrics.py`: RMSE/MAE/max|θ|, settling time, max|x|, ∫u²dt, cost J, success.
- `analysis/comparison.py`: result tables.

## 9. Visualization / GUI

- `visualization/realtime.py`: MuJoCo native passive viewer (`launch_passive`) + tkinter
  control panel (params, Start/Pause/Step/Reset, speed) + live matplotlib panels.
- `visualization/plots.py`: static report plots; angle heatmap for large N.
- `visualization/dashboard.py`: optional Streamlit dashboard + video export.

## 10. Config & reproducibility

- `config/default.yaml`, `config/experiments.yaml`, validated dataclasses.
- Every run saves `results/<name>/params.json` (N, controller, Q, R, u_max, ICs, seed,
  duration). Same seed -> same experiment.

## 11. Testing (pytest)

Model generation N=1/2/10 (dims, vertical equilibrium), state mapping, A/B dimensions,
LQR gain vs known N=1 solution, saturation, angle readback, recursive vs MuJoCo M(q)
match, symbolic vs recursive N=1..3, closed-loop N=1 LQR stability, seed reproducibility.

## 12. Delivery phases

- **Phase 0** env + config + N=1 MuJoCo model + simulator + PID stabilization end-to-end.
- **Phase 1** general-N generator + recursive/symbolic dynamics + linearization + LQR
  + MuJoCo-numeric comparison.
- **Phase 2** metrics + runner + benchmark/robustness/stability/scalability experiments.
- **Phase 3** interactive viewer + tkinter panel + live plots (+ optional MPC/dashboard),
  README + report skeleton.

## 13. Risks

- MuJoCo wheel availability on Python 3.14/Windows (fallback: 3.12 venv).
- Native viewer needs OpenGL; headless paths are tested independently.
- Symbolic derivation intractable for large N -> recursive numeric model is the LQR
  workhorse; sympy only for small N validation and report equations.