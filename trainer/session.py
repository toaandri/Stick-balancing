"""Pinned ML-Agents 1.1 adapter: full snapshots, strict resume, JSONL, safe stop.

One process per session. Internal API integration is deliberate and version checked.
The structured event stream is separate from the trainer's diagnostic stdout.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import threading
import time

from .storage import atomic_json
from .commands import CommandInbox


def atomic_checkpoint(path, state):
    import torch
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix='.pt.tmp')
    try:
        with os.fdopen(fd, 'wb') as stream:
            torch.save(state, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv=None):
    from importlib.metadata import version
    if version('mlagents') != '1.1.0':
        raise RuntimeError('This adapter requires ML-Agents 1.1.0')
    import torch
    from mlagents.trainers import learn
    from mlagents.trainers.model_saver.torch_model_saver import TorchModelSaver
    from mlagents.trainers.trainer import rl_trainer
    from mlagents.trainers.stats import StatsWriter, StatsReporter

    options = learn.parse_command_line(argv)
    experiment = Path(options.checkpoint_settings.results_dir).resolve().parent
    metadata_path = experiment / 'experiment.json'
    stop = threading.Event()
    write_lock = threading.Lock()
    inbox = CommandInbox()

    def emit(event, **data):
        record = dict(schema_version=1, event=event, unix_time=time.time(), **data)
        with write_lock, (experiment/'events.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, allow_nan=False) + '\n')

    class StructuredStats(StatsWriter):
        def write_stats(self, category, values, step):
            metrics = {key: float(value.aggregated_value) for key, value in values.items()
                       if value.num and math.isfinite(float(value.aggregated_value))}
            emit('metrics', behavior=category, steps=int(step), values=metrics,
                 reward=metrics.get('Environment/Cumulative Reward'),
                 reward_available='Environment/Cumulative Reward' in metrics,
                 elevation=metrics.get('Reward/Elevation'))

    class SafeSaver(TorchModelSaver):
        def save_checkpoint(self, behavior_name, step):
            state = {name: module.state_dict() for name, module in self.modules.items()}
            base = Path(self.model_path)/f'{behavior_name}-{step}'
            atomic_checkpoint(base.with_suffix('.pt'), state)
            checkpoint = Path(self.model_path)/'checkpoint.pt'
            if checkpoint.exists():
                atomic_checkpoint(Path(self.model_path)/'previous.pt',
                                  torch.load(checkpoint, map_location='cpu', weights_only=True))
            atomic_checkpoint(checkpoint, state)
            atomic_checkpoint(experiment/'snapshots/latest.pt', state)
            self.export(str(base), behavior_name)
            metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
            metadata['steps'] = int(step)
            metadata['checkpoints']['latest'] = {
                'path': 'snapshots/latest.pt', 'steps': int(step),
                'sha256': digest(experiment/'snapshots/latest.pt')}
            atomic_json(metadata_path, metadata)
            emit('checkpoint', kind='latest', steps=int(step))
            return str(base.with_suffix('.onnx')), [str(base.with_suffix('.pt'))]

        def _load_model(self, load_path, policy=None, reset_global_steps=False):
            state = torch.load(load_path, map_location='cpu', weights_only=True)
            modules = self.modules if policy is None else policy.get_modules()
            if not set(modules).issubset(state):
                raise ValueError('Incomplete checkpoint: policy or optimizer is missing')
            for name, module in modules.items():
                if isinstance(module, torch.nn.Module):
                    module.load_state_dict(state[name], strict=True)
                else:
                    module.load_state_dict(state[name])
            if reset_global_steps:
                (policy or self.policy).set_step(0)

    class ControlledTrainer(learn.TrainerController):
        def _reset_env(self, env_manager):
            super()._reset_env(env_manager)
            initial = experiment/'snapshots/initial.pt'
            for trainer in self.trainers.values():
                if trainer.threaded:
                    raise ValueError('Cooperative checkpoints require threaded=false')
                if not initial.exists():
                    if trainer.get_step != 0:
                        raise ValueError('Initial checkpoint is missing on resume')
                    state = {k: v.state_dict() for k, v in trainer.model_saver.modules.items()}
                    atomic_checkpoint(initial, state)
                    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
                    metadata['checkpoints']['initial'] = {
                        'path': 'snapshots/initial.pt', 'steps': 0, 'sha256': digest(initial)}
                    atomic_json(metadata_path, metadata)
                    emit('checkpoint', kind='initial', steps=0)
            emit('training', steps=max(t.get_step() for t in self.trainers.values()))

        def advance(self, env_manager):
            try:
                for command in inbox.poll():
                    if command in ('pause', 'stop'):
                        stop.set()
                        emit('stopping', reason=command)
                    else:
                        emit('command_error', message='Reset is only available during an interactive test')
            except ValueError as error:
                emit('command_error', message=str(error))
            if stop.is_set():
                raise KeyboardInterrupt
            return super().advance(env_manager)

    # A resumed session receives an additional budget, not the exhausted old target.
    if options.checkpoint_settings.resume:
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
        for settings in options.behaviors.values():
            settings.max_steps += int(metadata['steps'])
    for settings in options.behaviors.values():
        settings.threaded = False
    StatsReporter.add_writer(StructuredStats())
    rl_trainer.TorchModelSaver = SafeSaver
    learn.TrainerController = ControlledTrainer
    emit('starting', resume=options.checkpoint_settings.resume)
    debug_stream = None
    if os.environ.get('STICK_DEBUG_STACKS') == '1':
        import faulthandler
        debug_stream = (experiment/'thread-stacks.log').open('w')
        faulthandler.dump_traceback_later(15, file=debug_stream)
    try:
        learn.run_training(options.env_settings.seed, options, 1)
    except Exception as error:
        emit('error', message=str(error), type=type(error).__name__)
        raise
    finally:
        if debug_stream is not None:
            faulthandler.cancel_dump_traceback_later()
            debug_stream.close()
    emit('paused' if stop.is_set() else 'completed')
    return 0
