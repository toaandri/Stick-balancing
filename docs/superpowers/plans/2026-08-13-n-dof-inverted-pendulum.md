# N-DOF Inverted Pendulum Chain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A real experimental control-engineering project: MuJoCo-simulated cart + N-segment inverted pendulum chain stabilized by PID/LQR (MPC optional), with analytics, benchmarks, robustness studies, and an interactive GUI.

**Architecture:** Python generates MJCF for any N, MuJoCo is the physics truth; a recursive Newton–Euler analytical model (validated by sympy on small N and by `mj_computeODE` at equilibrium) supplies A/B for LQR. Controller is decoupled from the simulator.

**Tech Stack:** Python 3.14, mujoco>=3.11, numpy, matplotlib, scipy, sympy, PyYAML, pytest, tkinter (stdlib).

## Global Constraints

- MuJoCo is the source of truth for simulation; no fake Python integrator.
- N is never hard-coded (1, 2, 3, 5, 10 ... 20).
- State ordering for controllers: `[x, xdot, theta1, thetadot1, ..., thetaN, thetadotN]`.
- θ=0 is perfectly vertical. Hinge axes along +y (motion in x-z plane).
- Saturation: controller output and actuator both bounded by ±u_max.
- Everything reproducible via random seed; every run saves `results/<name>/params.json`.
- Code/docstrings/comments/README in English.
- Type hints + docstrings + logging; tests via pytest; separation sim/control/viz.

---
## Phase 0 — Env, config, N=1 model, simulator, PID stabilization

### Task 0.1: Environment setup

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`

- [ ] **Step 1:** Write `requirements.txt` with `mujoco>=3.11,<4`, `pyyaml>=6`, `sympy>=1.12` and `pytest>=8`.
- [ ] **Step 2:** Install: `python -m pip install -r requirements.txt`. Verify `python -c "import mujoco, yaml, sympy"`.
- [ ] **Step 3:** Write `.gitignore` (`__pycache__/`, `models/generated/*.xml`, `results/`, `.pytest_cache/`, `*.mp4`).
- [ ] **Step 4:** Commit.

### Task 0.2: Config system

**Files:**
- Create: `config/__init__.py`, `config/schema.py`, `config/default.yaml`, `config/experiments.yaml`
- Test: `tests/test_config.py`

**Interfaces:**
- `class SystemParams(dataclass)`: cart_mass, cart_friction, cart_max_force, cart_width/height/length, segment_mass, segment_length, segment_radius, joint_damping, joint_frictionloss, joint_armature, segment_inertia (auto), joint_range (tuple|None), uniform_segments (bool), physics_dt, ctrl_dt, sim_time, seed, initial_condition (str|dict), theta_max (deg), noise_sigma, command_delay, start_perturbations (list of dict).
- `class ControllerParams(dataclass)`: type ("none"|"pid"|"lqr"|"mpc"), kp, ki, kd, pid_weights (list|None), Q (list|"auto"), R (float), mpc_horizon, mpc_dt.
- `def load_defaults() -> SystemParams`, `def load_controller_defaults() -> ControllerParams`, `def load_yaml(path) -> dict`, `def from_dict(params_cls, d) -> dataclass`.
- Tests: defaults load, unknown keys rejected, `from_dict` round-trip, seed present.

### Task 0.3: MJCF generator (N=1)

**Files:**
- Create: `simulation/__init__.py`, `simulation/mujoco_model.py`
- Test: `tests/test_model_generation.py`

**Interfaces:**
- `def generate_mjcf(N: int, params: SystemParams) -> str`
- `def compile_model(N: int, params) -> tuple[mujoco.MjModel, mujoco.MjData]`
- `def save_mjcf(xml: str, N: int) -> Path` (to `models/generated/pendulum_N.xml`)
- Properties: `model.nq == N+1`, `model.nv == N+1`, `model.nu == 1`, hinge joint ids 1..N, vertical equilibrium θ=0 (body z up), qpos0 = [0, 0...].
- Test: N=1 model compiles, dims, actuator name "cart_force", joint names `hinge_1`, slider `cart_slide`, qpos0 vertical.

### Task 0.4: Simulator + perturbations

**Files:**
- Create: `simulation/simulator.py`, `simulation/perturbations.py`
- Test: `tests/test_simulator.py`

**Interfaces:**
- `class SimulationResult(dataclass)`: t, x (cart), theta (N,time), u, xdot, thetadot, states (nstates,time), success, params.
- `class Simulator`: `__init__(model, data, ctrl_dt, physics_dt)`, `reset(init_state)`, `set_state(qpos, qvel)`, `get_state() -> np.ndarray (X ordering)`, `apply_impulse(body_name, force_vector, duration)`, `apply_joint_torque(joint_name, torque, duration)`, `step(ctrl) -> None`, `run_headless(controller, duration, noise_sigma=0, callback=None) -> SimulationResult`.
- `simulation/perturbations.py`: `apply_initial_condition(data, params, rng)`, `random_ic(N, theta_max_deg, seed) -> np.ndarray` (θ vector), `make_impulse_schedule(params) -> dict`.
- Test: N=1 free swing under gravity from 30° loses verticality; `get_state` ordering matches X spec; impulse changes velocity; noise changes measurements only.

### Task 0.5: Base controller + PID

**Files:**
- Create: `controllers/__init__.py`, `controllers/base_controller.py`, `controllers/pid.py`
- Test: `tests/test_pid.py`

**Interfaces:**
- `class BaseController(ABC)`: `compute(state: np.ndarray, t: float) -> float`, `reset()`, `saturate(u)`, `params`.
- `class PIDController(BaseController)`: PID on `e = Σ w_i θ_i + w_x x` with per-term gains; anti-windup optional; `reset()` clears integral.
- Test: constant error -> steady output = Kp*e (+ integral after time); saturation clamps to ±u_max.

### Task 0.6: Phase 0 verification

**Files:**
- Create: `tests/test_stability.py`, `scripts/run_pid_n1.py`
- Test: N=1 PID stabilizes from 5° (θ|<0.5° within 10 s and stays); unstable without control.
- `scripts/run_pid_n1.py` runs N=1, saves `results/pid_n1/` + plots (`visualization/plots.py` minimal `plot_timeseries`). Commit.

---
## Phase 1 — General N, analytical model, LQR

### Task 1.1: General-N generator
- Generalize `generate_mjcf` loop over N (already generic); add tests N=2,3,10 (dims, θ=0 equilibrium, qpos0).

### Task 1.2: Recursive analytical dynamics
- `dynamics/recursive_model.py`: `class RecursivePendulumChain`: `__init__(cart_mass, segment_mass, segment_length)`, `mass_matrix(q) -> M (N+1 x N+1)`, `bias(q, qd) -> h (N+1)` (Cq̇+G), `coriolis_and_gravity(q, qd) -> (C_matrix, G)`. Coordinates match MuJoCo qpos/qvel ordering `[x, θ1..θN]`.
- Validation: `test_recursive_vs_mujoco`: at random q, compare M from recursive vs `mj_computeODE` `data.qM` and bias vs `data.qfrc_bias` (tolerance ~1e-6 relative).

### Task 1.3: Symbolic model (sympy)
- `dynamics/symbolic_model.py`: Lagrangian for cart + N pendulums; `symbolic_mass_matrix(N, symbols)`, `symbolic_bias(N)`; `evaluate_symbolic(N, q, qd)` via lambdify.
- Validation: `test_symbolic_vs_recursive` for N=1,2,3 (numeric agreement < 1e-8).

### Task 1.4: Linearization + state space
- `dynamics/linearization.py`: `linearize_around_vertical(recursive_model) -> (A, B, info)` (finite-difference Jacobians of bias & inverse-mass form); `linearize_mujoco(model, data) -> (A, B)` using `mj_computeODE` at q=0; `compare_linearizations(N) -> dict` (max |A_an - A_mj|).
- `dynamics/state_space.py`: `mujoco_to_state(qpos, qvel) -> X`, `state_to_mujoco(X) -> (qpos, qvel)`, `discretize_continuous(A, B, dt) -> (Ad, Bd)` via `scipy.linalg.expm` on augmented matrix.
- Test: A/B dims `(2N+2)x(2N+2)`, `(2N+2)x1`; analytic vs MuJoCo A match < 1e-3 for N=1..3; controllability rank check.

### Task 1.5: LQR controller
- `controllers/lqr.py`: `class LQRController(BaseController)`: built from A,B,Q,R; `K = solve_continuous_are`, `compute(X,t) = saturate(-K @ X)`. Q auto-build: `build_q(N, weights)` block-diagonal.
- Test: N=1 LQR K matches known closed-form solution (`Kx`, `Ktheta`) within 1e-6; closed-loop N=1/3/5 stabilize from 5°.

---
## Phase 2 — Metrics + automated experiments

### Task 2.1: Metrics + comparison
- `analysis/metrics.py`: `rmse`, `mae`, `max_abs`, `settling_time(theta, threshold, tol)`, `max_abs_cart(x)`, `control_effort(u, dt)` (∫u²dt), `control_energy`, `cost_J(states, u, Q, R, dt)`, `success(theta, angle_tol)`.
- `analysis/comparison.py`: `build_table(rows, columns) -> str/pandas DataFrame`, `format_results`.
- Test: known arrays -> known metrics; success flag logic.

### Task 2.2: Experiment runner + benchmark
- `experiments/runner.py`: `run_experiment(name, N, controller_params, system_params, perturbations) -> ExperimentResult`; saves `results/<name>/params.json` + `.npz`; seeds RNG; returns metrics dict.
- `experiments/benchmark.py`: `sweep_n(Ns, ...)`, `compare_controllers(N=3, controllers=[none,pid,lqr])`, `sweep_qr(...)`; prints/table.
- Test: `run_experiment` reproducible given same seed (identical arrays); benchmark runs headless for N in [1,2,3,5,10].

### Task 2.3: Robustness + stability limit + scalability
- `experiments/robustness.py`: sweeps perturbation deg, mass scale, length scale, friction scale, noise σ, delay steps, saturation level, impulse recovery.
- `experiments/stability_limit.py`: `find_critical_angle(N, ...)` bisection (max recoverable initial θ).
- `experiments/scalability.py`: N=1..20 -> (state dim, wall time, settling, cost, success) + plots.

---
## Phase 3 — GUI, visualization, docs

### Task 3.1: Static plots
- `visualization/plots.py`: `plot_timeseries(result)`, `plot_angles_heatmap(result)`, `plot_control_effort(result)`, `plot_comparison(results)`, `plot_stability_limit(df)`; auto-legible large N.

### Task 3.2: Interactive realtime app
- `visualization/realtime.py`: `run_interactive(N, params)` — MuJoCo passive viewer (`launch_passive`) + tkinter panel (Start/Pause/Step/Reset, sliders for gains) + live matplotlib subplots (θ(t), x(t), u(t)); physics loop driven by `viewer.sync()`.
- `scripts/run_gui.py` entry point. Manual smoke test.

### Task 3.3: Optional MPC + dashboard
- `controllers/mpc.py`: linear MPC (discrete model, horizon H, QP via `scipy.optimize.lsq_linear`); guarded import.
- `visualization/dashboard.py`: optional Streamlit runner for batch experiments + video export (mujoco offscreen render -> imageio).

### Task 3.4: Documentation + report
- `README.md`: install, architecture, physics, equations, controllers, usage, experiments, results.
- `docs/report/*.md`: 13-section report skeleton.
- Final validation: N=7, LQR, 5°, 20 s run + plots + metrics table.