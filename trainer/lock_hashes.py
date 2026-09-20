"""Fingerprint every pinned artifact of trainer/requirements.lock.

PyPI artifacts are hashed through their authoritative PyPI digests; the torch
CPU wheel is downloaded once from download.pytorch.org and hashed locally.
The lock file is rewritten in pip --require-hashes format so every rebuild
verifies the same artifacts. Run: python -m trainer.lock_hashes [--verify]
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'trainer' / 'requirements.lock'
TORCH_CACHE = ROOT / 'builds' / 'packages' / 'lock-wheels'
TORCH_CPU_INDEX = 'https://download.pytorch.org/whl/cpu'
PLATFORM = dict(python_tag='cp310', platform_tag='win_amd64')


def pypi_release(name, version):
    url = f'https://pypi.org/pypi/{name}/{version}/json'
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)


def select_artifact(files):
    """Closest artifact to the embedded runtime: cp310 win_amd64 wheel, then
    any Windows wheel, then any pure wheel, then the sdist pip would fall back to."""
    def rank(item):
        filename = item['filename']
        wheel = filename.endswith('.whl')
        cp310 = PLATFORM['python_tag'] in filename
        win_amd64 = PLATFORM['platform_tag'] in filename
        pure = any(tag in filename for tag in ('py3-none-any', 'py2.py3-none-any'))
        if wheel and cp310 and win_amd64: return 0
        if wheel and cp310 and 'win32' in filename: return 1
        if wheel and 'abi3-win_amd64' in filename: return 2
        if wheel and pure: return 3
        if wheel and 'win_amd64' in filename: return 4
        if not wheel: return 5
        return 9
    return min(files, key=rank)


def stream_sha256(url, destination=None):
    digest = hashlib.sha256()
    target = None
    if destination is not None:
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / Path(url).name
    with urllib.request.urlopen(url, timeout=600) as response, \
         (open(target, 'wb') if target else open('/dev/null', 'wb')) as stream:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
            if target:
                stream.write(block)
    return digest.hexdigest()


def parse_requirements():
    pins = []
    for line in LOCK.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if stripped.startswith('--') or stripped.startswith('#'):
            continue
        if stripped:
            pins.append(stripped)
    return pins


def pin_name_version(pin):
    spec = pin.split(';')[0].strip()
    name, _, version = spec.partition('==')
    return name.strip(), version.strip()


def hash_for(name, version):
    if name == 'torch':
        # Local version published only on the PyTorch CPU index.
        quoted = f'torch-{version.replace("+", "%2B")}-cp310-cp310-win_amd64.whl'
        url = f'{TORCH_CPU_INDEX}/{quoted}'
        return stream_sha256(url, TORCH_CACHE), url
    release = pypi_release(name, version)
    artifact = select_artifact(release['urls'])
    return artifact['digests']['sha256'], artifact['url']


def _hashes_in_lock():
    """Return {name: sha256} from the existing lock file, or {} if none."""
    if not LOCK.exists():
        return {}
    result = {}
    current_name = None
    for line in LOCK.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if stripped.startswith('--hash=sha256:'):
            sha = stripped[len('--hash=sha256:'):]
            if current_name:
                result[current_name] = sha
        elif stripped and not stripped.startswith('#') and not stripped.startswith('--'):
            current_name = stripped.rstrip(' \\').split('==')[0].strip()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true',
                        help='Check that the lock file already has all hashes; do NOT rewrite it.')
    args = parser.parse_args(argv)

    # --verify: local check only, no network calls.
    if args.verify:
        existing = _hashes_in_lock()
        pins = parse_requirements()
        unhashed = [pin for pin in pins if pin_name_version(pin)[0] not in existing]
        complete = len(unhashed) == 0 and len(existing) > 0
        print(json.dumps(dict(
            schema_version=1, complete=complete,
            hashed=len(existing), total_pins=len(pins),
            unhashed=unhashed,
        ), ensure_ascii=False))
        return 0 if complete else 1

    # Default: fetch hashes from PyPI / PyTorch index and rewrite the lock.
    pins = parse_requirements()
    lines, missing, summary = [], [], []
    current_name = None
    for pin in pins:
        name, version = pin_name_version(pin)
        sha256, url = hash_for(name, version)
        if not sha256:
            missing.append(f'{name}=={version}')
            continue
        summary.append(dict(requirement=f'{name}=={version}', sha256=sha256, source=url))
        lines.append(f'{name}=={version} \\\n    --hash=sha256:{sha256}')
    if missing:
        print(json.dumps(dict(schema_version=1, complete=False, missing=missing), ensure_ascii=False))
        return 1
    banner = [
        '# Resolved Windows x64 / CPython 3.10.11 runtime.',
        '# Every artifact is fingerprinted; rebuilds must use pip --require-hashes.',
        '# Refresh with: python -m trainer.lock_hashes',
    ]
    LOCK.write_text('\n'.join(banner + lines) + '\n', encoding='utf-8')
    (ROOT / 'builds' / 'packages' / 'lock-wheels').mkdir(parents=True, exist_ok=True)
    (ROOT / 'builds' / 'packages' / 'lock-wheels' / 'fingerprint-summary.json').write_text(
        json.dumps(dict(schema_version=1, platform=PLATFORM, artifacts=summary), indent=2),
        encoding='utf-8')
    print(json.dumps(dict(schema_version=1, complete=True, hashed=len(summary)), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
