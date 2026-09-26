"""Generate observation seams around the isolated availability candidate only."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = HERE / 'baseline_observer'

def sha(raw): return hashlib.sha256(raw).hexdigest()

def once(text, old, new):
    if text.count(old) != 1: raise ValueError('Nonunique observation seam: ' + old[:120])
    return text.replace(old, new)

def prepare(output):
    manifest = json.loads((BASE / 'copy-manifest.json').read_bytes())
    sources = {}
    for name, digest in manifest['files'].items():
        raw = (BASE / name).read_bytes()
        if sha(raw) != digest: raise ValueError('Frozen observed baseline changed: ' + name)
        sources[name] = raw.decode('utf-8').replace('\r\n', '\n')
    candidate = HERE / 'candidate'
    frame = '#include "observer_api.h"\n' + (candidate / 'src/protocol/nxdn/nxdn_frame.c').read_text(encoding='utf-8')
    fields = 'ctx.lich_full, ctx.lich, ctx.lich_parity_received, ctx.lich_parity_computed, ctx.voice, ctx.scch, ctx.pich_tch, ctx.idas, ctx.sacch, ctx.facch'
    for predicate, reason in (('nxdn_validate_lich_parity(state, &ctx)', 'parity_reject'),
                              ('nxdn_validate_lich_direction(opts, state, &ctx)', 'direction_reject'),
                              ('nxdn_apply_lich_profile(state, &ctx)', 'unsupported_profile')):
        old = f'    if (!{predicate}) {{\n        goto END;\n    }}'
        new = f'    if (!{predicate}) {{\n        xerax_v2_lich(state, "{reason}", 0, {fields});\n        goto END;\n    }}'
        frame = once(frame, old, new)
    frame = once(frame, '    state->carrier = 1;\n    nxdn_print_sync_banner',
                 f'    xerax_v2_lich(state, "accepted", 1, {fields});\n    state->carrier = 1;\n    nxdn_print_sync_banner')
    observer = sources['observer.c']
    begin = observer.index('int\n__wrap_getDibitSoft(')
    end = observer.index('int __wrap_rtl_stream_start', begin)
    observer = observer[:begin] + '''int __real_dsd_get_dibit_soft_checked(dsd_opts*, dsd_state*, int*, dsd_dibit_soft_t*);
int __wrap_dsd_get_dibit_soft_checked(dsd_opts*, dsd_state*, int*, dsd_dibit_soft_t*);
int
__wrap_dsd_get_dibit_soft_checked(dsd_opts* opts, dsd_state* state, int* dibit, dsd_dibit_soft_t* soft) {
    v2_call call = {.before = v2_consumed(state), .eof_before = exhausted, .symbol_before = state->symbolcnt};
    int available = __real_dsd_get_dibit_soft_checked(opts, state, dibit, soft);
    call.after = v2_consumed(state); call.eof_after = exhausted; call.symbol_after = state->symbolcnt;
    call.available = available;
    if (in_frame) {
        if (body_count + 1U >= sizeof(body) || !dibit || *dibit < 0 || *dibit > 3 || (available != 0 && available != 1)) { errors++; }
        else {
            v2_calls[body_count] = call;
            /* Keep the independent fixed-profile source-position witness; the
               candidate's explicit availability is observed separately. */
            body_positions[body_count] = (!call.eof_after && call.symbol_after == call.symbol_before + 1U) ? call.after : 0;
            body[body_count++] = (char)('0' + *dibit); body[body_count] = 0;
        }
    }
    return available;
}
''' + observer[end:]
    observer = once(observer, '    printf(",\\"observation_schema\\":2,',
                    '    printf(",\\"availability_schema\\":1,\\"observation_schema\\":2,')
    v2 = sources['v2_observer_extra.inc']
    v2 = once(v2, '    int eof_before, eof_after;', '    int eof_before, eof_after, available;')
    v2 = once(v2, '\\"symbol_before\\":%u,\\"symbol_after\\":%u}',
              '\\"symbol_before\\":%u,\\"symbol_after\\":%u,\\"available\\":%d}')
    v2 = once(v2, 'c->eof_before, c->eof_after, c->symbol_before, c->symbol_after);',
              'c->eof_before, c->eof_after, c->symbol_before, c->symbol_after, c->available);')
    for name in ('__real_nxdn_voice', '__wrap_nxdn_voice'):
        v2 = v2.replace(name, name + '_masked')
    v2 = v2.replace('int, uint8_t[182], const uint8_t*);', 'int, uint8_t[182], const uint8_t*, uint8_t);')
    v2 = once(v2, 'const uint8_t* reliability) {', 'const uint8_t* reliability, uint8_t available_slots) {')
    v2 = once(v2, '__real_nxdn_voice_masked(opts, state, voice, data, reliability);',
              '__real_nxdn_voice_masked(opts, state, voice, data, reliability, available_slots);')
    extra_path = ROOT / 'experiments/nxdn_clear_routing_v1/observer_extra.inc'
    extra_raw = extra_path.read_bytes()
    if sha(extra_raw) != '9459b0f168e47511beb2f4bb66832fff5f9ff8542f40725c93187d197eb8a192':
        raise ValueError('Frozen real-FEC routing observer changed')
    extra = extra_raw.decode('utf-8').replace('\r\n', '\n')
    extra = extra.replace('__wrap_nxdn_voice', '__wrap_nxdn_voice_masked')
    extra = once(extra, '    int voice;\n} routing_voice_context;', '    int voice;\n    uint8_t available_slots;\n} routing_voice_context;')
    extra = once(extra, '    routing_prefix(kind);\n    printf(',
                 '    routing_prefix(kind);\n    printf(",\\"available_slots\\":%u", (unsigned)routing_voice.available_slots);\n    printf(')
    extra = once(extra, 'int, uint8_t[182], const uint8_t*);', 'int, uint8_t[182], const uint8_t*, uint8_t);')
    extra = once(extra, '__wrap_nxdn_voice_masked(dsd_opts* opts, dsd_state* state, int voice, uint8_t data[182], const uint8_t* reliability) {',
                 '__wrap_nxdn_voice_masked(dsd_opts* opts, dsd_state* state, int voice, uint8_t data[182], const uint8_t* reliability, uint8_t available_slots) {')
    extra = once(extra, '.reliability = reliability, .voice = voice};',
                 '.reliability = reliability, .voice = voice, .available_slots = available_slots};')
    extra = once(extra, 'routing_v2_nxdn_voice(opts, state, voice, data, reliability);',
                 'routing_v2_nxdn_voice(opts, state, voice, data, reliability, available_slots);')
    generated = {name: sources[name] for name in ('engine_observed.c','dispatch_observed.c','nxdn_deperm_observed.c','observer_api.h')}
    generated.update({'nxdn_frame_observed.c':frame,'observer.c':observer,
                      'v2_observer_extra.inc':v2,'observer_extra.inc':extra})
    output.mkdir(parents=True, exist_ok=True)
    for name, text in generated.items(): (output / name).write_text(text, encoding='utf-8', newline='\n')
    identity = {'registration_commit':'76e175aef1b8f30431c07cb3d4a50d431b858c02',
        'baseline_copy_manifest_sha256':sha((BASE / 'copy-manifest.json').read_bytes()),
        'frozen_generated_sources':manifest['files'],
        'frozen_routing_extra_sha256':sha(extra_raw),
        'candidate_sources':{p.relative_to(HERE).as_posix():sha(p.read_bytes()) for p in sorted(candidate.rglob('*')) if p.is_file()},
        'generator_sha256':sha(Path(__file__).read_bytes()),
        'generated_sources':{name:sha((output/name).read_bytes()) for name in generated},
        'scope':'Explicit-availability candidate with forwarding-only observation; no input generation or receiver execution'}
    (output/'source-identity.json').write_text(json.dumps(identity,indent=2)+'\n',encoding='utf-8')
    return identity

if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('usage: prepare_build.py OUTPUT_DIRECTORY')
    prepare(Path(sys.argv[1]))
