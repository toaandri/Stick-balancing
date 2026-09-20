"""Assemble the explicit Windows preview bundle, without downloading at runtime.

Workers for N=1, N=2 and N=3 are included when their executables exist.
Only the N=1 worker is mandatory; N=2 and N=3 are optional at staging time
(they can be added later with --refresh-code once built).
"""
import argparse
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]

# All worker executables that may be present in builds/windows/worker/.
WORKER_NAMES = [
    'StickBalancingWorker.exe',       # N=1
    'StickBalancingWorkerN2.exe',     # N=2
    'StickBalancingWorkerN3.exe',     # N=3
]
REQUIRED_ARTIFACTS = [
    ROOT/'builds/windows/app/StickBalancing.exe',
    ROOT/'builds/windows/worker/StickBalancingWorker.exe',   # N=1 is mandatory
    ROOT/'trainer/runtime/python.exe',
]


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--refresh-code', action='store_true')
args = parser.parse_args()
destination = args.output.resolve()
destination.relative_to(ROOT)  # staging must remain within this repository

# ------------------------------------------------------------------
# --refresh-code: update code and worker files in an existing bundle
# ------------------------------------------------------------------
if args.refresh_code:
    manifest_path = destination / 'bundle-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    sources = [
        (ROOT / 'builds/windows/app', destination),
        (ROOT / 'builds/windows/worker', destination / 'workers'),
        (ROOT / 'configs', destination / 'configs'),
    ]
    copied = []
    for source_dir, target_dir in sources:
        if not source_dir.is_dir():
            continue
        for source in source_dir.rglob('*'):
            if source.is_file():
                target = target_dir / source.relative_to(source_dir)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                copied.append(target)
    for source in (ROOT / 'trainer').glob('*.py'):
        target = destination / 'trainer' / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(target)
    for path in copied:
        manifest['files'][path.relative_to(destination).as_posix()] = dict(
            sha256=sha256_file(path), size=path.stat().st_size)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(dict(refreshed_files=len(copied))))
    sys.exit(0)

# ------------------------------------------------------------------
# Fresh staging assembly
# ------------------------------------------------------------------
if destination.exists():
    raise SystemExit('Use a fresh staging directory; existing files are not overwritten')

for path in REQUIRED_ARTIFACTS:
    if not path.is_file():
        raise SystemExit(f'Required artifact missing: {path}')

# Desktop application
shutil.copytree(ROOT / 'builds/windows/app', destination)

# Workers — copy the whole worker folder; all executables present go in.
worker_src = ROOT / 'builds/windows/worker'
worker_dst = destination / 'workers'
worker_dst.mkdir(parents=True)
for entry in worker_src.rglob('*'):
    if entry.is_file():
        target = worker_dst / entry.relative_to(worker_src)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(entry, target)

# Note which N-values have a worker available for documentation.
available_workers = [n for n, name in enumerate(WORKER_NAMES, 1)
                     if (worker_src / name).is_file()]

# Python runtime + trainer sources
shutil.copytree(ROOT / 'trainer/runtime', destination / 'trainer/runtime',
                ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
for path in (ROOT / 'trainer').glob('*.py'):
    target = destination / 'trainer' / path.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)

# Configuration files
shutil.copytree(ROOT / 'configs', destination / 'configs')

# Notices
notices = destination / 'notices'
notices.mkdir()
shutil.copy2(ROOT / 'trainer/runtime/LICENSE.txt', notices / 'Python-LICENSE.txt')

inventory = []
for distribution in sorted(metadata.distributions(), key=lambda d: d.metadata['Name'].lower()):
    name = distribution.metadata['Name']
    entry = dict(name=name, version=distribution.version,
                 homepage=distribution.metadata.get('Home-page'),
                 license=distribution.metadata.get('License'), notices=[])
    for item in distribution.files or []:
        if any(token in item.name.lower() for token in ('license', 'licence', 'copying', 'notice')):
            source = Path(distribution.locate_file(item)).resolve()
            if not source.is_file() or source.suffix in ('.py', '.pyc', '.pyd'):
                continue
            target = notices / name / str(item).replace('..', '_').replace(':', '_')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            entry['notices'].append(target.relative_to(destination).as_posix())
    inventory.append(entry)
(notices / 'python-distributions.json').write_text(json.dumps(inventory, indent=2), encoding='utf-8')

for package in ('com.unity.ml-agents', 'com.unity.sentis'):
    for folder in (ROOT / 'unity/Library/PackageCache').glob(package + '@*'):
        for name in ('LICENSE.md', 'LICENSE', 'Third Party Notices.md'):
            source = folder / name
            if source.is_file():
                target = notices / package / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

# Preview note
(destination / 'PREVIEW.txt').write_text(
    'Stick Balancing — prototype\n'
    f'Workers available for N={available_workers}.\n'
    'Real local PPO, checkpoints, pause/resume and frozen evaluation.\n'
    'Not a validated final release: no promised swing-up convergence.\n'
    'See the project README for outstanding acceptance criteria.\n',
    encoding='utf-8')

# Bundle manifest (sha256 + size for every file)
files = {}
for path in sorted(destination.rglob('*')):
    if path.is_file():
        files[path.relative_to(destination).as_posix()] = dict(
            sha256=sha256_file(path), size=path.stat().st_size)
(destination / 'bundle-manifest.json').write_text(
    json.dumps(dict(schema_version=1, available_workers=available_workers, files=files), indent=2),
    encoding='utf-8')
print(json.dumps(dict(
    path=str(destination),
    available_workers=available_workers,
    files=len(files),
    bytes=sum(x['size'] for x in files.values()),
)))
