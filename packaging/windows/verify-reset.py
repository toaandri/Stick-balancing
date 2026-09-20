"""Exercise interactive physics reset and stop with a frozen real checkpoint."""
import argparse
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('experiment', type=Path)
args = parser.parse_args()
directory = args.experiment.resolve()
before = set((directory/'evaluations').glob('*'))
with (ROOT/'builds/reset-check.log').open('w', encoding='utf-8') as log:
    process = subprocess.Popen([str(ROOT/'trainer/runtime/python.exe'), '-I',
        str(ROOT/'trainer/bootstrap.py'), 'evaluate', '--experiment', str(directory),
        '--player', str(ROOT/'builds/windows/worker/StickBalancingWorker.exe'),
        '--episodes', '1', '--interactive', '--base-port', '5045'],
        stdin=subprocess.PIPE, stdout=log, stderr=log, text=True)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline and process.poll() is None:
        new = set((directory/'evaluations').glob('*')) - before
        if new:
            time.sleep(1)
            for command in ('reset', 'reset', 'stop'):
                process.stdin.write(json.dumps(dict(schema_version=1, command=command))+'\n')
            process.stdin.flush()
            process.stdin.close()
            break
        time.sleep(.1)
    assert process.wait(timeout=120) == 0
new = set((directory/'evaluations').glob('*')) - before
assert len(new) == 1
report = json.loads((new.pop()/'report.json').read_text(encoding='utf-8'))
assert report['weights_unchanged'] and report['physics_resets'] == 2 and report['stopped_by_user']
(ROOT/'docs/migration/reset-proof.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(dict(physics_resets=report['physics_resets'], weights_unchanged=report['weights_unchanged'])))
