"""Python contract tests ONLY: these do not execute Unity or prove RL learning."""
from dataclasses import asdict, replace
import json
import math
from pathlib import Path

import pytest

from trainer.contracts import TaskConfig, SuccessMonitor
from trainer.storage import atomic_json, create_experiment, experiment_lock, require_compatible
from trainer.launch import training_command, check


def test_full_rotation_requires_five_consecutive_seconds():
    monitor = SuccessMonitor(TaskConfig())
    for _ in range(2499):
        assert monitor.step(0, [2*math.pi], [0]) is None
    assert monitor.step(0, [0], [0]) == 'success'


def test_hold_resets_on_speed_or_tilt():
    monitor = SuccessMonitor(TaskConfig())
    for _ in range(100):
        monitor.step(0, [0], [0])
    assert monitor.held > 0
    assert monitor.step(0, [0], [1]) is None
    assert monitor.held == 0
    monitor.step(0, [math.pi], [0])
    assert monitor.held == 0


@pytest.mark.parametrize('angles,speeds', [([.5, -.5], [0, 0]), ([0, 0], [.3, .3])])
def test_all_absolute_angles_and_speeds_are_checked(angles, speeds):
    monitor = SuccessMonitor(TaskConfig(segments=2))
    monitor.step(0, angles, speeds)
    assert monitor.held == 0


@pytest.mark.parametrize('x,angles,expected', [(2.5, [0], 'rail_exit'), (0, [math.nan], 'physics_error')])
def test_failure_reason_is_explicit(x, angles, expected):
    monitor = SuccessMonitor(TaskConfig())
    assert monitor.step(x, angles, [0]) == expected
    with pytest.raises(RuntimeError):
        monitor.step(x, angles, [0])


def test_down_is_allowed_until_time_limit():
    monitor = SuccessMonitor(TaskConfig(physics_dt=.01, horizon_seconds=.1, hold_seconds=.05))
    for _ in range(9):
        assert monitor.step(0, [math.pi], [0]) is None
    assert monitor.step(0, [math.pi], [0]) == 'time_limit'


def test_new_experiments_have_independent_empty_histories(tmp_path):
    a = create_experiment(tmp_path, TaskConfig())
    b = create_experiment(tmp_path, TaskConfig())
    assert a != b
    metadata = require_compatible(a, TaskConfig())
    assert metadata['origin'] == 'new' and metadata['steps'] == 0
    assert metadata['checkpoints'] == {}
    with pytest.raises(ValueError):
        require_compatible(a, TaskConfig(segments=2))


def test_atomic_metadata_keeps_previous_and_rejects_nan(tmp_path):
    path = tmp_path/'experiment.json'
    atomic_json(path, {'steps': 0})
    atomic_json(path, {'steps': 100})
    with pytest.raises(ValueError):
        atomic_json(path, {'steps': math.nan})
    assert json.loads(path.read_text())['steps'] == 100
    assert json.loads(path.with_suffix('.json.previous').read_text())['steps'] == 0


def test_exclusive_training_lock(tmp_path):
    with experiment_lock(tmp_path):
        with pytest.raises(FileExistsError):
            with experiment_lock(tmp_path):
                pytest.fail('second trainer acquired same experiment')
    assert not (tmp_path/'trainer.lock').exists()


def test_launcher_preserves_argument_boundaries_for_spaces_and_accents(tmp_path):
    root = tmp_path/'ExpÃ©rience avec espaces & symboles'
    cmd = training_command(root/'python.exe', root/'worker.exe', root/'config.yaml', root, resume=True)
    assert cmd[0] == str((root/'python.exe').resolve())
    assert cmd[cmd.index('--env')+1] == str((root/'worker.exe').resolve())
    assert cmd.index('--resume') < cmd.index('--env-args')
    assert '--force' not in cmd
    assert '--initialize-from' not in cmd


def test_missing_tools_are_reported_without_simulating_training(tmp_path):
    errors = check(tmp_path/'python.exe', tmp_path/'worker.exe')
    assert len(errors) == 2


def test_launcher_handles_empty_event_stream_without_crashing(tmp_path, monkeypatch):
    from contextlib import nullcontext
    from trainer import launch

    task = TaskConfig()
    directory = tmp_path / 'experience'
    directory.mkdir()
    (directory / 'experiment.json').write_text(json.dumps({
        'schema_version': 1,
        'id': 'exp-1',
        'origin': 'new',
        'task': asdict(task),
        'compatibility': task.fingerprint(),
        'status': 'ready',
        'steps': 0,
        'checkpoints': {},
    }), encoding='utf-8')
    (directory / 'task.json').write_text(json.dumps(asdict(task)), encoding='utf-8')
    (directory / 'events.jsonl').write_text('', encoding='utf-8')
    (directory / 'trainer.log').write_text('', encoding='utf-8')

    monkeypatch.setattr(launch, 'check', lambda runtime, player: [])
    monkeypatch.setattr(launch, 'create_experiment', lambda root, task_obj: directory)
    monkeypatch.setattr(launch, 'experiment_lock', lambda _directory: nullcontext())
    monkeypatch.setattr(launch.subprocess, 'run', lambda *args, **kwargs: type('Result', (), {'returncode': 0})())

    rc = launch.main(['--train', '--data-root', str(tmp_path), '--runtime', str(tmp_path / 'python.exe'), '--player', str(tmp_path / 'worker.exe')])
    assert rc == 0


@pytest.mark.parametrize('changes', [{'segments': 0}, {'segments': 4}, {'physics_dt': math.nan}, {'decision_steps': 1.5}, {'rail_half_length': -1}])
def test_invalid_task_is_rejected(changes):
    with pytest.raises(ValueError):
        replace(TaskConfig(), **changes).validate()


def test_unity_assets_have_stable_metadata():
    root = Path(__file__).resolve().parents[2]/'unity/Assets'
    for path in root.rglob('*'):
        if path.suffix != '.meta':
            assert Path(str(path)+'.meta').is_file(), path


