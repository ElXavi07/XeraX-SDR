"""Bundle corresponding application source, patches, tests, docs and build scripts."""
from pathlib import Path
import hashlib
import json
import subprocess
import zipfile

root = Path(__file__).resolve().parents[1]
source = root / 'upstream/dsd-neo'
patch = root / 'patches/xerax.patch'
if (source / '.git').exists():
    # The development workspace uses a separate pinned upstream checkout.
    # In the public repository the engine is vendored; retain its baseline patch.
    result = subprocess.run(['git', '-C', str(source), '-c', 'core.autocrlf=true',
                             '-c', 'core.safecrlf=false', 'diff', '--binary'],
                            stdout=subprocess.PIPE, check=True)
    patch.write_bytes(result.stdout)
version = json.loads((root / 'UPSTREAM.json').read_text())['version']
dest = root / f'dist/XeraX-SDR-{version}-source.zip'
if dest.exists():
    raise SystemExit(f'Refusing to overwrite an existing source release: {dest.name}')
dest.parent.mkdir(exist_ok=True)
files = [root / name for name in ['README.md', 'README.es.md', 'CONTRIBUTING.md',
                                 'LICENSE', 'UPSTREAM.json', '.gitignore', '.gitattributes'] if (root / name).is_file()]
for directory in ['scripts', 'docs', 'checks', 'benchmarks', 'experiments', 'assets', 'patches', '.github', 'releases']:
    files += [p for p in (root / directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
if (source / '.git').exists() or (root / '.git').exists():
    tracked = subprocess.check_output(['git', '-C', str(source), 'ls-files', '-z']).decode().split('\0')
else:
    tracked = list(json.loads((source / 'XERAX_SOURCE_MANIFEST.json').read_text())['files'])
files += [source / name for name in tracked if name and (source / name).is_file()]
notices = source / 'android/package/assets/doc/xerax'
files += [p for p in notices.rglob('*') if p.is_file()]
files = sorted(set(files))
files = [p for p in files if p != source / 'XERAX_SOURCE_MANIFEST.json']
with zipfile.ZipFile(dest, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
    for path in files:
        bundle.write(path, 'XeraX-SDR/' + path.relative_to(root).as_posix())
    manifest = {
        'upstreamCommit': json.loads((root / 'UPSTREAM.json').read_text())['commit'],
        'files': {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in files if p.is_relative_to(source)}
    }
    bundle.writestr('XeraX-SDR/upstream/dsd-neo/XERAX_SOURCE_MANIFEST.json',
                    json.dumps(manifest, indent=2) + '\n')
summary = {'file': dest.name, 'files': len(files), 'bytes': dest.stat().st_size,
           'sha256': hashlib.sha256(dest.read_bytes()).hexdigest()}
print(json.dumps(summary, indent=2))
sums = dest.parent / 'SHA256SUMS.txt'
lines = sums.read_text(encoding='utf-8-sig').splitlines() if sums.exists() else []
lines = [line for line in lines if not line.endswith('  ' + dest.name)]
lines.append(summary['sha256'] + '  ' + dest.name)
sums.write_text('\n'.join(lines) + '\n', encoding='utf-8')
