"""Application commands for Unity; stdout contains one JSON response only."""
import argparse
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import asdict
import json
from pathlib import Path
import sys
import yaml

from .contracts import TaskConfig
from .launch import training_command
from .session import main as train
from .storage import atomic_json, create_experiment, require_compatible, experiment_lock

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['list', 'create', 'train'])
    parser.add_argument('--data-root', type=Path)
    parser.add_argument('--experiment', type=Path)
    parser.add_argument('--player', type=Path)
    parser.add_argument('--label', default='Pendule N=1')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--force', type=float, default=100)
    parser.add_argument('--length', type=float, default=1)
    parser.add_argument('--segments', type=int, default=1, choices=[1, 2, 3])
    parser.add_argument('--steps', type=int, default=2048)
    parser.add_argument('--base-port', type=int, default=5005)
    args = parser.parse_args(argv)
    try:
        result = command(args)
        print(json.dumps(dict(schema_version=1, ok=True, **result), ensure_ascii=False))
        return 0
    except Exception as error:
        print(json.dumps(dict(schema_version=1, ok=False, error=str(error)), ensure_ascii=False))
        return 1


def command(args):
    if args.command == 'list':
        if args.data_root is None:
            raise ValueError('Data directory required')
        items = []
        for path in sorted(args.data_root.glob('*/experiment.json'), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                task_data = data.get('task', {})
                segments = int(task_data.get('segments', 1))
                items.append(dict(id=data['id'], label=data.get('label', data['id'][:8]),
                                  path=str(path.parent.resolve()), status=data['status'],
                                  steps=data['steps'], segments=segments))
            except (ValueError, KeyError, OSError):
                continue
        return dict(items=items)
    if args.command == 'create':
        if args.data_root is None:
            raise ValueError('Data directory required')
        task = TaskConfig(seed=args.seed, force_limit=args.force, segment_length=args.length,
                          segments=args.segments)
        task.validate()
        directory = create_experiment(args.data_root, task)
        atomic_json(directory/'task.json', asdict(task))
        metadata = require_compatible(directory, task)
        metadata['label'] = args.label[:80]
        metadata['versions'] = json.loads((ROOT/'configs/toolchain.json').read_text(encoding='utf-8'))
        atomic_json(directory/'experiment.json', metadata)
        # Choose ppo config matching the behavior name for this N.
        behavior_name = f'StickBalancingN{args.segments}'
        ppo_src = ROOT/'configs/ppo-smoke.yaml'
        ppo_config = yaml.safe_load(ppo_src.read_text(encoding='utf-8'))
        if 'StickBalancingN1' in ppo_config['behaviors'] and behavior_name != 'StickBalancingN1':
            ppo_config['behaviors'][behavior_name] = ppo_config['behaviors'].pop('StickBalancingN1')
        (directory/'ppo.yaml').write_text(yaml.safe_dump(ppo_config), encoding='utf-8')
        return dict(path=str(directory), id=metadata['id'], label=metadata['label'],
                    steps=0, status='ready', segments=args.segments)
    if args.experiment is None or args.player is None or not args.player.is_file():
        raise ValueError('Experiment and built worker are required')
    if not 256 <= args.steps <= 10_000_000 or not 1024 <= args.base_port <= 65534:
        raise ValueError('Invalid training budget or local port')
    directory = args.experiment.resolve()
    task = TaskConfig(**json.loads((directory/'task.json').read_text(encoding='utf-8')))
    behavior_name = f'StickBalancingN{task.segments}'
    with experiment_lock(directory):
        metadata = require_compatible(directory, task)
        config = yaml.safe_load((directory/'ppo.yaml').read_text(encoding='utf-8'))
        # Support both legacy 'StickBalancingN1' key and dynamic behavior names.
        if behavior_name not in config['behaviors']:
            old_key = next(iter(config['behaviors']))
            config['behaviors'][behavior_name] = config['behaviors'].pop(old_key)
        config['behaviors'][behavior_name]['max_steps'] = args.steps
        config['env_settings']['seed'] = task.seed
        (directory/'session.yaml').write_text(yaml.safe_dump(config), encoding='utf-8')
        resume = (directory/f'checkpoints/training/{behavior_name}/checkpoint.pt').is_file()
        if metadata['steps'] > 0 and not resume:
            raise ValueError('Checkpoint missing; cannot silently restart an existing agent')
        metadata['status'] = 'starting'
        atomic_json(directory/'experiment.json', metadata)
        try:
            with (directory/'trainer.log').open('a', encoding='utf-8') as log, redirect_stdout(log), redirect_stderr(log):
                command_line = training_command(sys.executable, args.player, directory/'session.yaml',
                                                directory, resume, args.base_port)
                train(command_line[3:])
            metadata = require_compatible(directory, task)
            events_path = directory / 'events.jsonl'
            last_event = None
            if events_path.exists():
                lines = [l.strip() for l in events_path.read_text(encoding='utf-8').splitlines() if l.strip()]
                if lines:
                    try:
                        last_event = json.loads(lines[-1]).get('event')
                    except ValueError:
                        last_event = None
            # Map raw event names to valid status values.
            _event_to_status = {'paused': 'paused', 'completed': 'completed'}
            metadata['status'] = _event_to_status.get(last_event, 'error' if last_event is None else 'completed')
        except Exception:
            metadata = require_compatible(directory, task)
            metadata['status'] = 'error'
            raise
        finally:
            atomic_json(directory/'experiment.json', metadata)
        return dict(path=str(directory), steps=metadata['steps'], status=metadata['status'],
                    segments=task.segments)
