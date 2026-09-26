"""One registered pair. A valid negative receiver result is retained, not retried."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import zipfile

from policy import (ROOT, MATRIX, OFFSETS, ANCHORS, ARCHIVE_SHA, require, digest,
                    inspector, runner, quality)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def load_run(directory):
    report = read(directory / 'report.json')
    require(report['measurement_pass'], 'Invalid native measurement')
    require(report['inputs_before'] == report['inputs_after'], 'Input drift')
    for name, expected in report['output_sha256'].items():
        require(digest(directory / name) == expected, 'Output drift: ' + name)
    require(digest(directory / 'analysis.json') == report['analysis_sha256'], 'Analysis drift')
    analysis = inspector()(directory / 'cases.jsonl', directory, directory / 'vectors/vectors.json')
    require(analysis == report['analysis'] == read(directory / 'analysis.json'), 'Reanalysis differs')
    require(analysis['measurement_contract_pass'] and analysis['direct_block_gate_pass'], 'Contract failure')
    rows = [json.loads(line) for line in (directory / 'cases.jsonl').read_bytes().splitlines()]
    return report, analysis, rows


def verify_anchors(directory, role, rows, archive):
    prefix = 'build/rc2-runtime-pair/' + role + '/'
    frozen = [json.loads(line) for line in archive.read(prefix + 'cases.jsonl').splitlines()]
    direct = lambda rr: [x for x in rr if x['kind'] == 'direct']
    require(direct(rows) == direct(frozen), 'Direct anchor changed: ' + role)
    original = {x['id']: x for x in frozen if x['kind'] == 'case'}
    count = 0
    for row in rows:
        if row['kind'] != 'case' or (row['scenario'] == 'valid' and row['offset'] not in ANCHORS):
            continue
        require(row == original[row['id']], 'Anchor row changed: ' + row['id'])
        require((directory / row['pop_trace']).read_bytes() == archive.read(prefix + row['pop_trace']),
                'Anchor trace changed: ' + row['id'])
        count += 1
    require(count == 54, 'Missing anchors')
    return count


def chunk_gate(directory, rows):
    groups = {}
    cache = ('provider_sync', 'provider_end', 'cache_sync_pos', 'cache_sync_len',
             'cache_end_pos', 'cache_end_len')
    for row in rows:
        if row['kind'] != 'case':
            continue
        projection = json.loads(json.dumps(row['observed']))
        for frame in projection['frames']:
            for name in cache:
                frame.pop(name)
        projection['trace_sha256'] = digest(directory / row['pop_trace'])
        groups.setdefault((row['scenario'], row['ramp'], row['offset']), []).append((row['chunk'], projection))
    return len(groups) == 52 and all(sorted(c for c, _ in g) == [1, 37, 512]
                                    and all(v == g[0][1] for _, v in g) for g in groups.values())


def run(baseline, candidate, output, archive_path):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    executables = [Path(p).resolve() for p in (baseline, candidate)]
    archive_path = Path(archive_path).resolve()
    result = {'schema': 1, 'kind': 'nxdn_absolute_entry_pair', 'measurement_pass': False,
              'progression_pass': False, 'started_utc': datetime.now(timezone.utc).isoformat(),
              'errors': [], 'phases': {}, 'domain': 'discriminator_samples', 'offsets': OFFSETS,
              'input_hashes': {}, 'comparison': None,
              'limits': ['Cold absolute entry only, not dropped frames in a warm receiver.',
                         'Same control payloads and negative seeds; no RF, IQ, voice or CPU measurement.',
                         'Full dispatcher/profile feedback and physical device execution are excluded.']}
    try:
        require(digest(archive_path) == ARCHIVE_SHA, 'Frozen RC2 evidence changed')
        inner = runner()
        paths = [ROOT / p for p in inner['SOURCE_FILES']] + executables + [archive_path]
        result['input_hashes'] = {str(p): digest(p) for p in paths}
        # Preserve exact source bytes used by this execution; binaries and large
        # frozen archive remain identified by hash and their public provenance.
        for p in paths:
            if p.is_relative_to(ROOT) and 'dist' not in p.relative_to(ROOT).parts and p.suffix != '.exe':
                target = output / 'sources' / p.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(p.read_bytes())

        def stable():
            for p, expected in result['input_hashes'].items():
                require(digest(p) == expected, 'Input changed: ' + p)

        runs = []
        with zipfile.ZipFile(archive_path) as archive:
            for role, executable in zip(('baseline', 'candidate'), executables):
                stable()
                report = inner['run'](executable, output / role)
                result['phases'][role] = {'measurement_pass': report['measurement_pass'],
                                          'receiver_gate_pass': report['receiver_gate_pass']}
                stable()
                loaded = load_run(output / role)
                result['phases'][role]['anchor_cases'] = verify_anchors(output / role, role, loaded[2], archive)
                require(chunk_gate(output / role, loaded[2]), 'Chunk invariance failed: ' + role)
                runs.append(loaded)
        comparison = quality(runs[0][1], runs[1][1])
        save(output / 'comparison.json', comparison)
        result['comparison'] = comparison
        result['measurement_pass'] = True
        result['progression_pass'] = comparison['progression_pass']
        stable()
    except Exception as exc:
        result['errors'].append(type(exc).__name__ + ': ' + str(exc))
    finally:
        result['inputs_after'] = {}
        for p, expected in result['input_hashes'].items():
            try:
                actual = digest(p)
            except OSError:
                actual = None
            result['inputs_after'][p] = actual
            if actual != expected:
                result['errors'].append('Input drift: ' + p)
        if result['errors']:
            result['measurement_pass'] = result['progression_pass'] = False
        save(output / 'report.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--rc2-archive', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.baseline, args.candidate, args.output, args.rc2_archive)
    print(json.dumps({k: result[k] for k in ('measurement_pass', 'progression_pass', 'errors')}))
    return 0 if result['measurement_pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
