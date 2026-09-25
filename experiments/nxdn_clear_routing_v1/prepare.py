"""Construct the registered finite clear routing waveforms from agreed AIR bytes."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct

ROOT = Path(__file__).resolve().parents[2]
AIR_MANIFEST = '17061018477b6451207758d6e0390b3ef623e88099f565bfc3416f1168127067'
AIR_REPORT = '867264df1b1f05eaa5db49d30e7287def90c3a32ebb3d9dcd47a0e2feb296f6f'
AIR_RECORDS = 'bedb3ae824c357e68e8d2883b808b357e228e74c7ce253acf0a41cf257234c0b'
AIR_INDEX = '97b56f7d5ad4b4348b05daaa3915ebbcc926ff2a8c7bc40dc5220437fcb1016d'
LEVELS = (8000, 24000, -8000, -24000)
CONFIGURATIONS = (('primed', 'primed', 0), ('cold_default', 'cold', 0), ('cold_fast', 'cold', 1),
                  ('single_weak', 'single_weak', 1), ('bad_lich', 'bad_lich', 0), ('zero', 'zero', 0),
                  ('prefix_9999', 'prefix_9999', 0), ('prefix_10000', 'prefix_10000', 0),
                  ('prefix_10001', 'prefix_10001', 0))

def require(ok, message):
    if not ok: raise ValueError(message)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def dibits(raw):
    return bytes((v >> shift) & 3 for v in raw for shift in (6, 4, 2, 0))

def shaped(records):
    source = [LEVELS[d] for d in (1, 3) * 16 for _ in range(20)]
    for frame in records:
        require(type(frame) is bytes and len(frame) == 48, 'Wrong source frame dimension')
        source.extend(LEVELS[d] for d in dibits(frame) for _ in range(20))
    source.extend([8000] * 1280)
    # Integer levels and denominator eight give exact binary fractions before f32.
    values = [sum(source[max(0, min(len(source) - 1, i + k - 4))] for k in range(8)) / 8
              for i in range(len(source))]
    return struct.pack('<' + 'f' * len(values), *values)

def mutated_lich(raw):
    require(type(raw) is bytes and len(raw) == 48, 'Wrong LICH source dimension')
    changed = bytearray(raw); changed[4] ^= 0x20
    return bytes(changed)

def crc(info, width):
    require(width in (6, 12) and set(info) <= {'0', '1'}, 'Invalid control information')
    value = (1 << width) - 1
    for bit in info:
        feedback = int(bit) ^ (value >> (width - 1))
        value = ((value << 1) & ((1 << width) - 1)) ^ ({6: 0x27, 12: 0x80F}[width] if feedback else 0)
    return value

def prepare(parent, output):
    parent = Path(parent).resolve(); output = Path(output).absolute()
    require(not output.exists() and not output.is_symlink(), 'Existing corpus is immutable')
    require(sha(parent / 'report.json') == AIR_REPORT, 'AIR report changed')
    require(sha(parent / 'inputs/manifest.json') == AIR_MANIFEST, 'AIR input identity changed')
    require(sha(parent / 'primary/frames.records96') == AIR_RECORDS, 'Agreed AIR bytes changed')
    index = ROOT / 'docs/research/evidence/nxdn-air-v1-2026-09-25.json'
    require(sha(index) == AIR_INDEX, 'AIR publication changed')
    report = json.loads((parent / 'report.json').read_bytes())
    require(all(report.get(k) is True for k in ('measurement_pass', 'progression_pass', 'preservation_pass'))
            and report.get('product_promotion') is False, 'AIR gate does not pass')
    source_manifest = json.loads((parent / 'inputs/manifest.json').read_bytes())
    for name, row in source_manifest['files'].items():
        p = parent / 'inputs' / name
        require(p.stat().st_size == row['bytes'] and sha(p) == row['sha256'], 'AIR source file changed: ' + name)
    before = {str(p.resolve()): sha(p) for p in (parent / 'inputs').iterdir() if p.is_file()}
    before[str((parent / 'report.json').resolve())] = AIR_REPORT
    before[str((parent / 'primary/frames.records96').resolve())] = AIR_RECORDS
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(parent / 'inputs', output / 'reference')
    shutil.copy2(parent / 'report.json', output / 'reference/air-report.json')
    shutil.copy2(parent / 'primary/frames.records96', output / 'reference/primary.records96')
    shutil.copy2(index, output / 'reference/publication.json')
    references = {p.relative_to(output).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha(p)}
                  for p in (output / 'reference').iterdir() if p.is_file()}
    data = (parent / 'primary/frames.records96').read_bytes()
    raw = [data[i * 96:i * 96 + 48] for i in range(9)]
    air = [data[i * 96 + 48:(i + 1) * 96] for i in range(9)]
    frame_metadata = json.loads((parent / 'inputs/frames.json').read_bytes())
    vectors = {}; (output / 'vectors').mkdir()
    for frame_id in range(9):
        name = f'r{frame_id}.dibits'; p = output / 'vectors' / name; p.write_bytes(dibits(air[frame_id]))
        row = frame_metadata[frame_id]; sacch = row['sacch_information']; facch = row['facch_information']
        control = lambda info, width: {'information_bits': info, 'computed_crc': crc(info, width),
                                      'transmitted_crc': crc(info, width), 'crc_expected_pass': True}
        facch_bits = ''.join(f'{v:08b}' for v in bytes.fromhex(facch))
        vectors[name] = {'source_frame': frame_id, 'name': row['name'], 'lich': row['lich'] >> 1,
            'full_lich': row['lich'], 'sha256': sha(p), 'raw48_hex': raw[frame_id].hex(),
            'sacch': control(sacch, 6), 'facch': None if row['lich'] == 0xAE else control(facch_bits, 12),
            'transmitted_voice': row['transmitted_voice'], 'source_quartet': row['source_quartet']}
    p = output / 'vectors/r1_bad_lich.dibits'; p.write_bytes(dibits(mutated_lich(air[1])))
    vectors[p.name] = {**vectors['r1.dibits'], 'full_lich': 0xAF, 'sha256': sha(p),
                       'raw48_hex': mutated_lich(raw[1]).hex(), 'parity_valid': False}
    manifest = {'schema': 1, 'kind': 'nxdn_clear_routing_v1', 'domain': 'discriminator_samples',
        'rate_hz': 48000, 'symbol_rate': 2400, 'samples_per_symbol': 20, 'ramp': 8,
        'registration_commit': 'd98ccd32ddc6cb4fa15bae07a91cf33e144df445',
        'product_baseline': '289a82f8fd9c0495b64bf948fd45413bc63261c4',
        'air_report_sha256': AIR_REPORT, 'air_manifest_sha256': AIR_MANIFEST,
        'air_output_sha256': AIR_RECORDS, 'air_publication_sha256': AIR_INDEX,
        'generator_sha256': sha(__file__), 'reference_files': references,
        'vectors': {'vectors': vectors}, 'waveforms': {}, 'cases': []}
    def add(name, content, ids, original=None, edit=None):
        p = output / (name + '.f32le'); p.write_bytes(content); count = len(content) // 4
        origin = output / (name + '.origin.u32le'); origin.write_bytes(struct.pack('<' + 'I' * count, *range(count)))
        occurrence = output / (name + '.occurrence.u32le'); occurrence.write_bytes(bytes(count * 4))
        original = manifest['waveforms'].get(original)
        frames = []
        for ordinal, source_id in enumerate(ids):
            vector_name = 'r1_bad_lich.dibits' if name == 'bad_lich' and ordinal == 2 else f'r{source_id}.dibits'
            frames.append({'ordinal': ordinal, 'source_frame': source_id, 'kind': frame_metadata[source_id]['name'],
                'start': 640 + ordinal * 3840, 'end': 640 + (ordinal + 1) * 3840,
                'vector': vector_name, 'sha256': vectors[vector_name]['sha256'],
                'scored': not (name in ('primed', 'bad_lich') or name.startswith('prefix_')) or ordinal != 0})
        manifest['waveforms'][name] = {'file': p.name, 'sha256': sha(p), 'samples': count,
            'original_file': original['file'] if original else p.name,
            'original_sha256': original['sha256'] if original else sha(p),
            'original_samples': original['samples'] if original else count,
            'lineage_file': origin.name, 'lineage_sha256': sha(origin),
            'occurrence_file': occurrence.name, 'occurrence_sha256': sha(occurrence),
            'frames': frames, 'scenario': name, 'edit': edit or {'kind': 'none'}}
    primed_ids = [0] + list(range(9)); primed = shaped([air[i] for i in primed_ids])
    add('primed', primed, primed_ids)
    add('cold', shaped(air), list(range(9)))
    add('single_weak', shaped([air[1]]), [1])
    changed = [air[i] for i in primed_ids]; changed[2] = mutated_lich(changed[2])
    add('bad_lich', shaped(changed), primed_ids, 'primed',
        {'kind': 'lich_parity_before_shaping', 'frame_ordinal': 2, 'full_frame_bit': 34})
    add('zero', bytes(len(primed)), [], 'primed', {'kind': 'zero'})
    for cut in (9999, 10000, 10001):
        add(f'prefix_{cut}', primed[:cut * 4], primed_ids, 'primed', {'kind': 'prefix', 'cut': cut})
    for config, wave, fast in CONFIGURATIONS:
        for chunk in (37, 512):
            manifest['cases'].append({'id': f'{config}-c{chunk}', 'configuration': config,
                'waveform': wave, 'chunk': chunk, 'fast': fast})
    require(len(manifest['cases']) == 18 and len(manifest['waveforms']) == 8, 'Wrong fixed matrix')
    require(all(Path(p).is_file() and sha(p) == digest for p, digest in before.items()), 'AIR evidence changed while preparing')
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('parent', type=Path); parser.add_argument('output', type=Path)
    args = parser.parse_args(); result = prepare(args.parent, args.output)
    print(json.dumps({'waveforms': len(result['waveforms']), 'configurations': 9, 'native_invocations': 36,
                      'manifest_sha256': sha(args.output / 'manifest.json')}))
