"""Finite integration check of cooperative save-and-pause using real PPO."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

root = Path(__file__).resolve().parents[2]
output = root/'builds/pause-checks'/uuid.uuid4().hex
output.mkdir(parents=True)
with (output/'launcher.log').open('w', encoding='utf-8') as log:
    process = subprocess.Popen([sys.executable, '-m', 'trainer.launch', '--train',
                                '--data-root', str(output), '--base-port', '5025'],
                               cwd=root, stdin=subprocess.PIPE, stdout=log, stderr=log, text=True,
                               env=dict(os.environ, STICK_DEBUG_STACKS='1'))
    sent = False
    deadline = time.monotonic() + 60
    while process.poll() is None and time.monotonic() < deadline:
        events = list(output.glob('*/events.jsonl'))
        if events and not sent:
            lines = events[0].read_text(encoding='utf-8').splitlines()
            if any('"event": "metrics"' in line for line in lines):
                process.stdin.write('{"schema_version":1,"command":"pause"}\n')
                process.stdin.flush()
                process.stdin.close()
                sent = True
        time.sleep(.1)
    if process.poll() is None:
        if not process.stdin.closed:
            process.stdin.close()
        process.wait(timeout=120)
        raise RuntimeError(f'Cooperative pause timed out; inspect owned launcher PID {process.pid}')
    assert process.returncode == 0 and sent, (process.returncode, sent)
directory = next(p for p in output.iterdir() if p.is_dir())
metadata = json.loads((directory/'experiment.json').read_text(encoding='utf-8'))
assert metadata['status'] == 'paused', metadata
assert 0 < metadata['steps'] < 2048, metadata
assert (directory/'snapshots/latest.pt').is_file()
assert not (directory/'trainer.lock').exists()
proof = dict(schema_version=1, status=metadata['status'], steps=metadata['steps'],
             checkpoint_saved=True, exclusive_lock_released=True)
(root/'docs/migration/pause-proof.json').write_text(json.dumps(proof, indent=2), encoding='utf-8')
print(json.dumps(proof))
