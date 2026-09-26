"""Freeze and execute each registered clear-routing identity once, retaining failures."""
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
BASELINE = '289a82f8fd9c0495b64bf948fd45413bc63261c4'
INPUT_SHA = '6ca26a31598d8bb9d701bb9f6eba19d783de7e00a3e0730be2ccd3f0b20b12eb'
LIVE = {str(Path(p).resolve()): prepare.sha(p) for p in
        (__file__, analyze.__file__, prepare.__file__, analyze.FINITE_PATH,
         Path(analyze.__file__).with_name('source_truth.py'))}

def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')

def hashes(folder):
    return {str(p.resolve()): prepare.sha(p) for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts}

def preserved(group):
    return all(Path(p).is_file() and prepare.sha(p) == digest for p, digest in group.items())

def unique(pairs):
    result = {}
    for name, value in pairs:
        prepare.require(name not in result, 'Duplicate JSON field: ' + name)
        result[name] = value
    return result

def nonfinite(value):
    raise ValueError('Nonfinite JSON token: ' + value)

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
        save(folder / 'process.json', {'exit_code': result['exit_code']})  # Preserve attempt before checker code.
        rows = read_rows(folder / 'events.jsonl')
        result['audit'] = analyze.inspect(rows, folder / 'pops.u32le', case, manifest, inputs, enabled)
        result['measurement_pass'] = result['exit_code'] == 0 and result['audit'].get('measurement_pass') is True
    except Exception as error:
        result.update(exception=type(error).__name__, detail=str(error))
        (folder / 'failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
    if not (folder / 'process.json').exists():
        save(folder / 'process.json', {key: value for key, value in result.items()
                                     if key in ('exit_code', 'exception', 'detail')})
    save(folder / 'audit.json', result)
    return result

def checked_invoke(binary, folder, case, inputs, manifest, enabled, groups):
    prepare.require(all(preserved(group) for group in groups), 'Pre-launch identity changed; no native invocation')
    return invoke(binary, folder, case, inputs, manifest, enabled)

def run(build, inputs, output):
    output.mkdir(parents=True, exist_ok=False)
    prepare.require(preserved(LIVE), 'Imported execution source changed')
    prepare.require(prepare.sha(inputs / 'manifest.json') == INPUT_SHA, 'Registered corpus changed')
    manifest = analyze.validate_inputs(inputs)
    prepare.require(len(manifest['cases']) == 18 and len(manifest['waveforms']) == 8, 'Matrix dimensions differ')
    for command in (['git', 'diff', 'HEAD', '--', 'experiments/nxdn_clear_routing_v1'],
                    ['git', 'ls-files', '--others', '--exclude-standard', 'experiments/nxdn_clear_routing_v1']):
        prepare.require(not subprocess.check_output(command, cwd=ROOT), 'Freeze committed harness before execution')
    prepare.require(not subprocess.check_output(['git', 'diff', BASELINE, '--', 'upstream', 'patches'], cwd=ROOT), 'Product source changed')
    audit_path = ROOT / 'build/nxdn-clear-routing-v1-build-audit.json'
    audit_sha = prepare.sha(audit_path); audit = json.loads(audit_path.read_bytes())
    prepare.require(audit['source_and_linkage_pass'], 'Source/linkage audit failed')
    dependencies = audit['dependencies']; runtime = audit['runtime_files']
    prepare.require(preserved(dependencies) and preserved(runtime), 'Audited dependency changed')
    binary = build / 'xerax_nxdn_clear_routing_v1.exe'
    prepare.require(prepare.sha(binary) == audit['binary_sha256'], 'Audited receiver binary changed')
    originals = hashes(inputs) | hashes(build / 'generated') | hashes(Path(__file__).parent) | dependencies | runtime | LIVE
    originals[str(audit_path.resolve())] = audit_sha
    originals[str(binary.resolve())] = audit['binary_sha256']
    previous = json.loads((ROOT / 'build/nxdn-air-v1-run-20260925/before-execution.json').read_bytes())
    protected = previous['protected'].copy()
    for relative, digest in {
        'docs/research/evidence/nxdn-air-v1-2026-09-25-raw.zip': '08947807e6320512828a3cc988727c159175c25a56cd0a74fec38e3001766dd0',
        'docs/research/evidence/nxdn-air-v1-2026-09-25.json': prepare.AIR_INDEX,
        'build/nxdn-air-v1-run-20260925/report.json': prepare.AIR_REPORT}.items():
        protected[str((ROOT / relative).resolve())] = digest
    prepare.require(preserved(protected), 'Earlier release or research changed')
    frozen = output / 'frozen'; frozen.mkdir()
    copies = {}
    def copy(source, target):
        source = Path(source).resolve(); target = Path(target).resolve()
        expected = originals.setdefault(str(source), prepare.sha(source))
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, target)
        copies[str(target)] = expected
    copy(binary, frozen / 'engine.exe')
    for p in runtime: copy(p, frozen / Path(p).name)
    for name in ('CMakeCache.txt', 'compile_commands.json', 'build.ninja', 'clear-routing.map', 'toolchain.cmake'):
        copy(build / name, frozen / name)
    for source, destination in ((inputs, output / 'inputs'), (build / 'generated', frozen / 'generated')):
        for p in source.rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts: copy(p, destination / p.relative_to(source))
    # Preserve the repository hierarchy so the checker can hash/load its finite
    # helper without referring to the original study-machine working directory.
    skeleton = frozen / 'source_repository'
    for directory in ('nxdn_clear_routing_v1', 'nxdn_observation_v2', 'nxdn_engine_gap', 'nxdn_frames'):
        base = ROOT / 'experiments' / directory
        for p in base.iterdir():
            if p.is_file(): copy(p, skeleton / p.relative_to(ROOT))
    registration = ROOT / 'docs/research/NXDN-CLEAR-ROUTING-V1-PREREGISTRATION-2026-09-25.md'
    copy(registration, frozen / registration.name)
    failed_build = ROOT / 'build/nxdn-clear-routing-v1-preflight-build-failure'
    for p in failed_build.rglob('*'):
        if p.is_file(): copy(p, frozen / 'preflight-build-failure' / p.relative_to(failed_build))
    copy(ROOT / 'build/nxdn-clear-routing-v1-preflight-corrections.log', frozen / 'preflight-corrections.log')
    # Explicit completed preflight files only. The currently written outer log
    # is never placed in a pre-execution preservation group.
    for pattern in ('nxdn-clear-routing-v1-*audit*', 'nxdn-clear-routing-v1-*review*',
                    'nxdn-clear-routing-v1-*-plan.md', 'nxdn-clear-routing-v1-prepare-unit*.log',
                    'nxdn-clear-routing-v1-input-generation.log', 'nxdn-clear-routing-v1-configure*.log',
                    'nxdn-clear-routing-v1-build*.log', 'nxdn-clear-routing-v1-unit*.log'):
        for p in (ROOT / 'build').glob(pattern):
            if p.is_file(): copy(p, frozen / p.name)
    configured = {str(Path(c['file']).resolve()): prepare.sha(c['file'])
                  for c in json.loads((build / 'compile_commands.json').read_bytes())}
    inputs = output / 'inputs'
    files = hashes(output)
    save(output / 'before-execution.json', {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'product_baseline': BASELINE, 'frozen_files': files, 'original_files': originals,
        'copied_identities': copies, 'configured_sources': configured, 'protected': protected,
        'configured_scope': 'All compile_commands entries, including configured targets not built by this experiment.',
        'binary_sha256': audit['binary_sha256'], 'build_audit_sha256': audit_sha})
    report = {'schema': 1, 'kind': 'nxdn_clear_routing_v1', 'measurement_pass': False,
        'progression_pass': False, 'product_promotion': False, 'attempts': [], 'measurement_failures': []}
    save(output / 'report.json', report)
    pairs = {}; launch_groups = (files, originals, configured, protected, copies, LIVE)
    for case in manifest['cases']:
        for enabled in (0, 1):
            folder = output / 'runs' / case['id'] / str(enabled)
            result = checked_invoke(frozen / 'engine.exe', folder, case, inputs, manifest, enabled, launch_groups)
            report['attempts'].append({'id': case['id'], 'observed': enabled,
                **{k: result.get(k) for k in ('exit_code', 'measurement_pass', 'exception', 'detail')}})
            if result['measurement_pass']:
                pairs.setdefault(case['id'], {})[enabled] = result['audit']
            else:
                report['measurement_failures'].append({'id': case['id'], 'observed': enabled,
                    'exit_code': result['exit_code'], 'detail': result.get('detail')})
            save(output / 'report.json', report)
    report['comparison'] = analyze.compare(pairs, manifest)
    report['preservation_pass'] = all(preserved(group) for group in launch_groups)
    report['measurement_pass'] = (len(report['attempts']) == 36 and report['preservation_pass']
        and not report['measurement_failures'] and report['comparison'].get('measurement_pass') is True)
    report['progression_pass'] = report['measurement_pass'] and report['comparison'].get('progression_pass') is True
    report['files'] = {str(p.relative_to(output)): prepare.sha(p) for p in output.rglob('*')
                       if p.is_file() and p != output / 'report.json'}
    save(output / 'report.json', report)
    return report

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('build', 'inputs', 'output'): parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.output.exists(): parser.error('Existing run directory is immutable')
    try:
        report = run(*(getattr(args, name).resolve() for name in ('build', 'inputs', 'output')))
    except Exception as error:
        args.output.mkdir(parents=True, exist_ok=True); path = args.output / 'report.json'
        report = json.loads(path.read_bytes()) if path.exists() else {}
        report.update(measurement_pass=False, progression_pass=False, exception=type(error).__name__, detail=str(error))
        save(path, report); (args.output / 'failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
    print(json.dumps({'measurement_pass': report['measurement_pass'], 'progression_pass': report['progression_pass'],
                      'attempts': len(report.get('attempts', [])), 'detail': report.get('detail')}))
    sys.exit(0 if report['measurement_pass'] else 1)
