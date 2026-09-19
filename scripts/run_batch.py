"""Run the experiments YAML, persisting successful trials and explicit failures."""
from pathlib import Path
import argparse
import json
import sys
import re
from dataclasses import asdict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import load_yaml, from_dict, SystemParams, ControllerParams, PerturbationSpec
from experiments import run_experiment, save_result


def run_batch(config, out):
    raw = load_yaml(config)
    if set(raw) != {'experiments'} or not isinstance(raw['experiments'], list):
        raise ValueError('expected an experiments list')
    rows = []
    names = set()
    for item in raw['experiments']:
        name = item.get('name', '')
        if not re.fullmatch(r'[A-Za-z0-9_-]+', name) or name in names:
            raise ValueError('experiment names must be unique and contain only letters, digits, _ or -')
        names.add(name)
        if set(item) - {'name', 'system', 'controller', 'perturbations'}:
            raise ValueError('unknown experiment fields')
        try:
            params = from_dict(SystemParams, item.get('system', {}))
            cp = from_dict(ControllerParams, item.get('controller', {}))
            disturbances = [from_dict(PerturbationSpec, p) for p in item.get('perturbations', [])]
            result = run_experiment(params, cp, perturbations=disturbances)
            save_result(result, Path(out) / name)
            rows.append({'name': name, 'status': 'completed', 'success': result.success})
        except (ValueError, RuntimeError, ArithmeticError) as exc:
            rows.append({'name': name, 'status': 'error', 'error': str(exc)})
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / 'summary.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='config/experiments.yaml')
    parser.add_argument('--out', default='results/batch')
    args = parser.parse_args()
    rows = run_batch(args.config, args.out)
    print(json.dumps(rows, indent=2))
    return int(any(r['status'] == 'error' for r in rows))


if __name__ == '__main__':
    raise SystemExit(main())
