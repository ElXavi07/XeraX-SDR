"""Fetch the pinned decoder and apply XeraX's reviewable patch.

Never resets or overwrites an existing modified checkout.
"""
import hashlib
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
lock = json.loads((root / 'UPSTREAM.json').read_text())
source = root / 'upstream/dsd-neo'
patch = root / 'patches/xerax.patch'

def git(*args, check=True):
    return subprocess.run(['git', '-C', str(source), *args], check=check, capture_output=True)

if not source.exists():
    source.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'clone', '--no-checkout', '--filter=blob:none', lock['repository'], str(source)], check=True)
    git('checkout', '--detach', lock['commit'])
if not (source / '.git').exists():
    manifest_path = source / 'XERAX_SOURCE_MANIFEST.json'
    if not manifest_path.is_file():
        raise SystemExit('Existing non-Git source has no XeraX manifest; leaving it unchanged.')
    manifest = json.loads(manifest_path.read_text())
    if manifest['upstreamCommit'] != lock['commit']:
        raise SystemExit('Source archive does not match the pinned version.')
    for name, expected in manifest['files'].items():
        path = (source / name).resolve()
        if not path.is_relative_to(source.resolve()) or not path.is_file():
            raise SystemExit(f'Missing or invalid archive member: {name}')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise SystemExit(f'Archive source was modified: {name}; leaving it unchanged.')
    print('Complete patched source archive verified; no checkout or patch needed.')
    raise SystemExit(0)
if git('rev-parse', 'HEAD').stdout.decode().strip() != lock['commit']:
    raise SystemExit('Existing decoder checkout is not the pinned commit; leaving it unchanged.')
if git('apply', '--reverse', '--check', str(patch), check=False).returncode == 0:
    print('XeraX patch already applied.')
elif git('apply', '--check', str(patch), check=False).returncode == 0:
    git('apply', str(patch))
    print('XeraX patch applied.')
else:
    raise SystemExit('Patch conflicts with the existing checkout; leaving it unchanged.')
