"""Create four registered new boundary inputs; never execute a receiver."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import struct

ROOT = Path(__file__).resolve().parents[2]
REGISTRATION = 'b3a8cee4608db93ba3bc446281ed1ded954a6270'
BASELINE = 'acb52828842050986ab95e4ab25b270d227561e1'
PARENT_REPORT = '50a7dbb4b33200e203e102f58195110abedf6159ce02b66b551ebb2c65b74ab0'
PARENT_MANIFEST = '6ca26a31598d8bb9d701bb9f6eba19d783de7e00a3e0730be2ccd3f0b20b12eb'
PARENT_INDEX = '6d9c5b08482f37e30d15893f3a2c517c36f280a9ce6dcae6e11749505416236a'
PARENT_ARCHIVE = 'f27c1583db0526565dd5cf82c13df5d64cb6f315b1a3e3dc27585750113fd270'
BINARY = '6682f833c9c9a9ec23b596af2c8fe3f176de28134a90f3f487e8ab996b464704'
COLD = '187ec959f1d3fb81b7fa4f35df7a118eab7a50dca9677ef6bdacae06aa9657c8'
NAMES = ('active_prefix_6159', 'active_prefix_6160', 'active_prefix_6161', 'active_bad_lich')

def require(condition, message):
    if not condition: raise ValueError(message)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')

def inventory(folder):
    return {p.relative_to(folder).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha(p)}
            for p in sorted(folder.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}

def packed_path(folder, name):
    path = folder.joinpath(*name.replace('\\', '/').split('/')).resolve()
    require(path.is_relative_to(folder.resolve()), 'Escaped source path')
    return path

def shaped(dibit_frames):
    levels = (8000, 24000, -8000, -24000)
    stream = [levels[d] for d in (1, 3) * 16 for _ in range(20)]
    for frame in dibit_frames:
        require(len(frame) == 192 and all(0 <= d < 4 for d in frame), 'Wrong source frame')
        stream.extend(levels[d] for d in frame for _ in range(20))
    stream.extend([8000] * 1280)
    # Full-wave endpoint clamping only; prefix inputs are literal existing bytes.
    values = [sum(stream[max(0, min(len(stream)-1, i+j))] for j in range(-4, 4))/8
              for i in range(len(stream))]
    return struct.pack('<' + 'f'*len(values), *values)

def prepare(parent, output):
    parent, output = Path(parent).resolve(), Path(output).absolute()
    require(len(REGISTRATION) == 40 and all(c in '0123456789abcdef' for c in REGISTRATION), 'Commit registration before generation')
    require(not output.exists() and not output.is_symlink(), 'Existing input corpus is immutable')
    require(sha(parent / 'report.json') == PARENT_REPORT, 'Parent report changed')
    require(sha(parent / 'inputs/manifest.json') == PARENT_MANIFEST, 'Parent inputs changed')
    require(sha(parent / 'frozen/engine.exe') == BINARY, 'Parent recorder changed')
    report = json.loads((parent / 'report.json').read_bytes())
    require(report['measurement_pass'] and report['preservation_pass'] and not report['progression_pass'], 'Prior outcome changed')
    for name, digest in report['files'].items():
        require(sha(packed_path(parent, name)) == digest, 'Prior evidence changed: ' + name)
    index = ROOT / 'docs/research/evidence/nxdn-clear-routing-v1-2026-09-25.json'
    archive = ROOT / 'docs/research/evidence/nxdn-clear-routing-v1-2026-09-25-raw.zip'
    require(sha(index) == PARENT_INDEX and sha(archive) == PARENT_ARCHIVE, 'Prior publication changed')
    old = json.loads((parent / 'inputs/manifest.json').read_bytes())
    cold_path = parent / 'inputs/cold.f32le'
    require(sha(cold_path) == COLD, 'Cold parent changed')
    originals = {str(p.resolve()): sha(p) for p in (parent / 'inputs').rglob('*') if p.is_file()}
    originals.update({str(parent / 'report.json'): PARENT_REPORT, str(index): PARENT_INDEX, str(archive): PARENT_ARCHIVE})
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(parent / 'inputs', output / 'parent')
    shutil.copy2(parent / 'report.json', output / 'parent-report.json')
    shutil.copy2(index, output / 'parent-publication.json')
    for chunk in (37, 512):
        for detail in (0, 1):
            source = parent / f'runs/cold_fast-c{chunk}/{detail}'
            target = output / f'anchors/cold_fast-c{chunk}/{detail}'
            shutil.copytree(source, target)
            for p in source.iterdir():
                if p.is_file(): originals[str(p.resolve())] = sha(p)
    references = {name: row for name, row in inventory(output).items()}
    cold = cold_path.read_bytes()
    vectors = [bytearray((parent / f'inputs/vectors/r{i}.dibits').read_bytes()) for i in range(9)]
    vectors[1][17] ^= 2  # Only full-frame high bit 34; spacer bit 35 unchanged.
    require(bytes(vectors[1]) == (parent / 'inputs/vectors/r1_bad_lich.dibits').read_bytes(), 'Corrupted vector identity differs')
    contents = {f'active_prefix_{cut}': cold[:4*cut] for cut in (6159, 6160, 6161)}
    contents['active_bad_lich'] = shaped(vectors)
    manifest = {'schema': 1, 'kind': 'nxdn_active_boundaries_v1', 'registration_commit': REGISTRATION,
        'source_baseline': BASELINE, 'receiver_sha256': BINARY, 'generator_sha256': sha(__file__),
        'domain': 'discriminator_samples', 'rate_hz': 48000, 'samples_per_symbol': 20,
        'reference_files': references, 'waveforms': {}, 'cases': []}
    for name in NAMES:
        content = contents[name]; count = len(content)//4
        path = output / (name + '.f32le'); path.write_bytes(content)
        origin = output / (name + '.origin.u32le'); origin.write_bytes(struct.pack('<' + 'I'*count, *range(count)))
        occurrences = output / (name + '.occurrence.u32le'); occurrences.write_bytes(bytes(count*4))
        frames = copy.deepcopy(old['waveforms']['cold']['frames'])
        if name == 'active_bad_lich':
            frames[1].update(vector='r1_bad_lich.dibits', sha256=old['vectors']['vectors']['r1_bad_lich.dibits']['sha256'])
        manifest['waveforms'][name] = {'file': path.name, 'sha256': sha(path), 'samples': count,
            'original_file': 'parent/cold.f32le', 'original_sha256': COLD, 'original_samples': 36480,
            'lineage_file': origin.name, 'lineage_sha256': sha(origin),
            'occurrence_file': occurrences.name, 'occurrence_sha256': sha(occurrences),
            'frames': frames, 'scenario': name, 'edit': {'kind': 'lich_parity_before_shaping', 'frame_ordinal': 1, 'full_frame_bit': 34}
            if name == 'active_bad_lich' else {'kind': 'prefix', 'cut': count}}
        for chunk in (37, 512):
            manifest['cases'].append({'id': f'{name}-c{chunk}', 'configuration': name, 'waveform': name, 'chunk': chunk, 'fast': 1})
    require(all(sha(p) == digest for p, digest in originals.items()), 'Historical source changed during preparation')
    save(output / 'manifest.json', manifest)
    return manifest

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('parent', type=Path); parser.add_argument('output', type=Path)
    args = parser.parse_args(); manifest = prepare(args.parent, args.output)
    print(json.dumps({'waveforms': len(manifest['waveforms']), 'cases': len(manifest['cases']),
                      'native_invocations': 16, 'manifest_sha256': sha(args.output / 'manifest.json')}))
