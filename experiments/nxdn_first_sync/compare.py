"""Independent paired gates; this file never invokes a native decoder."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSPECTOR = ROOT / 'experiments/nxdn_frames/inspect_frames.py'
INSPECTOR_SHA = 'a26e47b64f09db1810d4d0dbb0c2c8d7e110b1abc248eecf0a634618ab514bc4'
CACHE_FIELDS = {'provider_sync', 'provider_end', 'cache_sync_pos', 'cache_sync_len', 'cache_end_pos', 'cache_end_len'}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_bytes())

def normalized_analysis(value):
    value = json.loads(json.dumps(value))
    for key in ('artifact_sha256', 'vector_sha256'):
        entries = value[key]
        normalized = {name.replace('\\', '/').rsplit('/', 1)[-1]: digest for name, digest in entries.items()}
        if len(normalized) != len(entries):
            raise ValueError('Ambiguous artifact names')
        value[key] = normalized
    return value

def load_run(directory):
    directory = Path(directory).resolve()
    report = read(directory / 'report.json')
    if not report['measurement_pass'] or report['native']['returncode'] != 0 or report['errors']:
        raise ValueError('Invalid underlying measurement: ' + str(directory))
    if report['inputs_before'] != report['inputs_after']:
        raise ValueError('Underlying input drift')
    outputs = report['output_sha256']
    if outputs != report['outputs_before_validation'] or outputs != report['outputs_after_validation']:
        raise ValueError('Underlying output drift')
    if len(outputs) != 163:
        raise ValueError('Incomplete fixed output set')
    for name, expected in outputs.items():
        path = (directory / name).resolve()
        if directory not in path.parents or sha(path) != expected:
            raise ValueError('Output hash/path mismatch: ' + name)
    for name, expected in report['manifest_sha256'].items():
        path = (directory / name).resolve()
        if directory not in path.parents or sha(path) != expected:
            raise ValueError('Manifest drift')
    if read(directory / 'manifest-before.json')['inputs'] != report['inputs_before']:
        raise ValueError('Manifest input mismatch')
    if sha(directory / 'analysis.json') != report['analysis_sha256']:
        raise ValueError('Saved analysis drift')
    source = INSPECTOR.read_bytes()
    if hashlib.sha256(source).hexdigest() != INSPECTOR_SHA:
        raise ValueError('Frozen schema2 inspector changed')
    declared = [digest for path, digest in report['inputs_before'].items()
                if path.replace('\\', '/').endswith('/experiments/nxdn_frames/inspect_frames.py')]
    if declared != [INSPECTOR_SHA]:
        raise ValueError('Run used a different inspector')
    namespace = {'__name__': 'first_sync_frozen_inspector', '__file__': str(INSPECTOR)}
    exec(compile(source, str(INSPECTOR), 'exec'), namespace)
    analysis = namespace['analyze'](directory / 'cases.jsonl', directory, directory / 'vectors/vectors.json')
    normalized = normalized_analysis(analysis)
    if normalized != normalized_analysis(report['analysis']) or normalized != normalized_analysis(read(directory / 'analysis.json')):
        raise ValueError('Independent reanalysis differs')
    for name, expected in report['validated_outputs'].items():
        if outputs.get(name) != expected:
            raise ValueError('Validated artifact binding differs')
    for key in ('measurement_contract_pass', 'direct_block_gate_pass', 'receiver_gate_pass'):
        if report[key] != analysis[key]:
            raise ValueError('Contradictory gate: ' + key)
    rows = [json.loads(line) for line in (directory / 'cases.jsonl').read_bytes().splitlines()]
    return {'directory': directory, 'report': report, 'analysis': analysis, 'rows': rows}

def baseline_matches(baseline, frozen):
    if not baseline['analysis']['receiver_gate_pass'] or not frozen['analysis']['receiver_gate_pass']:
        raise ValueError('Baseline quality gate failed')
    if baseline['rows'] != frozen['rows']:
        raise ValueError('Fresh baseline changed frozen observations')
    for name, expected in frozen['report']['output_sha256'].items():
        if name.endswith('.u32le') or name.startswith('vectors/'):
            if baseline['report']['output_sha256'].get(name) != expected:
                raise ValueError('Fresh baseline changed frozen traces/vectors')

def chunk_gate(rows, output_hashes=None):
    groups = {}
    for row in rows:
        if row['kind'] != 'case':
            continue
        projection = json.loads(json.dumps(row['observed']))
        for frame in projection['frames']:
            for key in CACHE_FIELDS:
                frame.pop(key)
        if output_hashes is not None:
            projection['trace_sha256'] = output_hashes[row['pop_trace']]
        key = (row['scenario'], row['ramp'], row['offset'])
        groups.setdefault(key, []).append((row['chunk'], projection))
    return len(groups) == 52 and all(sorted(chunk for chunk, _ in values) == [1, 37, 512]
           and all(value == values[0][1] for _, value in values) for values in groups.values())

def quality(baseline_analysis, candidate_analysis):
    failures, cases = [], []
    if not candidate_analysis['receiver_gate_pass']:
        failures.append({'reason': 'candidate_receiver_gate_failed'})
    baseline = {case['id']: case for case in baseline_analysis['cases']}
    candidate = {case['id']: case for case in candidate_analysis['cases']}
    if set(baseline) != set(candidate) or len(baseline) != 156:
        raise ValueError('Incomplete comparison grid')
    def good(case):
        return {frame['source_frame']: frame['end_consumed'] for frame in case['frames']
                if frame['source_frame'] is not None and frame['exact_channels'] and frame['current_proof']
                and not frame['source_truncated'] and frame['expected_variant'] == 'valid'}
    for identity, before in baseline.items():
        if before['scenario'] != 'valid':
            continue
        b, c = good(before), good(candidate[identity])
        improvement = min(b.values()) - min(c.values()) if b and c else None
        passed = set(b) == {1, 2, 3} and set(c) == {0, 1, 2, 3} and improvement is not None and improvement > 3360
        cases.append({'id': identity, 'baseline_frames': sorted(b), 'candidate_frames': sorted(c),
                      'first_crc_gain_samples': improvement,
                      'first_crc_gain_ms': improvement / 48.0 if improvement is not None else None, 'pass': passed})
        if not passed:
            failures.append({'case': identity, 'reason': 'first_frame_gain_or_preservation_failed'})
    if len(cases) != 120:
        raise ValueError('Incomplete positive grid')
    return cases, failures

def costs(rows):
    result = {}
    for row in rows:
        if row['kind'] != 'case':
            continue
        run = row['observed']
        item = result.setdefault(row['scenario'], {'cases': 0, 'frame_calls': 0, 'body_samples': 0,
                'no_current_proof_body_samples': 0, 'result0_calls': 0, 'result0_body_samples': 0,
                'result1_calls': 0, 'result1_body_samples': 0,
                'current_proof_calls': 0, 'crc_checks': 0, 'hard_fallbacks': 0})
        item['cases'] += 1
        item['frame_calls'] += len(run['frames'])
        for frame in run['frames']:
            consumed = frame['end_consumed'] - frame['sync_consumed']
            item['body_samples'] += consumed
            item['current_proof_calls'] += frame['result'] == 2
            if frame['result'] in (0, 1):
                item['no_current_proof_body_samples'] += consumed
                prefix = 'result' + str(frame['result'])
                item[prefix + '_calls'] += 1
                item[prefix + '_body_samples'] += consumed
        item['crc_checks'] += len(run['events'])
        item['hard_fallbacks'] += sum(event['fallback'] for event in run['events'])
    return result

def compare(baseline_dir, candidate_dir, *, frozen_baseline_dir):
    baseline, candidate, frozen = map(load_run, (baseline_dir, candidate_dir, frozen_baseline_dir))
    baseline_matches(baseline, frozen)
    for name in ('vectors.json', 'valid.dibits', 'wrong_all_crc.dibits', 'wrong_lich.dibits'):
        if sha(baseline['directory'] / 'vectors' / name) != sha(candidate['directory'] / 'vectors' / name):
            raise ValueError('Candidate vector changed')
    identities = [run['report']['inputs_before'][run['report']['command'][0]] for run in (baseline, candidate)]
    if identities[0] == identities[1]:
        raise ValueError('Baseline and candidate binary identities identical')
    direct = [[row for row in run['rows'] if row['kind'] == 'direct'] for run in (baseline, candidate)]
    cases, failures = quality(baseline['analysis'], candidate['analysis'])
    if direct[0] != direct[1]:
        failures.append({'reason': 'direct_block_observations_changed'})
    chunks = {name: chunk_gate(run['rows'], run['report']['output_sha256'])
              for name, run in (('baseline', baseline), ('candidate', candidate))}
    if not all(chunks.values()):
        failures.append({'reason': 'chunk_invariance_failed'})
    return {'schema': 1, 'evidence_valid': True, 'promotion_pass': not failures,
            'domain': 'discriminator_samples', 'rate_hz': 48000, 'cases': cases, 'failures': failures,
            'baseline_matches_frozen': True, 'chunk_invariance': chunks,
            'binary_sha256': dict(zip(('baseline', 'candidate'), identities)),
            'report_sha256': {key: sha(run['directory'] / 'report.json') for key, run in
                             (('baseline', baseline), ('candidate', candidate), ('frozen', frozen))},
            'costs': {'baseline': costs(baseline['rows']), 'candidate': costs(candidate['rows'])},
            'original_iq_latency': None, 'cpu_speedup': None, 'pcm_latency': None,
            'limits': ['Sign-only NXDN48 component acquisition with unchanged generated controls; not RF or CPU speed.',
                       'Recorded binary identities do not prove private compiler flags; separate linkage audit required.',
                       'Historical foreign source/binary paths are provenance; current file availability is not assumed.',
                       'Full dispatcher/profile feedback, scanner hold correctness and documented side effects are outside this study.']}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path); parser.add_argument('candidate', type=Path)
    parser.add_argument('--frozen-baseline-dir', type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.baseline, args.candidate, frozen_baseline_dir=args.frozen_baseline_dir)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result['promotion_pass'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
