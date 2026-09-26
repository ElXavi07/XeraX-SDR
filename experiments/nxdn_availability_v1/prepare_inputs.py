"""Copy immutable registered inputs and cached baseline traces; no generation."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
REGISTRATION = '76e175aef1b8f30431c07cb3d4a50d431b858c02'
ACTIVE_REPORT = '058cf74cb23a390d0815e20ae0a2faeb8cf8e2c4e2c4fee98beb04ac290864db'
ACTIVE_MANIFEST = '899bc2f55403b4b5f465dfbf8939d3dc396e86d197feef86654d3a6529b7a0c6'
NAMES = ('active_prefix_6159','active_prefix_6160','active_prefix_6161','active_bad_lich','cold_clean')
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def need(ok, reason):
    if not ok: raise ValueError(reason)
def save(path, value): Path(path).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
def prepare(parent, output):
    need(not output.exists(),'Existing candidate corpus is immutable')
    need(sha(parent/'report.json') == ACTIVE_REPORT,'Frozen baseline report changed')
    report = json.loads((parent/'report.json').read_bytes())
    inventory = {k.replace('\\','/'):v for k,v in report['files'].items()}
    need(report['measurement_pass'] and report['preservation_pass'] and not report['progression_pass'],'Frozen baseline outcome changed')
    for name,digest in inventory.items(): need(sha(parent/name)==digest,'Frozen baseline file changed: '+name)
    need(sha(parent/'inputs/manifest.json')==ACTIVE_MANIFEST,'Frozen active inputs changed')
    output.mkdir(parents=True)
    references={}
    def duplicate(source,target):
        target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(source,target)
        references[target.relative_to(output).as_posix()] = sha(source)
    for p in (parent/'inputs').rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts: duplicate(p,output/'active'/p.relative_to(parent/'inputs'))
    for p in (parent/'runs').rglob('*'):
        if p.is_file(): duplicate(p,output/'baseline-active'/p.relative_to(parent/'runs'))
    duplicate(parent/'report.json',output/'baseline-active-report.json')
    duplicate(parent/'before-execution.json',output/'baseline-active-before.json')
    active=json.loads((output/'active/manifest.json').read_bytes())
    old=json.loads((output/'active/parent/manifest.json').read_bytes())
    waves={}
    for name in NAMES:
        original=old['waveforms']['cold'] if name=='cold_clean' else active['waveforms'][name]
        prefix='active/parent/' if name=='cold_clean' else 'active/'
        wave=copy.deepcopy(original)
        for key in ('file','lineage_file','occurrence_file','original_file'):
            if key in wave: wave[key]=prefix+wave[key]
        waves[name]=wave
    manifest={'schema':1,'kind':'nxdn_availability_v1','registration_commit':REGISTRATION,
              'source_baseline':'ec712a0869184c0b73ec06b1ce36d3d1bdaf6b04','input_domain':'discriminator_samples',
              'rate_hz':48000,'samples_per_symbol':20,'native_invocations':20,'input_generation':False,
              'recipe_sha256':sha(__file__),'reference_files':references,'waveforms':waves,
              'cases':[{'id':f'{name}-c{chunk}','configuration':name,'waveform':name,'chunk':chunk,'fast':1}
                       for name in NAMES for chunk in (37,512)]}
    save(output/'manifest.json',manifest)
    return manifest
if __name__=='__main__':
    if len(sys.argv)!=3: raise SystemExit('usage: prepare_inputs.py ACTIVE_STUDY NEW_INPUT_DIRECTORY')
    result=prepare(Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve())
    print(json.dumps({'cases':len(result['cases']),'generated_samples':False,'manifest_sha256':sha(Path(sys.argv[2])/'manifest.json')}))
