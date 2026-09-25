"""Generate only private observation seams from an immutable product source revision."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PIN = "938c5fe8a24719dbfad510bc536f1084de650a1a"


def replace_one(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Observation seam is not unique: " + old[:80])
    return text.replace(old, new)


def prepare(output):
    output.mkdir(parents=True, exist_ok=True)
    identities = {}
    def read(relative):
        raw = (ROOT / relative).read_bytes()
        expected = subprocess.check_output(["git", "show", PIN + ":" + relative], cwd=ROOT)
        if raw != expected:
            raise ValueError("Pinned native/observer source changed: " + relative)
        identities[relative] = hashlib.sha256(raw).hexdigest()
        return raw.decode().replace("\r\n", "\n")

    engine = read("upstream/dsd-neo/src/engine/engine.c")
    engine = replace_one(engine, "void\nnoCarrier(dsd_opts* opts, dsd_state* state)",
                         "void\nxerax_real_noCarrier(dsd_opts* opts, dsd_state* state)")
    engine = ('#include "observer_api.h"\n#define getFrameSync xerax_record_sync\n'
              '#define processFrame xerax_record_dispatch\n' + engine +
              '\nvoid xerax_run_live_loop(dsd_opts* opts, dsd_state* state) { live_scanner_main_loop(opts, state); }\n')
    observer = read("experiments/nxdn_engine_gap/observer.c")
    observer = replace_one(observer, "int\nxerax_record_sync", '#include "observer_extra.inc"\n\nint\nxerax_record_sync')
    observer = replace_one(observer, '    printf("]}\\n");\n    return result;',
                            '    printf("]"); v2_dump_body_calls(); printf("}\\n");\n    return result;')
    begin = observer.index("int\n__wrap_getDibitSoft(")
    end = observer.index("int __wrap_rtl_stream_start", begin)
    observer = observer[:begin] + '''int
__wrap_getDibitSoft(dsd_opts* opts, dsd_state* state, dsd_dibit_soft_t* soft) {
    v2_call call = {.before = v2_consumed(state), .eof_before = exhausted, .symbol_before = state->symbolcnt};
    int result = __real_getDibitSoft(opts, state, soft);
    call.after = v2_consumed(state); call.eof_after = exhausted; call.symbol_after = state->symbolcnt;
    if (in_frame) {
        if (body_count + 1U >= sizeof(body) || result < 0 || result > 3) { errors++; }
        else {
            v2_calls[body_count] = call;
            body_positions[body_count] = (!call.eof_after && call.symbol_after == call.symbol_before + 1U) ? call.after : 0;
            body[body_count++] = (char)('0' + result); body[body_count] = 0;
        }
    }
    return result;
}
''' + observer[end:]
    observer = replace_one(observer, '    opts.use_cosine_filter = 0; opts.msize = 1; opts.ssize = 128;',
                            '    opts.use_cosine_filter = 0; opts.msize = 1; opts.ssize = 128; opts.datascope = 0;')
    observer = replace_one(observer, '    prefix("configuration");',
        '    prefix("configuration");\n    printf(",\\"observation_schema\\":2,\\"datascope\\":%d,\\"pulse_digi_rate_out\\":%d,\\"floating_point\\":%d,\\"dmr_stereo\\":%d",\n'
        '           opts.datascope, opts.pulse_digi_rate_out, opts.floating_point, opts.dmr_stereo);')
    observer = replace_one(observer, '    prefix("summary");',
        '    prefix("summary");\n    printf(",\\"v2_lich_events\\":%u,\\"v2_scch_events\\":%u,\\"v2_voice_calls\\":%u,\\"v2_mbe_calls\\":%u,\\"v2_audio_calls\\":%u",\n'
        '           v2_lich_events, v2_scch_events, v2_voice_calls, v2_mbe_calls, v2_audio_calls);')
    frame = read("upstream/dsd-neo/src/protocol/nxdn/nxdn_frame.c")
    frame = '#include "observer_api.h"\n' + frame
    fields = 'ctx.lich_full, ctx.lich, ctx.lich_parity_received, ctx.lich_parity_computed, ctx.voice, ctx.scch, ctx.pich_tch, ctx.idas, ctx.sacch, ctx.facch'
    for predicate, reason in (("nxdn_validate_lich_parity(state, &ctx)", "parity_reject"),
                              ("nxdn_validate_lich_direction(opts, state, &ctx)", "direction_reject"),
                              ("nxdn_apply_lich_profile(state, &ctx)", "unsupported_profile")):
        old = f"    if (!{predicate}) {{\n        goto END;\n    }}"
        new = f'    if (!{predicate}) {{\n        xerax_v2_lich(state, "{reason}", 0, {fields});\n        goto END;\n    }}'
        frame = replace_one(frame, old, new)
    frame = replace_one(frame, "    state->carrier = 1;\n    nxdn_print_sync_banner",
        f'    xerax_v2_lich(state, "accepted", 1, {fields});\n    state->carrier = 1;\n    nxdn_print_sync_banner')
    deperm = read("upstream/dsd-neo/src/protocol/nxdn/nxdn_deperm.c")
    deperm = '#include "observer_api.h"\n' + deperm
    start = deperm.index("void\nnxdn_deperm_scch_soft(")
    finish = deperm.index("/*\n * Soft-decision SACCH2", start)
    part = deperm[start:finish]
    part = replace_one(part, "    if (crc != check) {\n        nxdn_hard_fallback_decode",
        "    const int v2_soft_pass = crc == check;\n    if (crc != check) {\n        nxdn_hard_fallback_decode")
    part = replace_one(part, "    const uint8_t sf =", "    xerax_v2_scch(state, trellis_buf, crc, check, v2_soft_pass, direction);\n\n    const uint8_t sf =")
    deperm = deperm[:start] + part + deperm[finish:]
    generated = {"engine_observed.c": engine, "observer.c": observer, "nxdn_frame_observed.c": frame, "nxdn_deperm_observed.c": deperm}
    for name, text in generated.items():
        (output / name).write_text(text, encoding="utf-8", newline="\n")
    (output / "source-identity.json").write_text(json.dumps({"source_commit": PIN, "original_sources": identities,
        "generated_sources": {name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in generated}}, indent=2) + "\n")


if __name__ == "__main__":
    prepare(Path(sys.argv[1]))
