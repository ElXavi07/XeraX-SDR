"""Reuse the frozen recorder for 16 new once-only boundary identities."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

import analyze
import prepare

ROOT = prepare.ROOT
LIVE = {str(Path(p).resolve()): prepare.sha(p) for p in
        (__file__, analyze.__file__, prepare.__file__, Path(__file__).with_name('source_truth.py'),
         ROOT / 'experiments/nxdn_clear_routing_v1/analyze.py',
         ROOT / 'experiments/nxdn_clear_routing_v1/source_truth.py',
         ROOT / 'experiments/nxdn_clear_routing_v1/prepare.py',
         ROOT / 'experiments/nxdn_observation_v2/analyze.py')}
INPUT_SHA = '899bc2f55403b4b5f465dfbf8939d3dc396e86d197feef86654d3a6529b7a0c6'

def save(path, value): prepare.save(path, value)

def hashes(folder):
    return {str(p.resolve()): prepare.sha(p) for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts}

def preserved(group):
    return all(Path(p).is_file() and prepare.sha(p) == digest for p, digest in group.items())

def unique(pairs):
    result = {}
    for key, value in pairs:
        prepare.require(key not in result, 'Duplicate JSON field: ' + key); result[key] = value
    return result

def nonfinite(value): raise ValueError('Nonfinite JSON token: ' + value)

def read_rows(path):
    return [json.loads(line, object_pairs_hook=unique, parse_constant=nonfinite)
            for line in path.read_text(encoding='utf-8').splitlines()]

def invoke(binary, folder, case, inputs, manifest, enabled):
    folder.mkdir(parents=True, exist_ok=False)
    args = [str(binary), str(inputs / manifest['waveforms'][case['waveform']]['file']),
            str(case['fast']), str(case['chunk']), str(enabled), str(folder / 'pops.u32le')]
    save(folder / 'invocation.json', {'arguments': args, 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                    'timeout_seconds': 60, 'dsd_environment_removed': True})
    result = {'exit_code': None, 'measurement_pass': False}
    try:
        with (folder / 'events.jsonl').open('wb') as out, (folder / 'stderr.txt').open('wb') as err:
            result['exit_code'] = subprocess.run(args, cwd=folder, stdout=out, stderr=err, timeout=60,
                env={k: v for k, v in os.environ.items() if not k.upper().startswith('DSD_')}).returncode
        save(folder / 'process.json', {'exit_code': result['exit_code']})
        result['audit'] = analyze.inspect(read_rows(folder / 'events.jsonl'), folder / 'pops.u32le', case, manifest, inputs, enabled)
        result['measurement_pass'] = result['exit_code'] == 0 and result['audit'].get('measurement_pass') is True
    except Exception as error:
        result.update(exception=type(error).__name__, detail=str(error))
        (folder / 'failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
    if not (folder / 'process.json').exists():
        save(folder / 'process.json', {k: result[k] for k in ('exit_code', 'exception', 'detail') if k in result})
    save(folder / 'audit.json', result)
    return result

def checked_invoke(binary, folder, case, inputs, manifest, enabled, groups):
    prepare.require(all(preserved(group) for group in groups), 'Pre-launch identity changed; no native invocation')
    return invoke(binary, folder, case, inputs, manifest, enabled)

def merge_identity(target, source):
    for name, digest in source.items():
        prepare.require(name not in target or target[name] == digest, 'Conflicting historical identity: ' + name)
        target[name] = digest

def run(parent, inputs, output):
    output.mkdir(parents=True, exist_ok=False)
    prepare.require(preserved(LIVE), 'Loaded execution source changed')
    prepare.require(prepare.sha(inputs / 'manifest.json') == INPUT_SHA, 'Registered input corpus changed')
    manifest = analyze.validate_inputs(inputs)
    prepare.require(len(manifest['cases']) == 8 and len(manifest['waveforms']) == 4, 'Wrong new matrix')
    prepare.require(all(c['fast'] == 1 for c in manifest['cases']), 'Public acquisition option changed')
    for command in (['git', 'diff', 'HEAD', '--', 'experiments/nxdn_active_boundaries_v1'],
                    ['git', 'ls-files', '--others', '--exclude-standard', 'experiments/nxdn_active_boundaries_v1']):
        prepare.require(not subprocess.check_output(command, cwd=ROOT), 'Commit complete harness before execution')
    prepare.require(not subprocess.check_output(['git', 'diff', prepare.BASELINE, '--', 'upstream', 'patches'], cwd=ROOT), 'Product source changed')
    prepare.require(prepare.sha(parent / 'report.json') == prepare.PARENT_REPORT, 'Historical report changed')
    prior_report = json.loads((parent / 'report.json').read_bytes())
    prepare.require(prior_report['measurement_pass'] and prior_report['preservation_pass'] and not prior_report['progression_pass'], 'Historical outcome changed')
    for name, digest in prior_report['files'].items():
        prepare.require(prepare.sha(prepare.packed_path(parent, name)) == digest, 'Historical trace changed: ' + name)
    prior = json.loads((parent / 'before-execution.json').read_bytes())
    protected = {}
    historical_counts = {}
    for group in ('frozen_files', 'original_files', 'copied_identities', 'configured_sources', 'protected'):
        historical_counts[group] = len(prior[group]); merge_identity(protected, prior[group])
    merge_identity(protected, {str(prepare.packed_path(parent, name)): digest for name, digest in prior_report['files'].items()})
    for relative, digest in {
        'docs/research/evidence/nxdn-clear-routing-v1-2026-09-25.json': prepare.PARENT_INDEX,
        'docs/research/evidence/nxdn-clear-routing-v1-2026-09-25-raw.zip': prepare.PARENT_ARCHIVE}.items():
        merge_identity(protected, {str((ROOT / relative).resolve()): digest})
    merge_identity(protected, {str((parent / 'report.json').resolve()): prepare.PARENT_REPORT})
    prepare.require(preserved(protected), 'Historical source/runtime/release identity changed')
    binary = parent / 'frozen/engine.exe'
    prepare.require(prepare.sha(binary) == prepare.BINARY, 'Reused executable changed')
    build_audit = json.loads((parent / 'frozen/nxdn-clear-routing-v1-build-audit.json').read_bytes())
    prepare.require(build_audit['source_and_linkage_pass'] and build_audit['binary_sha256'] == prepare.BINARY,
                    'Reused real decoder linkage is unproven')
    prepare.require(preserved(build_audit['dependencies']) and preserved(build_audit['runtime_files']), 'Audited build/runtime source changed')
    originals = hashes(inputs) | hashes(Path(__file__).parent) | LIVE
    merge_identity(originals, protected)
    frozen = output / 'frozen'; frozen.mkdir()
    copies = {}
    def copy(source, target):
        source, target = Path(source).resolve(), Path(target).resolve()
        expected = originals.setdefault(str(source), prepare.sha(source))
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, target)
        copies[str(target)] = expected
    for source, destination in ((parent / 'frozen', frozen / 'receiver'), (inputs, output / 'inputs')):
        for p in source.rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts: copy(p, destination / p.relative_to(source))
    skeleton = frozen / 'source_repository'
    for name in ('nxdn_active_boundaries_v1', 'nxdn_clear_routing_v1', 'nxdn_observation_v2', 'nxdn_engine_gap', 'nxdn_frames'):
        base = ROOT / 'experiments' / name
        for p in base.iterdir():
            if p.is_file(): copy(p, skeleton / p.relative_to(ROOT))
    registration = ROOT / 'docs/research/NXDN-ACTIVE-BOUNDARIES-V1-PREREGISTRATION-2026-09-25.md'
    copy(registration, frozen / registration.name)
    # Only named, completed preflight records: never glob a live result audit/log.
    for name in ('plan-review.md', 'source-audit.md', 'preflight-review.md',
                 'unit.log', 'unit-optimized.log', 'input-generation.log'):
        p = ROOT / ('build/nxdn-active-boundaries-v1-' + name); copy(p, frozen / p.name)
    configured = prior['configured_sources']
    files = hashes(output)
    save(output / 'before-execution.json', {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'registration_commit': prepare.REGISTRATION, 'source_baseline': prepare.BASELINE,
        'receiver_product_baseline': '289a82f8fd9c0495b64bf948fd45413bc63261c4',
        'receiver_rebuilt': False, 'native_invocations_registered': 16, 'binary_sha256': prepare.BINARY,
        'prior_group_counts': historical_counts, 'frozen_files': files, 'original_files': originals,
        'copied_identities': copies, 'configured_sources': configured, 'protected': protected,
        'configured_scope': 'Unchanged prior configured sources; no compilation occurred in this experiment.'})
    report = {'schema': 1, 'kind': 'nxdn_active_boundaries_v1', 'measurement_pass': False,
        'progression_pass': False, 'product_promotion': False, 'attempts': [], 'measurement_failures': []}
    save(output / 'report.json', report)
    groups = (files, originals, copies, configured, protected, LIVE)
    pairs = {}; frozen_inputs = output / 'inputs'
    for case in manifest['cases']:
        for enabled in (0, 1):
            result = checked_invoke(frozen / 'receiver/engine.exe', output / 'runs' / case['id'] / str(enabled),
                                    case, frozen_inputs, manifest, enabled, groups)
            report['attempts'].append({'id': case['id'], 'observed': enabled,
                                      **{k: result.get(k) for k in ('exit_code', 'measurement_pass', 'exception', 'detail')}})
            if result['measurement_pass']: pairs.setdefault(case['id'], {})[enabled] = result['audit']
            else: report['measurement_failures'].append(report['attempts'][-1])
            save(output / 'report.json', report)
    report['comparison'] = analyze.compare(pairs, manifest)
    report['preservation_pass'] = all(preserved(group) for group in groups)
    report['measurement_pass'] = len(report['attempts']) == 16 and not report['measurement_failures'] and report['preservation_pass'] and report['comparison'].get('measurement_pass') is True
    report['progression_pass'] = report['measurement_pass'] and report['comparison'].get('progression_pass') is True
    report['files'] = {p.relative_to(output).as_posix(): prepare.sha(p) for p in output.rglob('*')
                       if p.is_file() and p != output / 'report.json' and '__pycache__' not in p.parts}
    save(output / 'report.json', report)
    return report

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'inputs', 'output'): parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.output.exists(): parser.error('Existing run directory is immutable')
    try:
        report = run(*(getattr(args, name).resolve() for name in ('parent', 'inputs', 'output')))
    except Exception as error:
        args.output.mkdir(parents=True, exist_ok=True); path = args.output / 'report.json'
        report = json.loads(path.read_bytes()) if path.exists() else {}
        report.update(measurement_pass=False, progression_pass=False, exception=type(error).__name__, detail=str(error))
        save(path, report); (args.output / 'failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
    print(json.dumps({'measurement_pass': report['measurement_pass'], 'progression_pass': report['progression_pass'],
                      'attempts': len(report.get('attempts', [])), 'detail': report.get('detail')}))
    sys.exit(0 if report['measurement_pass'] else 1)
