"""Run the predeclared pair once; exit zero means valid evidence, not promotion."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
INNER = ROOT / 'experiments/nxdn_frames/run_frames.py'
COMPARER = ROOT / 'experiments/nxdn_first_sync/compare.py'

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path, data): Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8')
def module(path):
    raw = path.read_bytes()
    namespace = {'__name__': 'frozen_pair_module', '__file__': str(path)}
    exec(compile(raw, str(path), 'exec'), namespace)
    return namespace, hashlib.sha256(raw).hexdigest()

def run(baseline_exe, candidate_exe, output_dir, *, frozen_baseline_dir):
    output = Path(output_dir).resolve(); output.mkdir(parents=True, exist_ok=False)
    executables = [Path(value).resolve() for value in (baseline_exe, candidate_exe)]
    frozen_dir = Path(frozen_baseline_dir).resolve()
    result = {'schema': 1, 'started_utc': datetime.now(timezone.utc).isoformat(), 'measurement_pass': False,
              'promotion_pass': False, 'status': 'failed', 'errors': [], 'phases': {}, 'comparison': None,
              'inputs_before': {}, 'inputs_after': {}, 'domain': 'discriminator_samples'}
    inputs = {}
    try:
        inner, inner_sha = module(INNER)
        comparator, comparator_sha = module(COMPARER)
        paths = [ROOT / name for name in inner['SOURCE_FILES']] + [INNER, COMPARER] + executables
        paths += [ROOT / ('experiments/nxdn_first_sync/' + name) for name in
                  ('CMakeLists.txt', 'run_pair.py', 'test_compare.py', 'test_run_pair.py')]
        paths += [ROOT / 'docs/research/NXDN-FIRST-SYNC-PREREGISTRATION-2026-09-25.md']
        paths += [p for p in frozen_dir.rglob('*') if p.is_file()]
        inputs = {str(path): digest(path) for path in paths}
        if inputs[str(INNER)] != inner_sha or inputs[str(COMPARER)] != comparator_sha:
            raise ValueError('Module changed during loading')
        if executables[0] == executables[1] or inputs[str(executables[0])] == inputs[str(executables[1])]:
            raise ValueError('Distinct candidate binary required')
        result['inputs_before'] = inputs
        save(output / 'manifest-before.json', {'inputs': inputs, 'started_utc': result['started_utc']})
        def stable():
            if any(digest(path) != expected for path, expected in inputs.items()):
                raise ValueError('Frozen pair input changed')
        frozen = comparator['load_run'](frozen_dir)
        for name, executable in zip(('baseline', 'candidate'), executables):
            stable()
            report = inner['run'](executable, output / name)
            result['phases'][name] = {'status': report['status'], 'measurement_pass': report['measurement_pass'],
                                     'receiver_gate_pass': report['receiver_gate_pass']}
            stable()
            if not report['measurement_pass']:
                raise ValueError(name + ' measurement failed')
            if name == 'baseline':
                comparator['baseline_matches'](comparator['load_run'](output / name), frozen)
        comparison = comparator['compare'](output / 'baseline', output / 'candidate', frozen_baseline_dir=frozen_dir)
        save(output / 'comparison.json', comparison)
        result['comparison'] = comparison
        stable()
        result['measurement_pass'] = comparison['evidence_valid'] is True
        result['promotion_pass'] = comparison['promotion_pass'] is True
        result['status'] = 'measured_candidate_passed' if result['promotion_pass'] else 'measured_candidate_rejected'
    except Exception as exc:
        result['errors'].append(type(exc).__name__ + ': ' + str(exc))
    finally:
        for path, expected in inputs.items():
            try: actual = digest(path)
            except OSError: actual = None
            result['inputs_after'][path] = actual
            if actual != expected:
                result['errors'].append('Input drift: ' + path)
        if result['errors']:
            result['measurement_pass'] = result['promotion_pass'] = False
            result['status'] = 'failed'
        save(output / 'report.json', result)
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path); parser.add_argument('candidate', type=Path)
    parser.add_argument('output', type=Path); parser.add_argument('--frozen-baseline-dir', type=Path, required=True)
    args = parser.parse_args()
    try: result = run(args.baseline, args.candidate, args.output, frozen_baseline_dir=args.frozen_baseline_dir)
    except OSError as exc:
        print(str(exc), file=sys.stderr); return 2
    print(json.dumps({key: result[key] for key in ('status', 'measurement_pass', 'promotion_pass', 'errors')}))
    return 0 if result['measurement_pass'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
