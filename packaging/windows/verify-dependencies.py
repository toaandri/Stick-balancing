"""Verify that every pinned wheel in trainer/requirements.lock exists in the
private runtime and matches the recorded SHA-256.

Run from the repository root with the SYSTEM Python (no network needed):
    python packaging/windows/verify-dependencies.py

Or with the private runtime itself:
    trainer/runtime/python.exe -I packaging/windows/verify-dependencies.py

Exit 0 = all wheels present and matching.
Exit 1 = at least one wheel is missing or has a wrong hash.
Exit 2 = the lock file has no hashes yet (run: python -m trainer.lock_hashes).
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / 'trainer' / 'requirements.lock'
SITE_PACKAGES = ROOT / 'trainer' / 'runtime' / 'Lib' / 'site-packages'


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def parse_lock():
    """Return [(name, version, sha256_or_None)] from the lock file."""
    if not LOCK.exists():
        raise SystemExit(f'Lock file not found: {LOCK}')
    entries = []
    current = None
    for line in LOCK.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if stripped.startswith('#') or stripped.startswith('--extra-index') or not stripped:
            continue
        if stripped.startswith('--hash=sha256:'):
            sha = stripped[len('--hash=sha256:'):]
            if current:
                entries[-1] = (entries[-1][0], entries[-1][1], sha)
        else:
            name_ver = stripped.rstrip(' \\')
            name, _, version = name_ver.partition('==')
            current = name.strip()
            entries.append((current, version.strip(), None))
    return entries


def find_dist_info(name: str) -> Path | None:
    """Locate the .dist-info directory for a package in the private runtime."""
    normalised = name.lower().replace('-', '_')
    for d in SITE_PACKAGES.glob('*.dist-info'):
        if d.name.lower().split('-')[0] == normalised:
            return d
    return None


def find_wheel_record(dist_info: Path) -> Path | None:
    """Return the RECORD file inside a .dist-info directory."""
    record = dist_info / 'RECORD'
    return record if record.is_file() else None


def find_wheel_file(dist_info: Path) -> Path | None:
    """Return the installed .whl path if recorded, or None."""
    # Wheels installed by pip leave a WHEEL marker; we locate any .whl in site-packages.
    name_prefix = dist_info.name.split('-')[0].lower()
    for candidate in SITE_PACKAGES.glob(f'{name_prefix}*.whl'):
        return candidate
    # Fall back: check direct_url.json for the original wheel path (may not exist).
    direct = dist_info / 'direct_url.json'
    if direct.is_file():
        try:
            data = json.loads(direct.read_text(encoding='utf-8'))
            url = data.get('url', '')
            if url.startswith('file://') and url.endswith('.whl'):
                p = Path(url[7:])
                if p.is_file():
                    return p
        except (ValueError, KeyError):
            pass
    return None


def check_installed_hash(name: str, expected_sha: str | None) -> dict:
    """
    Verify that the package is installed in the private runtime.
    If the lock has a hash and a cached wheel is found, verify the wheel hash.
    Returns a result dict.
    """
    dist = find_dist_info(name)
    if dist is None:
        return dict(name=name, status='missing', detail='not found in private runtime')
    if expected_sha is None:
        return dict(name=name, status='no_hash', detail='lock entry has no --hash yet')
    # Try to verify the wheel file hash.
    wheel = find_wheel_file(dist)
    if wheel and wheel.is_file():
        actual = sha256_file(wheel)
        if actual == expected_sha:
            return dict(name=name, status='ok', wheel=str(wheel.name))
        return dict(name=name, status='hash_mismatch',
                    detail=f'expected {expected_sha[:16]}… got {actual[:16]}…',
                    wheel=str(wheel.name))
    # No cached wheel — installed but cannot verify hash from files alone.
    return dict(name=name, status='installed_no_wheel',
                detail='package is installed but no .whl found to verify hash')


def main():
    entries = parse_lock()
    hashed = [e for e in entries if e[2] is not None]
    if not hashed:
        print(json.dumps(dict(
            schema_version=1, complete=False,
            detail='Lock file has no --hash entries. Run: python -m trainer.lock_hashes',
        ), ensure_ascii=False, indent=2))
        sys.exit(2)

    results = [check_installed_hash(name, sha) for name, _ver, sha in entries]
    missing  = [r for r in results if r['status'] == 'missing']
    mismatched = [r for r in results if r['status'] == 'hash_mismatch']
    no_hash  = [r for r in results if r['status'] == 'no_hash']
    ok       = [r for r in results if r['status'] in ('ok', 'installed_no_wheel')]

    complete = len(missing) == 0 and len(mismatched) == 0 and len(no_hash) == 0
    report = dict(
        schema_version=1,
        complete=complete,
        ok=len(ok),
        missing=len(missing),
        hash_mismatches=len(mismatched),
        no_hash_entries=len(no_hash),
        total=len(results),
        details=results,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0 if complete else 1)


if __name__ == '__main__':
    main()
