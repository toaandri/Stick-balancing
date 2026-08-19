# N-DOF Inverted Pendulum on a Cart — Report

> Skeleton report. Every section lists the exact command that produces its
> numbers/figures. Fill in the observed values when the project is finished.

## 1. Introduction

Study the stabilization of an N-link inverted-pendulum chain mounted on a
1-D cart. MuJoCo is the ground-truth physics; analytic models (recursive and
symbolic) and linearizations are validated against it. Controllers (PID, LQR,
MPC) are evaluated on stabilization performance, control effort, robustness,
and scalability.

## 2. Model

- Coordinates, equations of motion (recursive Newton–Euler), linearization.
- Validation: `tests/test_recursive_model.py`, `tests/test_linearization.py`.

## 3. Controllers

- PID: per-joint angle + cart regulation (`controllers/pid.py`).
- LQR: continuous ARE, block-diagonal Q (`controllers/lqr.py`).
- MPC: finite-horizon LQR via Riccati recursion (`controllers/mpc.py`).

## 4. Results

### 4.1 Controller comparison

Regenerate:

```bash
python scripts/run_dashboard.py --N 2 --theta-deg 2.0 --time 10.0
```

Expected output: `results/dashboard/comparison.png`,
`results/dashboard/timeseries_{pid,lqr,mpc}.png`, and a metrics table.

### 4.2 Stability limits

Regenerate (PID N=1, from 0.5 to 5 deg):

```bash
python scripts/run_experiments.py   # see "Experiment commands" below
```

Stability-limit bisection example:

```python
from config import load_defaults, load_controller_defaults
from experiments import bisect_angle
p = load_defaults(); p.N = 1
cp = load_controller_defaults(); cp.type = "pid"
critical, iters, _ = bisect_angle(p, cp, lo=0.5, hi=5.0)
```

### 4.3 Robustness

Sweeps over initial angle, joint friction, measurement noise, command delay:

```python
from experiments import sweep_initial_angle, sweep_friction, sweep_noise, sweep_delay
```

### 4.4 Scalability

```python
from experiments import scalability_rows
```

## 5. Conclusions

(To be written.)

## Appendix: experiment commands

| Metric | Command |
| --- | --- |
| Comparison table + plots | `python scripts/run_dashboard.py --N 2 --theta-deg 2.0` |
| Realtime demo | `python scripts/run_gui.py --N 3 --controller lqr` |
| Full test suite | `python -m pytest tests/ -q` |