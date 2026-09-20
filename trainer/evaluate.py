"""Separate finite deterministic evaluation. No trainer or optimizer is created."""
import argparse
import json
from pathlib import Path
import uuid
import yaml

from .contracts import TaskConfig
from .commands import CommandInbox
from .session import digest, atomic_checkpoint
from .storage import atomic_json, experiment_lock, require_compatible


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment', type=Path, required=True)
    parser.add_argument('--player', type=Path, required=True)
    parser.add_argument('--checkpoint', choices=['initial', 'latest', 'best', 'zero', 'random'], default='latest')
    parser.add_argument('--episodes', type=int, default=20)
    parser.add_argument('--base-port', type=int, default=5015)
    parser.add_argument('--visible', action='store_true')
    parser.add_argument('--exact-down', action='store_true')
    parser.add_argument('--interactive', action='store_true')
    parser.add_argument('--capture-dir', type=Path)
    parser.add_argument('--capture-count', type=int, default=60)
    args = parser.parse_args(argv)
    if not 1 <= args.episodes <= 1000 or not 1024 <= args.base_port < 65535:
        parser.error('invalid episode count or local port')
    if args.capture_dir and (not args.visible or not 1 <= args.capture_count <= 300):
        parser.error('capture requires a visible Player and 1..300 frames')
    with experiment_lock(args.experiment):
        result = evaluate(args)
    print(json.dumps(result, ensure_ascii=False))
    return 0


def evaluate(args):
    import numpy as np
    import torch
    from mlagents.trainers.policy.torch_policy import TorchPolicy
    from mlagents.trainers.torch_entities.networks import SimpleActor
    from mlagents.trainers.settings import NetworkSettings
    from mlagents_envs.environment import UnityEnvironment
    from mlagents_envs.base_env import ActionTuple
    from mlagents_envs.side_channel.engine_configuration_channel import EngineConfigurationChannel
    from mlagents_envs.side_channel.stats_side_channel import StatsSideChannel

    directory = args.experiment.resolve()
    task = TaskConfig(**json.loads((directory/'task.json').read_text(encoding='utf-8')))
    require_compatible(directory, task)
    
    # Load network settings from session.yaml (created by desktop train command)
    session_yaml = directory / 'session.yaml'
    if session_yaml.exists():
        session_config = yaml.safe_load(session_yaml.read_text(encoding='utf-8'))
        beh = session_config['behaviors']['StickBalancingN1']
        net_settings = beh['network_settings']
        normalize = net_settings.get('normalize', False)
        hidden_units = net_settings.get('hidden_units', 64)
        num_layers = net_settings.get('num_layers', 2)
    else:
        normalize = False
        hidden_units = 64
        num_layers = 2
    
    evaluation = directory/'evaluations'/uuid.uuid4().hex
    evaluation.mkdir(parents=True)
    episode_log = evaluation/'episodes.jsonl'
    checkpoint = directory/'snapshots'/f'{args.checkpoint}.pt'
    frozen_hash = digest(checkpoint) if args.checkpoint not in ('zero', 'random') else None
    rng = np.random.RandomState(task.seed)
    channel = EngineConfigurationChannel()
    stats = StatsSideChannel()
    channel.set_configuration_parameters(time_scale=1 if args.visible else 20, capture_frame_rate=0,
                                         width=1280 if args.visible else 84, height=720 if args.visible else 84)
    extra = ['--task-config', str(directory/'task.json'), '--episode-log', str(episode_log)]
    if args.exact_down:
        extra += ['--exact-down']
    if args.capture_dir:
        extra += ['--capture-dir', str(args.capture_dir.resolve()), '--capture-count', str(args.capture_count)]
    env = UnityEnvironment(file_name=str(args.player.resolve()), base_port=args.base_port,
                           seed=task.seed, no_graphics=not args.visible, additional_args=extra,
                           side_channels=[channel, stats], log_folder=str(evaluation))
    policy = None
    inbox = CommandInbox()
    stopped = False
    resets = 0
    try:
        env.reset()
        behavior, spec = next(iter(env.behavior_specs.items()))
        if len(env.behavior_specs) != 1 or spec.observation_specs[0].shape != (task.observation_size,):
            raise ValueError('Unexpected worker observation contract')
        if spec.action_spec.continuous_size != 1 or spec.action_spec.discrete_size:
            raise ValueError('Unexpected worker action contract')
        if frozen_hash:
            policy = TorchPolicy(task.seed, spec,
                NetworkSettings(normalize=normalize, hidden_units=hidden_units, num_layers=num_layers, deterministic=True),
                SimpleActor, {'conditional_sigma': False, 'tanh_squash': False})
            state = torch.load(checkpoint, map_location='cpu', weights_only=True)
            policy.actor.load_state_dict(state['Policy'], strict=True)
            policy.actor.eval()
            policy.actor.requires_grad_(False)
            before = {k: v.clone() for k, v in policy.actor.state_dict().items()}
        completed = 0
        # Bound the loop even if a malformed Player stops ending its episodes.
        limit = args.episodes * (int(task.horizon_seconds / task.physics_dt) + 100)
        for _ in range(limit):
            for command in inbox.poll():
                if command in ('stop', 'pause'):
                    stopped = True
                elif command == 'reset' and args.interactive:
                    env.reset()
                    resets += 1
            if stopped:
                break
            decisions, terminal = env.get_steps(behavior)
            completed += len(terminal)
            if completed >= args.episodes:
                break
            if len(decisions):
                if policy:
                    action = policy.get_action(decisions).action
                else:
                    values = (rng.uniform(-1, 1, (len(decisions), 1))
                              if args.checkpoint == 'random' else np.zeros((len(decisions), 1)))
                    action = ActionTuple(continuous=values.astype(np.float32))
                env.set_actions(behavior, action)
            env.step()
            stats.get_and_reset_stats()
        else:
            raise RuntimeError('Worker did not finish the requested finite evaluation')
        if policy and any(not torch.equal(before[k], v) for k, v in policy.actor.state_dict().items()):
            raise RuntimeError('Evaluation changed policy weights')
    finally:
        env.close()
    if frozen_hash and digest(checkpoint) != frozen_hash:
        raise RuntimeError('Evaluation changed the source checkpoint')
    episodes = [json.loads(line) for line in episode_log.read_text(encoding='utf-8').splitlines()] if episode_log.exists() else []
    if len(episodes) < args.episodes and not stopped:
        raise RuntimeError('Missing structured episode records')
    episodes = episodes[:args.episodes]
    report = dict(schema_version=1, checkpoint=args.checkpoint, checkpoint_sha256=frozen_hash,
                  seed=task.seed, reset='exact_down' if args.exact_down else 'seeded_down',
                  successes=sum(e['outcome'] == 'Success' for e in episodes),
                  trials=len(episodes), weights_unchanged=True, episodes=episodes,
                  interactive=args.interactive, physics_resets=resets, stopped_by_user=stopped)
    atomic_json(evaluation/'report.json', report)
    consider_best(directory, evaluation/'report.json')
    return report


def consider_best(directory, report_path):
    """Select only on complete evaluation trials, never on training reward."""
    report = json.loads(Path(report_path).read_text(encoding='utf-8'))
    if (report['checkpoint'] != 'latest' or report.get('interactive', False)
            or report.get('stopped_by_user', False) or report['trials'] < 20
            or not report['weights_unchanged']):
        return
    directory = Path(directory)
    checkpoint = directory/'snapshots/latest.pt'
    if digest(checkpoint) != report['checkpoint_sha256']:
        raise ValueError('Evaluation no longer refers to the current checkpoint')
    metadata = json.loads((directory/'experiment.json').read_text(encoding='utf-8'))
    score = [report['successes']/report['trials'],
             sum(e['held_seconds'] for e in report['episodes'])/report['trials']]
    protocol = dict(seed=report['seed'], reset=report['reset'], trials=report['trials'])
    previous = metadata['checkpoints'].get('best')
    if previous and (previous['protocol'] != protocol or previous['score'] >= score):
        return
    import torch
    atomic_checkpoint(directory/'snapshots/best.pt', torch.load(checkpoint, map_location='cpu', weights_only=True))
    metadata['checkpoints']['best'] = dict(path='snapshots/best.pt', steps=metadata['steps'],
        sha256=digest(directory/'snapshots/best.pt'), score=score, protocol=protocol,
        evaluation=Path(report_path).relative_to(directory).as_posix())
    atomic_json(directory/'experiment.json', metadata)
