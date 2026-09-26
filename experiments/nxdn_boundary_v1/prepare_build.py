"""Private boundary seams layered over the frozen observation-v2 generator."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PIN = "56e83ddfb31fe6bb8e028d0360a281698c5d0b13"


def one(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Nonunique boundary seam: " + old[:100])
    return text.replace(old, new)


def prepare(parent, out):
    out.mkdir(parents=True, exist_ok=True)
    originals = {}
    def read(path):
        raw = path.read_bytes()
        originals[str(path)] = hashlib.sha256(raw).hexdigest()
        return raw.decode().replace("\r\n", "\n")
    observer = read(parent / "observer.c")
    observer = '#include "phase_runtime.h"\n' + observer
    observer = one(observer, '    if (read_wave(argv[1])) { return 3; }',
        '    if (read_wave(argv[1])) { return 3; }\n    if (nxdn_boundary_runtime_open("phase.jsonl")) { return 6; }')
    observer = one(observer, '    mark("reset_begin", state, 0);',
        '    nxdn_boundary_runtime_reset("carrier");\n    mark("reset_begin", state, 0);')
    observer = one(observer, '    errors += (unsigned)write_trace(argv[5]);',
        '    errors += (unsigned)nxdn_boundary_runtime_close();\n    errors += (unsigned)write_trace(argv[5]);')
    frame = '#include "phase_runtime.h"\n' + read(parent / "nxdn_frame_observed.c")
    frame = one(frame, 'nxdn_frame(dsd_opts* opts, dsd_state* state) {',
        'nxdn_frame(dsd_opts* opts, dsd_state* state) {\n    const nxdn_boundary_v1_context boundary_begin = nxdn_boundary_runtime_context(opts, state);')
    frame = one(frame, '    return frame_proved ? 2 : nxdn_confirm_is_confirmed(state);',
        '    const int boundary_result = frame_proved ? 2 : nxdn_confirm_is_confirmed(state);\n'
        '    nxdn_boundary_runtime_frame(&boundary_begin, opts, state, boundary_result);\n    return boundary_result;')
    relative = "upstream/dsd-neo/src/dsp/dsd_frame_sync.c"
    path = ROOT / relative
    if path.read_bytes() != subprocess.check_output(["git", "show", PIN + ":" + relative], cwd=ROOT):
        raise ValueError("Pinned matcher changed")
    sync = '#include "phase_runtime.h"\n' + read(path)
    sync = one(sync, '    state->offset = ctx->synctest_pos;\n    int first_canonical_enabled',
        '    if (!nxdn_boundary_runtime_allow(opts, state, ctx->synctest10)) { return DSD_SYNC_NONE; }\n'
        '    state->offset = ctx->synctest_pos;\n    int first_canonical_enabled')
    sync = one(sync, '    dsd_frame_sync_reset_mod_state();\n    dsd_frame_sync_sps_hunt_restart_dwell(state);',
        '    nxdn_boundary_runtime_reset("acquisition");\n    dsd_frame_sync_reset_mod_state();\n    dsd_frame_sync_sps_hunt_restart_dwell(state);')
    sync = one(sync, '    state->sps_hunt_idx = next_idx;',
        '    nxdn_boundary_runtime_reset("profile");\n    state->sps_hunt_idx = next_idx;')
    files = {"observer.c": observer, "nxdn_frame_boundary.c": frame, "dsd_frame_sync_boundary.c": sync}
    for name, value in files.items():
        (out / name).write_text(value, encoding="utf-8", newline="\n")
    (out / "source-identity.json").write_text(json.dumps({"product_pin": PIN, "originals": originals,
        "generated": {name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in files}}, indent=2) + "\n")


if __name__ == "__main__":
    prepare(Path(sys.argv[1]), Path(sys.argv[2]))
