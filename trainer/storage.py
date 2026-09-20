"""Per-experiment identity, compatibility and atomic metadata writes."""
from dataclasses import asdict
from pathlib import Path
from contextlib import contextmanager
import json
import os
import shutil
import tempfile
import uuid

from .contracts import TaskConfig


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
    fd, temporary = tempfile.mkstemp(prefix=path.name, suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            # Preserve a complete prior metadata file before replacing the current one.
            backup = path.with_suffix(path.suffix + '.previous')
            shutil.copyfile(path, backup)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def create_experiment(root, config: TaskConfig):
    config.validate()
    experiment_id = uuid.uuid4().hex
    directory = Path(root).resolve() / experiment_id
    directory.mkdir(parents=True, exist_ok=False)
    atomic_json(directory / 'experiment.json', {
        'schema_version': 1, 'id': experiment_id, 'origin': 'new',
        'task': asdict(config), 'compatibility': config.fingerprint(),
        'status': 'ready', 'steps': 0, 'checkpoints': {},
    })
    return directory


def require_compatible(directory, config):
    metadata = json.loads((Path(directory) / 'experiment.json').read_text(encoding='utf-8'))
    if metadata['schema_version'] != 1 or metadata['compatibility'] != config.fingerprint():
        raise ValueError('checkpoint and requested experiment are incompatible')
    return metadata


@contextmanager
def experiment_lock(directory):
    """Exclusive ownership; a stale lock after crash requires explicit recovery."""
    lock = Path(directory) / 'trainer.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        lock.unlink()
