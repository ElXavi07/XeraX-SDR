"""Generate private observation-only sources; never create inputs or run a receiver.

All original files are byte-hash bound to the registered product/historical
sources. This also works in an archived source skeleton without a Git checkout.
The existing V2 generator and all historical matrix runners are never invoked.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
PIN = "289a82f8fd9c0495b64bf948fd45413bc63261c4"
V2_PIN = "a07b3ab37ffcdc127d40fad9a48a043c6ffcb3f7"
PINNED = {
    "upstream/dsd-neo/src/engine/engine.c": "fb2e493663947090fa94d8e8a5188fb2b8dc0596432e05e08acb440fce77ae9f",
    "upstream/dsd-neo/src/engine/dispatch/dispatch_nxdn.c": "fac4f15b77b85e59619a7e6d39608ffd3e9b8d7b36eb8be7ce5425a29587451f",
    "upstream/dsd-neo/src/protocol/nxdn/nxdn_frame.c": "a2c0d15efd6258c1469df2ebbb7dea05400f9e0ab74fba653c1e20125f04919a",
    "upstream/dsd-neo/src/protocol/nxdn/nxdn_deperm.c": "fca07d14eeefb128dddcd70dded0630f85f704643f5aac45e9ce92959e820010",
    "upstream/dsd-neo/src/protocol/nxdn/nxdn_voice.c": "4e56a528681b11f4f694a1b7f1d1f4cbeb6866fda8ff6b95d2116bc9d23dc675",
    "upstream/dsd-neo/src/core/vocoder/dsd_mbe.c": "6d46d12147e041123bd66654435c8dfc0f503e0faa43b1dfb933078604dad96c",
    "upstream/dsd-neo/include/dsd-neo/core/ambe_interleave.h": "167837a85ce0f43c0d0b30f6f68f22cef35393bf39ec4ec5148df1df360f41a5",
    "experiments/nxdn_engine_gap/observer.c": "87e77ee6570bd9bca084ee5b2dfe31feecd0a0820bb4b5de653204dd9e4c91da",
    "experiments/nxdn_engine_gap/observer_api.h": "89ebbdb3d11ffd223db807009f41e5aefa28b4b523243ae38cdfa6c2118abc79",
    "experiments/nxdn_observation_v2/observer_extra.inc": "c6d7b0ad47299c5f8ac1135e47c4dd00817198abe4d381f819d8bda9446e7357",
    "experiments/nxdn_observation_v2/observer_api.h": "9fb173a4cca90819e88b408196598a3601950903cd1ce99ac5ab8f646682843b",
    "experiments/nxdn_observation_v2/prepare_build.py": "0779b520c5eef929ff474026521060d5b372a89809a474b2c5f0e689cc045b62",
    "experiments/nxdn_frames/CMakeLists.txt": "67e064b5228b3ccaa392fe158045ed704f19e7342e9b803376c6df9a08879dfa",
}


def replace_one(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Observation seam is not unique: " + old[:100])
    return text.replace(old, new)


def prepare(output):
    sources = {}
    for relative, expected in PINNED.items():
        raw = (ROOT / relative).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("Pinned original source changed: " + relative)
        sources[relative] = raw.decode("utf-8").replace("\r\n", "\n")

    engine = sources["upstream/dsd-neo/src/engine/engine.c"]
    engine = replace_one(engine, "void\nnoCarrier(dsd_opts* opts, dsd_state* state)",
                         "void\nxerax_real_noCarrier(dsd_opts* opts, dsd_state* state)")
    engine = ('#include "observer_api.h"\n#define getFrameSync xerax_record_sync\n'
              '#define processFrame xerax_record_dispatch\n' + engine +
              '\nvoid xerax_run_live_loop(dsd_opts* opts, dsd_state* state) { live_scanner_main_loop(opts, state); }\n')

    observer = sources["experiments/nxdn_engine_gap/observer.c"]
    observer = replace_one(observer, "static void\nsnapshot(const dsd_state* s)",
        "static void routing_snapshot(const dsd_state* state);\n\nstatic void\nsnapshot(const dsd_state* s)")
    observer = replace_one(observer,
        "           s->audio_out_idx, s->audio_out_idx2, s->audio_out_idxR, s->audio_out_idx2R);\n}",
        "           s->audio_out_idx, s->audio_out_idx2, s->audio_out_idxR, s->audio_out_idx2R);\n"
        "    routing_snapshot(s);\n}")
    observer = replace_one(observer, "int\nxerax_record_sync",
        '#include "observer_extra.inc"\n\nint\nxerax_record_sync')
    observer = replace_one(observer, '    printf("]}\\n");\n    return result;',
        '    printf("]"); v2_dump_body_calls(); printf("}\\n");\n    return result;')
    begin_marker = "int\n__wrap_getDibitSoft("
    end_marker = "int __wrap_rtl_stream_start"
    if observer.count(begin_marker) != 1 or observer.count(end_marker) != 2:
        raise ValueError("Original dibit/provider seam changed")
    begin, end = observer.index(begin_marker), observer.index(end_marker)
    if end <= begin:
        raise ValueError("Original dibit/provider order changed")
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
        '    prefix("configuration");\n    routing_configuration(&opts, &state);\n'
        '    printf(",\\"observation_schema\\":2,\\"datascope\\":%d,\\"pulse_digi_rate_out\\":%d,\\"floating_point\\":%d,\\"dmr_stereo\\":%d",\n'
        '           opts.datascope, opts.pulse_digi_rate_out, opts.floating_point, opts.dmr_stereo);')
    observer = replace_one(observer, '    freeState(&state);\n    errors +=',
        '    routing_final_check();\n    freeState(&state);\n    errors +=')
    observer = replace_one(observer, '    prefix("summary");',
        '    prefix("summary");\n    routing_summary();\n'
        '    printf(",\\"v2_lich_events\\":%u,\\"v2_scch_events\\":%u,\\"v2_voice_calls\\":%u,\\"v2_mbe_calls\\":%u,\\"v2_audio_calls\\":%u",\n'
        '           v2_lich_events, v2_scch_events, v2_voice_calls, v2_mbe_calls, v2_audio_calls);')

    frame = '#include "observer_api.h"\n' + sources["upstream/dsd-neo/src/protocol/nxdn/nxdn_frame.c"]
    fields = 'ctx.lich_full, ctx.lich, ctx.lich_parity_received, ctx.lich_parity_computed, ctx.voice, ctx.scch, ctx.pich_tch, ctx.idas, ctx.sacch, ctx.facch'
    for predicate, reason in (("nxdn_validate_lich_parity(state, &ctx)", "parity_reject"),
                              ("nxdn_validate_lich_direction(opts, state, &ctx)", "direction_reject"),
                              ("nxdn_apply_lich_profile(state, &ctx)", "unsupported_profile")):
        old = f"    if (!{predicate}) {{\n        goto END;\n    }}"
        new = f'    if (!{predicate}) {{\n        xerax_v2_lich(state, "{reason}", 0, {fields});\n        goto END;\n    }}'
        frame = replace_one(frame, old, new)
    frame = replace_one(frame, "    state->carrier = 1;\n    nxdn_print_sync_banner",
        f'    xerax_v2_lich(state, "accepted", 1, {fields});\n    state->carrier = 1;\n    nxdn_print_sync_banner')

    deperm = '#include "observer_api.h"\n' + sources["upstream/dsd-neo/src/protocol/nxdn/nxdn_deperm.c"]
    start = deperm.index("void\nnxdn_deperm_scch_soft(")
    finish = deperm.index("/*\n * Soft-decision SACCH2", start)
    part = deperm[start:finish]
    part = replace_one(part, "    if (crc != check) {\n        nxdn_hard_fallback_decode",
        "    const int v2_soft_pass = crc == check;\n    if (crc != check) {\n        nxdn_hard_fallback_decode")
    part = replace_one(part, "    const uint8_t sf =",
        "    xerax_v2_scch(state, trellis_buf, crc, check, v2_soft_pass, direction);\n\n    const uint8_t sf =")
    deperm = deperm[:start] + part + deperm[finish:]

    header = sources["experiments/nxdn_engine_gap/observer_api.h"] + "\n"
    v2_header = sources["experiments/nxdn_observation_v2/observer_api.h"]
    v2_header = replace_one(v2_header, '#include "../nxdn_engine_gap/observer_api.h"\n', "")
    header += v2_header
    dispatch = ('#include "observer_api.h"\n#define nxdn_frame xerax_record_frame\n'
                + sources["upstream/dsd-neo/src/engine/dispatch/dispatch_nxdn.c"])
    generated = {"engine_observed.c": engine, "observer.c": observer,
        "nxdn_frame_observed.c": frame, "nxdn_deperm_observed.c": deperm,
        "observer_api.h": header, "dispatch_observed.c": dispatch,
        "v2_observer_extra.inc": sources["experiments/nxdn_observation_v2/observer_extra.inc"]}

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for name, text in generated.items():
        (output / name).write_text(text, encoding="utf-8", newline="\n")
    own = [Path(__file__), Path(__file__).with_name("observer_extra.inc"), Path(__file__).with_name("CMakeLists.txt")]
    identity = {"source_commit": PIN, "v2_recorder_commit": V2_PIN, "original_sources": PINNED,
        "observation_sources": {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest() for p in own},
        "generated_sources": {name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in generated},
        "scope": "Private observation only; real decoder forwards once; no fixture truth or policy patch"}
    (output / "source-identity.json").write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8", newline="\n")
    return identity


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: prepare_build.py NEW_GENERATED_SOURCE_DIRECTORY")
    prepare(Path(sys.argv[1]))
