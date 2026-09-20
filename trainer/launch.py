"""Developer-only launcher for the finite phase-0 training experiment.

No runtime download, shell command interpolation or global process termination.
Training must be explicitly requested; --check never trains.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys

from .contracts import TaskConfig
from .storage import atomic_json, create_experiment, experiment_lock, require_compatible

ROOT = Path(__file__).resolve().parents[1]


def training_command(runtime, player, config, experiment, resume=False, base_port=5005):
    if not 1024 <= base_port <= 65534:
        raise ValueError('invalid local communication port')
    command = [str(Path(runtime).resolve()), '-I', str(ROOT/'trainer/bootstrap.py'),
               str(Path(config).resolve()), '--env', str(Path(player).resolve()),
               '--run-id', 'training', '--results-dir', str(Path(experiment).resolve() / 'checkpoints'),
               '--base-port', str(base_port), '--no-graphics',
               '--env-args', '--task-config', str(Path(experiment).resolve() / 'task.json'),
               '--episode-log', str(Path(experiment).resolve() / 'episodes.jsonl')]
    # --env-args consumes the remaining tokens; trainer flags go before it.
    if resume:
        command.insert(command.index('--env-args'), '--resume')
    return command


def check(runtime, player):
    errors = []
    if not Path(player).is_file():
        errors.append('Unity worker Player is not built')
    if not Path(runtime).is_file():
        errors.append('private Python runtime is missing')
    else:
        probe = subprocess.run([str(Path(runtime).resolve()), '-I', '-c',
            'import sys,importlib.metadata as m,json; import torch,mlagents.trainers.learn; print(json.dumps({"python":sys.version_info[:3],"mlagents":m.version("mlagents"),"mlagents-envs":m.version("mlagents-envs"),"torch":m.version("torch"),"numpy":m.version("numpy")}))'],
            capture_output=True, text=True, timeout=30, shell=False)
        if probe.returncode:
            errors.append('private runtime dependencies are incomplete: ' + probe.stderr.strip())
        else:
            versions = json.loads(probe.stdout)
            expected = {'python': [3, 10, 11], 'mlagents': '1.1.0', 'mlagents-envs': '1.1.0', 'torch': '2.1.1+cpu', 'numpy': '1.23.5'}
            if versions != expected:
                errors.append(f'private runtime differs from candidate toolchain: {versions}')
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, default=ROOT/'trainer/runtime/python.exe')
    parser.add_argument('--player', type=Path, default=ROOT/'builds/windows/worker/StickBalancingWorker.exe')
    parser.add_argument('--data-root', type=Path)
    parser.add_argument('--resume', type=Path)
    parser.add_argument('--base-port', type=int, default=5005)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--train', action='store_true')
    args = parser.parse_args(argv)
    errors = check(args.runtime, args.player)
    if errors or args.check or not args.train:
        print(json.dumps({'schema_version': 1, 'ready': not errors, 'errors': errors}, ensure_ascii=False, indent=2))
        return int(bool(errors))
    if not args.data_root and not args.resume:
        parser.error('--data-root is required for a new developer experiment')
    task = TaskConfig()
    if args.resume:
        directory = args.resume.resolve()
        task = TaskConfig(**json.loads((directory/'task.json').read_text(encoding='utf-8')))
        require_compatible(directory, task)
        if not list((directory/'checkpoints').rglob('*.pt')):
            raise ValueError('no training checkpoint; ONNX alone cannot resume training')
    else:
        directory = create_experiment(args.data_root, task)
        atomic_json(directory/'task.json', asdict(task))
    with experiment_lock(directory):
        metadata = require_compatible(directory, task)
        metadata['status'] = 'starting'
        atomic_json(directory/'experiment.json', metadata)
        with (directory/'trainer.log').open('a', encoding='utf-8') as log:
            result = subprocess.run(training_command(args.runtime, args.player, ROOT/'configs/ppo-smoke.yaml', directory, bool(args.resume), args.base_port),
                                    stdin=sys.stdin, stdout=log, stderr=subprocess.STDOUT, cwd=directory, shell=False)
        metadata = require_compatible(directory, task)
        metadata['status'] = 'completed' if result.returncode == 0 else 'error'
        events = directory/'events.jsonl'
        if result.returncode == 0 and events.exists():
            lines = [line.strip() for line in events.read_text(encoding='utf-8').splitlines() if line.strip()]
            if lines:
                try:
                    last_event = json.loads(lines[-1])
                except ValueError:
                    metadata['status'] = 'error'
                else:
                    if last_event.get('event') == 'paused':
                        metadata['status'] = 'paused'
        metadata['trainer_exit_code'] = result.returncode
        atomic_json(directory/'experiment.json', metadata)
        print(json.dumps({'schema_version': 1, 'event': 'trainer_exited', 'experiment': str(directory), 'exit_code': result.returncode}))
        return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
