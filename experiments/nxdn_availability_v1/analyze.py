"""Independent candidate gates layered on frozen source/sample ownership checks."""
import copy
import hashlib
import json
from pathlib import Path
import types

ROOT=Path(__file__).resolve().parents[2]
PARENT_PATH=ROOT/'experiments/nxdn_active_boundaries_v1/analyze.py'
PARENT_SHA='a52ae5615712b9ade79589e342bb154f9a42e7bac07e54b71bed1908b504a690'
raw=PARENT_PATH.read_bytes()
if hashlib.sha256(raw).hexdigest()!=PARENT_SHA: raise ValueError('Frozen parent checker changed')
active=types.ModuleType('frozen_availability_active'); active.__file__=str(PARENT_PATH)
exec(compile(raw,str(PARENT_PATH),'exec'),active.__dict__)
base=active.base; require=base.require
NAMES=active.SCENARIOS+('cold_clean',)
def digest(raw): return hashlib.sha256(raw).hexdigest()
def expected_cases():
    return [{'id':f'{name}-c{chunk}','configuration':name,'waveform':name,'chunk':chunk,'fast':1}
            for name in NAMES for chunk in (37,512)]
def read(root,name): return active.truth.strict_json(active.truth.read_file(root,name))
def validate_inputs(inputs):
    inputs=Path(inputs); manifest=read(inputs,'manifest.json')
    require((manifest['schema'],manifest['kind'],manifest['registration_commit'],manifest['source_baseline'],manifest['input_domain'],
             manifest['rate_hz'],manifest['samples_per_symbol'],manifest['native_invocations'],manifest['input_generation'])==
            (1,'nxdn_availability_v1','76e175aef1b8f30431c07cb3d4a50d431b858c02','ec712a0869184c0b73ec06b1ce36d3d1bdaf6b04',
             'discriminator_samples',48000,20,20,False),'Registered input scope changed')
    require(manifest['cases']==expected_cases() and set(manifest['waveforms'])==set(NAMES),'Registered input grid changed')
    parent=active.validate_inputs(inputs/'active')
    original=read(inputs/'active/parent','manifest.json')
    report_raw=active.truth.read_file(inputs,'baseline-active-report.json','058cf74cb23a390d0815e20ae0a2faeb8cf8e2c4e2c4fee98beb04ac290864db')
    report=active.truth.strict_json(report_raw)
    require(report['measurement_pass'] and report['preservation_pass'] and not report['progression_pass'],'Prior failed result changed')
    refs={'baseline-active-report.json':digest(report_raw)}
    for name,d in report['files'].items():
        name=name.replace('\\','/')
        if name.startswith('inputs/'): refs['active/'+name[7:]]=d
        elif name.startswith('runs/'): refs['baseline-active/'+name[5:]]=d
        elif name=='before-execution.json': refs['baseline-active-before.json']=d
    require(refs==manifest['reference_files'],'Copied reference inventory changed')
    for name,d in refs.items(): active.truth.read_file(inputs,name,d)
    for name in NAMES:
        wave=copy.deepcopy(original['waveforms']['cold'] if name=='cold_clean' else parent['waveforms'][name])
        prefix='active/parent/' if name=='cold_clean' else 'active/'
        for key in ('file','lineage_file','occurrence_file','original_file'):
            if key in wave: wave[key]=prefix+wave[key]
        require(manifest['waveforms'][name]==wave,'Copied waveform metadata changed')
    require(digest(Path(__file__).with_name('prepare_inputs.py').read_bytes())==manifest['recipe_sha256'],'Copy recipe changed')
    return manifest

def explicit_availability(audit):
    """The new API's status must agree with independent delivered-sample evidence."""
    issues=[]
    for frame in audit['frames']:
        available=[]
        for call,kind in zip(frame['end']['body_calls'],frame['classes']):
            value=base.integer(call.get('available'),0,1,'explicit read availability')
            require(value==int(kind=='complete'),'Checked API availability contradicts actual symbol delivery')
            available.append(value)
        for route in frame['routes']:
            slot=route['begin']['slot']; indices=range(38+36*slot,74+36*slot)
            permitted=len(available)==182 and all(available[i] for i in indices)
            mask=base.integer(route['begin'].get('available_slots'),0,15,'voice availability mask')
            require(route['end'].get('available_slots')==mask,'Voice mask changed across real route')
            expected=sum(1<<s for s in base.SLOTS[route['begin']['voice']]
                         if len(available)==182 and all(available[i] for i in range(38+36*s,74+36*s)))
            require(mask==expected,'Masked voice entry contradicts independent complete-slot map')
            if not permitted or not(mask&(1<<slot)):
                issues.append({'reason':'unavailable_slot_reaches_processing','frame':frame['begin']['frame'],'slot':slot})
    return issues

def remove_added_observation(rows):
    """Only the three registered additive telemetry fields differ from baseline."""
    out=copy.deepcopy(rows)
    for row in out:
        row.pop('availability_schema',None); row.pop('available_slots',None)
        for call in row.get('body_calls',[]): call.pop('available',None)
    return out

def compare_complete_baseline(rows,baseline_rows):
    return base.semantic(remove_added_observation(rows))==base.semantic(baseline_rows)

def inspect(rows,trace_path,case,manifest,inputs,enabled):
    require(case in expected_cases() and manifest['cases']==expected_cases(),'Unregistered candidate identity')
    require(rows[0].get('availability_schema')==1,'Missing actual checked API observer')
    _,oracle=active.truth.parent_truth(Path(inputs)/'active',base)
    wave=manifest['waveforms'][case['waveform']]
    audit=base.inspect_evidence(rows,Path(trace_path).read_bytes(),case,wave,oracle,enabled)
    guard_issues=explicit_availability(audit)
    name=case['configuration']
    if name!='cold_clean':
        audit.update(active.assess(audit,wave,oracle,enabled,name))
        baseline_stem=Path(inputs)/'baseline-active'/case['id']/str(enabled)
    else:
        baseline_stem=Path(inputs)/'active/anchors'/f"cold_fast-c{case['chunk']}"/str(enabled)
        expected=[(s['ordinal'],v['slot'],v['source_id']) for s in wave['frames']
                  for v in oracle['vectors'][s['vector']]['transmitted_voice']]
        actual=[(v['ordinal'],v['slot'],v['source_id']) for v in audit['source_occurrences']]
        require(len(expected)==24,'Clean source oracle changed')
        audit.update({'exposure_pass':True,'retention_pass':actual==expected and all(v['exact'] for v in audit['source_occurrences']),
                      'exposure_issues':[],'retention_issues':[],'negative_issues':audit['negative_issues']})
        header=[f for f in audit['frames'] if f['source'] and f['source']['ordinal']==0 and f['fully_sampled']]
        trailer=[f for f in audit['frames'] if f['source'] and f['source']['ordinal']==8 and f['fully_sampled']]
        audit['exposure_pass']=len(header)==len(trailer)==1 and active.good_call(header[0]['end'].get('call'))
        if audit['exposure_pass']:
            h=header[0]['end']['call']; t=trailer[0]['end'].get('call')
            audit['retention_pass'] &= t is not None and (t['epoch'],t['phase'],t['end_reason'],t['source'],t['target'],t['crypto'])==(h['epoch'],2,3,901,1201,1)
    baseline_rows=[active.truth.strict_json(line) for line in (baseline_stem/'events.jsonl').read_bytes().splitlines()]
    unchanged = compare_complete_baseline(rows,baseline_rows) if name in ('cold_clean','active_bad_lich') else None
    if unchanged is False: guard_issues.append({'reason':'complete_input_changed_cached_receiver_outcomes'})
    if name.startswith('active_prefix_'):
        wanted=0 if name.endswith('6159') else 1
        if audit['summary']['fec_outer_calls']!=wanted or audit['summary']['synthesis_calls']!=wanted:
            guard_issues.append({'reason':'prefix_processing_count','expected':wanted})
        if wanted==0:
            target=[f for f in audit['frames'] if f['lich_source'] and f['lich_source']['ordinal']==1]
            if not target or target[0]['end'].get('call',{}).get('media_active')!=0 or target[0]['end']['audio_indices']!=target[0]['begin']['audio_indices']:
                guard_issues.append({'reason':'unavailable_only_frame_changed_media_or_audio'})
    safe=audit['finite_voice_safety_pass'] and not guard_issues
    required_retention=audit['retention_pass'] if name!='active_bad_lich' else unchanged is True
    audit.update(availability_guard_pass=bool(safe and audit['routing_pass'] and audit['exposure_pass'] and audit['negative_pass'] and required_retention),
                 guard_issues=guard_issues,complete_input_baseline_equal=unchanged,
                 product_promotion=False)
    return audit

def compare(pairs,manifest):
    issues=[]; required=expected_cases(); gates={k:True for k in ('routing_pass','exposure_pass','retention_pass','negative_pass','finite_voice_safety_pass','availability_guard_pass')}
    if manifest.get('cases')!=required or set(pairs)!={c['id'] for c in required}: issues.append('changed_or_incomplete_grid')
    normalized={}
    for case in required:
        values=pairs.get(case['id'],{})
        if len(values)!=2 or {str(k) for k in values}!={'0','1'}: issues.append('missing_detail_pair:'+case['id']); continue
        roles={int(k):v for k,v in values.items()}
        normalized[case['id']]=roles
        for mode,a in roles.items():
            if a.get('case')!=case or a.get('summary',{}).get('observed')!=mode or not a.get('measurement_pass'): issues.append('wrong_audit_identity:'+case['id'])
            for key in gates: gates[key] &= a.get(key) is True
        if roles[0]['semantic']!=roles[1]['semantic']: issues.append('detail_changes_outcome:'+case['id'])
    for name in NAMES:
        keys=[f'{name}-c{c}' for c in (37,512)]
        if not all(k in normalized for k in keys): issues.append('missing_chunk_pair:'+name); continue
        for mode in (0,1):
            a,b=(normalized[k][mode] for k in keys)
            if a['chunk_semantic']!=b['chunk_semantic'] or a['trace_sha256']!=b['trace_sha256']: issues.append('chunk_changes_outcome:'+name)
    measured=not issues
    return {'measurement_pass':measured,**gates,'targeted_guard_pass':bool(measured and gates['availability_guard_pass']),
            'progression_pass':bool(measured and all(gates.values())),'product_promotion':False,
            'audited_invocations':sum(len(v) for v in normalized.values()),'measurement_issues':issues,
            'scope':'clear finite discriminator availability; no recovered-speech, RF, key or speed claim'}
