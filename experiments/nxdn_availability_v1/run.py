"""Twenty new once-only candidate processes, after committed source/linkage gates."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET
import analyze
import prepare_inputs as prepare

ROOT=prepare.ROOT
INPUT_SHA='d42a311b1367b0a200dd3c52ab0aaa3bfd292a429785a9ac534ee54348dad98c'
BASELINE='ec712a0869184c0b73ec06b1ce36d3d1bdaf6b04'
HERE=Path(__file__).resolve().parent
LIVE={str(p.resolve()):prepare.sha(p) for folder in (
    HERE,ROOT/'experiments/nxdn_active_boundaries_v1',ROOT/'experiments/nxdn_clear_routing_v1',
    ROOT/'experiments/nxdn_observation_v2') for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
def save(path,value): prepare.save(path,value)
def hashes(folder):
    return {str(p.resolve()):prepare.sha(p) for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
def preserved(group): return all(Path(p).is_file() and prepare.sha(p)==d for p,d in group.items())
def merge_identity(target,source):
    for p,d in source.items():
        prepare.need(p not in target or target[p]==d,'Conflicting identity: '+p); target[p]=d
NATIVE_TEST_NAMES = (
    'xerax_availability_symbol_replay', 'xerax_availability_symbol_replay_no_radio',
    'xerax_availability_symbol_wav', 'xerax_availability_symbol_wav_no_radio',
    'xerax_availability_symbol_live', 'xerax_availability_dibit',
    'NXDN_AVAILABILITY_VOICE', 'NXDN_AVAILABILITY_FRAME',
)
NATIVE_UNIT_FILES = (
    'native-unit-status.json', 'native-unit.log', 'native-unit-status-1.json',
    'native-unit-1.log', 'native-unit-1.xml',
)

def validate_native_units(folder):
    """Bind the pass claim to actual saved CTest cases, not a count-only JSON."""
    paths = {name: Path(folder) / ('nxdn-availability-v1-' + name) for name in NATIVE_UNIT_FILES}
    prepare.need(all(p.is_file() for p in paths.values()), 'Missing saved native-unit evidence')
    raw = {name: p.read_bytes() for name, p in paths.items()}
    prepare.need(raw['native-unit-status.json'] == raw['native-unit-status-1.json'],
                 'Final native-unit status differs from recorded attempt')
    prepare.need(raw['native-unit.log'] == raw['native-unit-1.log'],
                 'Final native-unit log differs from recorded attempt')
    status = analyze.active.truth.strict_json(raw['native-unit-status.json'])
    prepare.need(isinstance(status, dict) and status.get('all_pass') is True,
                 'Native contracts not passed')
    for key, expected in (('test_count', 8), ('exit_code', 0), ('native_receiver_invocations', 0)):
        prepare.need(type(status.get(key)) is int and status[key] == expected,
                     'Invalid native-unit status: ' + key)
    prepare.need(status.get('test_names') == list(NATIVE_TEST_NAMES), 'Native-unit status names differ')
    prepare.need(status.get('xml_sha256') == analyze.digest(raw['native-unit-1.xml']),
                 'Saved native-unit XML hash differs')
    try:
        xml = ET.fromstring(raw['native-unit-1.xml'])
    except ET.ParseError as error:
        raise ValueError('Malformed native-unit XML') from error
    prepare.need(xml.tag == 'testsuite' and xml.get('tests') == '8', 'Native-unit XML suite differs')
    for key in ('failures', 'disabled', 'skipped', 'errors'):
        prepare.need(xml.get(key, '0') == '0', 'Native-unit XML reports ' + key)
    cases = xml.findall('.//testcase')
    prepare.need(len(cases) == 8 and [c.get('name') for c in cases] == list(NATIVE_TEST_NAMES),
                 'Native-unit XML cases differ')
    prepare.need(all(c.get('status') == 'run' for c in cases), 'Native-unit case was not executed')
    prepare.need(not any(e.tag in ('failure', 'error', 'skipped') for e in xml.iter()),
                 'Native-unit case did not pass')
    return {str(p.resolve()): analyze.digest(raw[name]) for name, p in paths.items()}

def completed_preflight_files(folder):
    """Bounded completed preflight artifacts, including failed auditor versions."""
    patterns = ('nxdn-availability-v1-configure*', 'nxdn-availability-v1-build*.log',
                'nxdn-availability-v1-build-audit-*',
                'nxdn-availability-v1-framework-preflight*.log',
                'nxdn-availability-v1-framework-evidence*.log',
                'nxdn-availability-v1-prepare-build-initial.py',
                'nxdn-availability-v1-observer-prototype-failure.c')
    return sorted({p for pattern in patterns for p in Path(folder).glob(pattern) if p.is_file()})

def read_rows(path): return [analyze.active.truth.strict_json(line) for line in path.read_bytes().splitlines()]
def invoke(binary,folder,case,inputs,manifest,enabled):
    folder.mkdir(parents=True,exist_ok=False)
    args=[str(binary),str(inputs/manifest['waveforms'][case['waveform']]['file']),str(case['fast']),str(case['chunk']),str(enabled),str(folder/'pops.u32le')]
    save(folder/'invocation.json',{'arguments':args,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                 'timeout_seconds':60,'dsd_environment_removed':True})
    result={'exit_code':None,'measurement_pass':False}
    try:
        with (folder/'events.jsonl').open('wb') as out,(folder/'stderr.txt').open('wb') as err:
            result['exit_code']=subprocess.run(args,cwd=folder,stdout=out,stderr=err,timeout=60,
                env={k:v for k,v in os.environ.items() if not k.upper().startswith('DSD_')}).returncode
        save(folder/'process.json',{'exit_code':result['exit_code']})
        result['audit']=analyze.inspect(read_rows(folder/'events.jsonl'),folder/'pops.u32le',case,manifest,inputs,enabled)
        result['measurement_pass']=result['exit_code']==0 and result['audit'].get('measurement_pass') is True
    except Exception as error:
        result.update(exception=type(error).__name__,detail=str(error))
        (folder/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
    if not (folder/'process.json').exists(): save(folder/'process.json',{k:result[k] for k in ('exit_code','exception','detail') if k in result})
    save(folder/'audit.json',result)
    return result
def checked_invoke(binary,folder,case,inputs,manifest,enabled,groups):
    prepare.need(all(preserved(g) for g in groups),'Identity changed; abort new native launches')
    return invoke(binary,folder,case,inputs,manifest,enabled)

def run(build,parent,inputs,output):
    output.mkdir(parents=True,exist_ok=False)
    prepare.need(preserved(LIVE),'Loaded source changed')
    prepare.need(prepare.sha(inputs/'manifest.json')==INPUT_SHA,'Frozen copied inputs changed')
    manifest=analyze.validate_inputs(inputs)
    for command in (['git','diff','HEAD','--','experiments/nxdn_availability_v1'],
                    ['git','ls-files','--others','--exclude-standard','experiments/nxdn_availability_v1']):
        prepare.need(not subprocess.check_output(command,cwd=ROOT),'Commit the complete candidate/harness before execution')
    prepare.need(not subprocess.check_output(['git','diff',BASELINE,'--','upstream','patches'],cwd=ROOT),'Product source changed')
    prepare.need(prepare.sha(parent/'report.json')==prepare.ACTIVE_REPORT,'Cached baseline report changed')
    prior=json.loads((parent/'before-execution.json').read_bytes()); historical=json.loads((parent/'report.json').read_bytes())
    protected={}
    for group in ('frozen_files','original_files','copied_identities','configured_sources','protected'):
        merge_identity(protected,prior[group])
    merge_identity(protected,{str((parent/name.replace('\\','/')).resolve()):d for name,d in historical['files'].items()})
    merge_identity(protected,{str((parent/'report.json').resolve()):prepare.ACTIVE_REPORT})
    for name in ('nxdn-active-boundaries-v1-2026-09-25-raw.zip','nxdn-active-boundaries-v1-2026-09-25.json',
                 'nxdn-active-boundaries-v1-publication-audit-2026-09-25.zip'):
        p=ROOT/'docs/research/evidence'/name
        expected=subprocess.check_output(['git','show',BASELINE+':'+p.relative_to(ROOT).as_posix()],cwd=ROOT)
        prepare.need(p.read_bytes()==expected,'Published baseline changed')
        protected[str(p.resolve())]=prepare.sha(p)
    prepare.need(preserved(protected),'Historical preservation failed')
    audit_path=ROOT/'build/nxdn-availability-v1-build-audit.json'
    audit=json.loads(audit_path.read_bytes())
    prepare.need(audit['source_and_linkage_pass'],'Candidate build/linkage audit failed')
    binary=build/'xerax_nxdn_availability_v1.exe'
    prepare.need(prepare.sha(binary)==audit['binary_sha256'],'Candidate executable changed')
    dependencies=audit['dependencies']; runtimes=audit['runtime_files']
    prepare.need(preserved(dependencies) and preserved(runtimes),'Audited dependency/runtime changed')
    unit_evidence=validate_native_units(ROOT/'build')
    originals=hashes(inputs)|hashes(HERE)|LIVE
    merge_identity(originals,protected); merge_identity(originals,dependencies); merge_identity(originals,runtimes)
    merge_identity(originals,unit_evidence)
    frozen=output/'frozen'; frozen.mkdir(); copies={}
    def duplicate(source,target):
        source,target=Path(source).resolve(),Path(target).resolve()
        d=prepare.sha(source); merge_identity(originals,{str(source):d})
        target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(source,target); copies[str(target)]=d
    duplicate(binary,frozen/'engine.exe')
    for p in runtimes: duplicate(p,frozen/Path(p).name)
    for p in inputs.rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts: duplicate(p,output/'inputs'/p.relative_to(inputs))
    for name in ('nxdn_availability_v1','nxdn_active_boundaries_v1','nxdn_clear_routing_v1','nxdn_observation_v2','nxdn_engine_gap','nxdn_frames'):
        for p in (ROOT/'experiments'/name).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts: duplicate(p,frozen/'source_repository'/p.relative_to(ROOT))
    for p in (build/'generated').rglob('*'):
        if p.is_file(): duplicate(p,frozen/'generated'/p.relative_to(build/'generated'))
    for name in ('CMakeCache.txt','compile_commands.json','build.ninja','availability.map','toolchain.cmake'):
        duplicate(build/name,frozen/name)
    for p in build.glob('xerax_*available*.map'): duplicate(p,frozen/'unit-maps'/p.name)
    for p in build.glob('xerax_availability_*.map'): duplicate(p,frozen/'unit-maps'/p.name)
    for name in ('build-audit.py','build-audit.json','build-audit.md','preflight-review.md',
                 'unit.log','unit-optimized.log',
                 'preflight-notes.txt','input-copy.log'):
        p=ROOT/('build/nxdn-availability-v1-'+name); duplicate(p,frozen/p.name)
    for p in unit_evidence:
        duplicate(p,frozen/Path(p).name)
    # Copy only completed preflight artifacts. The live execution log is excluded.
    for p in completed_preflight_files(ROOT/'build'):
        duplicate(p,frozen/'preflight'/p.name)
    for p in (ROOT/'build/nxdn-availability-agent-unit').glob('*'):
        if p.is_file(): duplicate(p,frozen/'frame-voice-unit-preflight'/p.name)
    duplicate(ROOT/'docs/research/NXDN-AVAILABILITY-V1-PREREGISTRATION-2026-09-25.md',frozen/'REGISTRATION.md')
    files=hashes(output)
    save(output/'before-execution.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
         'registration_commit':prepare.REGISTRATION,'source_baseline':BASELINE,'binary_sha256':audit['binary_sha256'],
         'native_invocations_registered':20,'baseline_receiver_rerun':False,'frozen_files':files,'original_files':originals,
         'copied_identities':copies,'configured_sources':dependencies,'protected':protected})
    groups=(files,originals,copies,dependencies,protected,LIVE)
    report={'schema':1,'kind':'nxdn_availability_v1','measurement_pass':False,'targeted_guard_pass':False,
            'progression_pass':False,'product_promotion':False,'attempts':[],'measurement_failures':[]}
    save(output/'report.json',report); pairs={}
    for case in manifest['cases']:
        for enabled in (0,1):
            r=checked_invoke(frozen/'engine.exe',output/'runs'/case['id']/str(enabled),case,output/'inputs',manifest,enabled,groups)
            attempt={'id':case['id'],'observed':enabled,**{k:r.get(k) for k in ('exit_code','measurement_pass','exception','detail')}}
            report['attempts'].append(attempt)
            if r['measurement_pass']: pairs.setdefault(case['id'],{})[enabled]=r['audit']
            else: report['measurement_failures'].append(attempt)
            save(output/'report.json',report)
    report['comparison']=analyze.compare(pairs,manifest)
    report['preservation_pass']=all(preserved(g) for g in groups)
    report['measurement_pass']=len(report['attempts'])==20 and not report['measurement_failures'] and report['preservation_pass'] and report['comparison']['measurement_pass']
    for gate in ('targeted_guard_pass','progression_pass'): report[gate]=bool(report['measurement_pass'] and report['comparison'][gate])
    report['files']={p.relative_to(output).as_posix():prepare.sha(p) for p in output.rglob('*') if p.is_file() and p!=output/'report.json' and '__pycache__' not in p.parts}
    save(output/'report.json',report)
    return report
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('build','parent','inputs','output'): parser.add_argument(name,type=Path)
    args=parser.parse_args()
    if args.output.exists(): parser.error('Existing run is immutable; never retry identities')
    try: report=run(*(getattr(args,n).resolve() for n in ('build','parent','inputs','output')))
    except Exception as error:
        args.output.mkdir(parents=True,exist_ok=True); path=args.output/'report.json'
        report=json.loads(path.read_bytes()) if path.exists() else {}
        report.update(measurement_pass=False,targeted_guard_pass=False,progression_pass=False,exception=type(error).__name__,detail=str(error))
        save(path,report); (args.output/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
    print(json.dumps({k:report.get(k) for k in ('measurement_pass','targeted_guard_pass','progression_pass','detail')},indent=2))
    sys.exit(0 if report['measurement_pass'] else 1)
