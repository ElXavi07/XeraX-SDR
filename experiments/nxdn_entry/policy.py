"""Explicit input-grid adapter; frozen CRC/frame/lineage validation is unchanged."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OFFSETS = (0, 7, 19, 640, 641, 719, 839, 840, 999, 1240, 1599, 1600,
           2440, 2559, 2560, 3199, 3200, 4000, 4479, 4480)
ANCHORS = (0, 7, 19)
SCENARIOS = ('valid', 'bad_crc', 'bad_lich', 'mixed', 'one_fsw', 'zero', 'random')
MATRIX = {(s, r, o, c) for s in SCENARIOS for r in (8, 14)
          for o in (OFFSETS if s == 'valid' else (0,)) for c in (1, 37, 512)}
INSPECTOR = 'experiments/nxdn_frames/inspect_frames.py'
INSPECTOR_SHA = 'a26e47b64f09db1810d4d0dbb0c2c8d7e110b1abc248eecf0a634618ab514bc4'
RUNNER = 'experiments/nxdn_frames/run_frames.py'
RUNNER_SHA = '377946ee6bb0047b8390cb6bbe695e461bb3e638c9d699301731dd87624e2757'
ARCHIVE_SHA = 'b46a6433dbf802bca231f70149c0d65d6c6884ac75a0b7ecd58ede7981dd4446'
ADAPTER_INPUTS = ('experiments/nxdn_entry/observer.c', 'experiments/nxdn_entry/CMakeLists.txt',
                  'experiments/nxdn_entry/policy.py', 'experiments/nxdn_entry/run_pair.py',
                  'experiments/nxdn_entry/test_policy.py',
                  'docs/research/NXDN-ENTRY-PREREGISTRATION-2026-09-25.md',
                  'upstream/dsd-neo/include/dsd-neo/core/opts.h')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frozen_namespace(relative, expected):
    path = ROOT / relative
    source = path.read_bytes()
    require(hashlib.sha256(source).hexdigest() == expected, 'Frozen source changed: ' + relative)
    namespace = {'__name__': 'xerax_entry_frozen', '__file__': str(path)}
    exec(compile(source, str(path), 'exec'), namespace)
    return namespace


def inspector():
    namespace = frozen_namespace(INSPECTOR, INSPECTOR_SHA)
    # This is the entire validation change: the allowed absolute input entries.
    namespace['MATRIX'] = MATRIX
    return namespace['analyze']


def output_paths(directory):
    names = ['cases.jsonl', 'stderr.log', 'process.json', 'vectors/vectors.json']
    names += ['vectors/' + v + '.dibits' for v in ('valid', 'wrong_all_crc', 'wrong_lich')]
    names += ['%s-r%d-o%d-c%d.u32le' % row for row in sorted(MATRIX)]
    return [directory / name for name in names]


def runner():
    namespace = frozen_namespace(RUNNER, RUNNER_SHA)
    original_loader = namespace['load_entry']

    def load_entry(source, path, entry):
        function = original_loader(source, path, entry)
        if entry == 'analyze':
            require(hashlib.sha256(source).hexdigest() == INSPECTOR_SHA, 'Inspector bytes changed')
            function.__globals__['MATRIX'] = MATRIX
        return function

    namespace['SOURCE_FILES'] = tuple(namespace['SOURCE_FILES']) + ADAPTER_INPUTS
    namespace['load_entry'] = load_entry
    namespace['output_paths'] = output_paths
    return namespace


def good_frames(case):
    result = {}
    for frame in case['frames']:
        if (frame['source_frame'] is not None and frame['exact_channels']
                and frame['current_proof'] and not frame['source_truncated']
                and frame['expected_variant'] == 'valid'):
            source = frame['source_frame']
            require(source not in result, 'Duplicate successful source-frame identity')
            result[source] = frame['end_consumed']
    return result


def quality(baseline, candidate):
    before = {c['id']: c for c in baseline['cases']}
    after = {c['id']: c for c in candidate['cases']}
    require(set(before) == set(after) and len(before) == 156, 'Incomplete paired grid')
    failures, gains = [], []
    if not candidate['receiver_gate_pass']:
        failures.append({'reason': 'candidate_receiver_gate_failed'})
    for identity, case in before.items():
        b, c = good_frames(case), good_frames(after[identity])
        for source, end in b.items():
            if source not in c or c[source] > end + 20:
                failures.append({'id': identity, 'source_frame': source,
                                 'reason': 'lost_or_delayed_baseline_frame',
                                 'baseline_end': end, 'candidate_end': c.get(source)})
        if case['scenario'] == 'valid':
            # Preserve absent outcomes instead of inventing an infinite speedup.
            gain = min(b.values()) - min(c.values()) if b and c else None
            gains.append({'id': identity, 'baseline_frames': b, 'candidate_frames': c,
                          'first_frame_gain_samples': gain,
                          'first_frame_gain_ms': gain / 48 if gain is not None else None})
    qualifying = []
    by_id = {g['id']: g for g in gains}
    for offset in OFFSETS:
        if offset in ANCHORS:
            continue
        values = [by_id['valid-r%d-o%d-c%d' % (r, offset, c)]['first_frame_gain_samples']
                  for r in (8, 14) for c in (1, 37, 512)]
        if all(v is not None and v >= 3360 for v in values):
            qualifying.append(offset)
    if not qualifying:
        failures.append({'reason': 'no_held_out_offset_meets_registered_gain'})
    return {'progression_pass': not failures, 'failures': failures, 'positive_cases': gains,
            'qualifying_held_out_offsets': qualifying}
