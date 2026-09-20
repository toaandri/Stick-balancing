"""Tests for trainer/desktop.py — command handling, status mapping, edge cases."""
import json
from contextlib import nullcontext
from dataclasses import asdict
from pathlib import Path

import pytest

from trainer.contracts import TaskConfig
from trainer.storage import atomic_json


def _make_experiment(root):
    """Create a minimal valid experiment directory inside root and return its path."""
    task = TaskConfig()
    directory = root
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'snapshots').mkdir(exist_ok=True)
    (directory / 'checkpoints' / 'training' / 'StickBalancingN1').mkdir(parents=True, exist_ok=True)
    atomic_json(directory / 'experiment.json', {
        'schema_version': 1,
        'id': 'test-id',
        'label': 'Test',
        'origin': 'new',
        'task': asdict(task),
        'compatibility': task.fingerprint(),
        'status': 'ready',
        'steps': 0,
        'checkpoints': {},
    })
    (directory / 'task.json').write_text(json.dumps(asdict(task)), encoding='utf-8')
    (directory / 'ppo.yaml').write_bytes(
        Path(__file__).resolve().parents[2].joinpath('configs/ppo-smoke.yaml').read_bytes()
    )
    (directory / 'trainer.log').write_text('', encoding='utf-8')
    return directory


# ---------------------------------------------------------------------------
# list command
# ---------------------------------------------------------------------------

def test_list_returns_empty_for_missing_data_root(tmp_path):
    import argparse
    from trainer.desktop import command
    args = argparse.Namespace(command='list', data_root=tmp_path / 'missing')
    result = command(args)
    assert result['items'] == []


def test_list_skips_malformed_experiment_json(tmp_path):
    bad = tmp_path / 'deadbeef'
    bad.mkdir()
    (bad / 'experiment.json').write_text('not json', encoding='utf-8')
    import argparse
    from trainer.desktop import command
    args = argparse.Namespace(command='list', data_root=tmp_path)
    result = command(args)
    assert result['items'] == []


def test_list_returns_valid_experiment(tmp_path):
    exp = tmp_path / 'exp-a'
    exp.mkdir()
    data = {'schema_version': 1, 'id': 'aaa', 'label': 'Alpha', 'status': 'ready', 'steps': 0,
            'task': {'segments': 2}}
    (exp / 'experiment.json').write_text(json.dumps(data), encoding='utf-8')
    import argparse
    from trainer.desktop import command
    args = argparse.Namespace(command='list', data_root=tmp_path)
    result = command(args)
    assert len(result['items']) == 1
    assert result['items'][0]['label'] == 'Alpha'
    assert result['items'][0]['segments'] == 2


def test_list_defaults_segments_to_1_when_task_missing(tmp_path):
    exp = tmp_path / 'exp-b'
    exp.mkdir()
    data = {'schema_version': 1, 'id': 'bbb', 'label': 'Beta', 'status': 'ready', 'steps': 0}
    (exp / 'experiment.json').write_text(json.dumps(data), encoding='utf-8')
    import argparse
    from trainer.desktop import command
    args = argparse.Namespace(command='list', data_root=tmp_path)
    result = command(args)
    assert result['items'][0]['segments'] == 1


# ---------------------------------------------------------------------------
# create command — N=2 and N=3
# ---------------------------------------------------------------------------

def test_create_experiment_n2(tmp_path):
    import argparse
    from trainer.desktop import command
    args = argparse.Namespace(
        command='create', data_root=tmp_path,
        label='Double pendule', seed=7, force=80.0, length=0.8, segments=2,
    )
    result = command(args)
    assert result['segments'] == 2
    assert result['status'] == 'ready'
    # experiment.json must record segments=2 in the task.
    import json as _json
    meta = _json.loads((Path(result['path']) / 'experiment.json').read_text(encoding='utf-8'))
    assert meta['task']['segments'] == 2
    # ppo.yaml must use the behavior name StickBalancingN2.
    import yaml
    ppo = yaml.safe_load((Path(result['path']) / 'ppo.yaml').read_text(encoding='utf-8'))
    assert 'StickBalancingN2' in ppo['behaviors']
    assert 'StickBalancingN1' not in ppo['behaviors']


def test_create_experiment_n3(tmp_path):
    import argparse
    from trainer.desktop import command
    args = argparse.Namespace(
        command='create', data_root=tmp_path,
        label='Triple pendule', seed=13, force=120.0, length=0.6, segments=3,
    )
    result = command(args)
    assert result['segments'] == 3
    import yaml
    ppo = yaml.safe_load((Path(result['path']) / 'ppo.yaml').read_text(encoding='utf-8'))
    assert 'StickBalancingN3' in ppo['behaviors']


def test_create_experiment_n1_keeps_original_behavior_name(tmp_path):
    import argparse
    from trainer.desktop import command
    args = argparse.Namespace(
        command='create', data_root=tmp_path,
        label='Simple', seed=42, force=100.0, length=1.0, segments=1,
    )
    result = command(args)
    import yaml
    ppo = yaml.safe_load((Path(result['path']) / 'ppo.yaml').read_text(encoding='utf-8'))
    assert 'StickBalancingN1' in ppo['behaviors']


# ---------------------------------------------------------------------------
# train command — status mapping and empty event stream
# The tests patch session.main (imported as `train` inside desktop.command)
# so that no real ML-Agents or mlagents package is required.
# ---------------------------------------------------------------------------

def _make_train_args(directory, worker_path, steps=512, base_port=5005):
    import argparse
    return argparse.Namespace(
        command='train', experiment=directory, player=worker_path,
        steps=steps, base_port=base_port,
    )


def test_train_status_is_paused_when_last_event_is_paused(tmp_path, monkeypatch):
    from trainer import desktop
    directory = _make_experiment(tmp_path / 'exp')
    worker = tmp_path / 'worker.exe'
    worker.write_bytes(b'\x00')
    paused_line = json.dumps({'schema_version': 1, 'event': 'paused', 'unix_time': 0})

    def fake_train(argv):
        (directory / 'events.jsonl').write_text(paused_line + '\n', encoding='utf-8')

    # `train` is imported at module level in desktop; patch it there.
    monkeypatch.setattr(desktop, 'train', fake_train)
    monkeypatch.setattr(desktop, 'experiment_lock', lambda d: nullcontext())

    result = desktop.command(_make_train_args(directory, worker))
    assert result['status'] == 'paused'


def test_train_status_is_completed_when_last_event_is_completed(tmp_path, monkeypatch):
    from trainer import desktop
    directory = _make_experiment(tmp_path / 'exp')
    worker = tmp_path / 'worker.exe'
    worker.write_bytes(b'\x00')
    completed_line = json.dumps({'schema_version': 1, 'event': 'completed', 'unix_time': 0})

    def fake_train(argv):
        (directory / 'events.jsonl').write_text(completed_line + '\n', encoding='utf-8')

    monkeypatch.setattr(desktop, 'train', fake_train)
    monkeypatch.setattr(desktop, 'experiment_lock', lambda d: nullcontext())

    result = desktop.command(_make_train_args(directory, worker))
    assert result['status'] == 'completed'


def test_train_status_is_error_when_events_jsonl_is_empty(tmp_path, monkeypatch):
    from trainer import desktop
    directory = _make_experiment(tmp_path / 'exp')
    worker = tmp_path / 'worker.exe'
    worker.write_bytes(b'\x00')

    def fake_train(argv):
        (directory / 'events.jsonl').write_text('', encoding='utf-8')

    monkeypatch.setattr(desktop, 'train', fake_train)
    monkeypatch.setattr(desktop, 'experiment_lock', lambda d: nullcontext())

    result = desktop.command(_make_train_args(directory, worker))
    assert result['status'] == 'error'


def test_train_status_is_error_when_events_jsonl_absent(tmp_path, monkeypatch):
    from trainer import desktop
    directory = _make_experiment(tmp_path / 'exp')
    worker = tmp_path / 'worker.exe'
    worker.write_bytes(b'\x00')

    def fake_train(argv):
        pass  # do not write events.jsonl

    monkeypatch.setattr(desktop, 'train', fake_train)
    monkeypatch.setattr(desktop, 'experiment_lock', lambda d: nullcontext())

    result = desktop.command(_make_train_args(directory, worker))
    assert result['status'] == 'error'
