"""Generate fixed independent dibit vectors and a private evidence-accounting candidate."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
ENCODER = ROOT / "experiments/nxdn_frames/generate_vectors.py"
FRAME = ROOT / "upstream/dsd-neo/src/protocol/nxdn/nxdn_frame.c"
SEQUENCES = {
    "adjacent_weak": "WW", "parity_gap": "WPWW", "unsupported_gap": "WUWW",
    "direction_gap": "WDWW", "crc_gap": "WCWW", "strong_parity": "SPW",
    "reset_weak": "WRWW", "reset_strong": "SRWW", "adjacent_strong": "SS",
    "rejected_before_weak": "PPWW", "confirmed_crc_gap": "SCW",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_encoder():
    registration = (ROOT / "docs/research/NXDN-LICH-GAP-PREREGISTRATION-2026-09-25.md").read_text()
    if f"`{sha(ENCODER)}`" not in registration or f"`{sha(FRAME)}`" not in registration:
        raise ValueError("Frozen source hash changed")
    spec = importlib.util.spec_from_file_location("frozen_gap_encoder", ENCODER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def candidate(source):
    # All transformations must match exactly once; no source mutation or fuzzy patch.
    replacements = (
        ("    nxdn_frame_ctx_init(&ctx);", "    nxdn_confirm_begin_frame(state);\n    nxdn_frame_ctx_init(&ctx);"),
        ("    nxdn_confirm_begin_frame(state);\n    nxdn_print_voice_or_data_and_sync_lfsr", "    nxdn_print_voice_or_data_and_sync_lfsr"),
        ("    nxdn_confirm_end_frame(state);\n    frame_proved = nxdn_confirm_frame_proved(state);\n", ""),
        ("END:\n    nxdn_finalize_sync_reject(state);", "END:\n    nxdn_confirm_end_frame(state);\n    frame_proved = nxdn_confirm_frame_proved(state);\n    nxdn_finalize_sync_reject(state);"),
    )
    result = source.replace("\r\n", "\n")
    for before, after in replacements:
        if result.count(before) != 1:
            raise ValueError("Candidate patch context changed")
        result = result.replace(before, after)
    return result


def vector(encoder, payload, name):
    lich = 0x7F if name == "U" else 0x40 if name == "D" else 0x41
    full = lich << 1
    parity = sum(encoder.bits(full >> 4, 4)) % 2
    full |= parity ^ (name == "P")
    lich_bits = tuple(v for bit in encoder.bits(full, 8) for v in (bit, 1))
    sacch_info = encoder.bits(0, 2) + encoder.bits(23 if payload == 0 else 37, 6) + encoder.bits(0x10, 8)
    sacch_info += (0,) * 10 if payload == 0 else (1, 0) * 5
    facch_info = encoder.bits(0x10, 8) + ((0,) * 72 if payload == 0 else (1, 0) * 36)
    sacch, sacch_meta = encoder.channel(sacch_info, 6, name == "C")
    facch, facch_meta = encoder.channel(facch_info, 12, name != "S")
    data = encoder.to_dibits(encoder.bits(encoder.FSW, 20)) + encoder.whiten(encoder.to_dibits(lich_bits + sacch + facch + facch))
    return data, {"payload": payload, "name": name, "lich": lich, "full_lich": full,
                  "sacch": sacch_meta, "facch": facch_meta, "sha256": hashlib.sha256(data).hexdigest()}


def prepare(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    encoder = load_encoder()
    manifest = {"schema": 1, "frame_source_sha256": sha(FRAME), "encoder_sha256": sha(ENCODER),
                "sequences": SEQUENCES, "vectors": {}}
    (output / "nxdn_frame_candidate.c").write_text(candidate(FRAME.read_text()), newline="\n")
    for payload in range(2):
        for name in "WSCPUD":
            data, meta = vector(encoder, payload, name)
            path = output / f"{payload}-{name}.dibits"
            path.write_bytes(data)
            manifest["vectors"][path.name] = meta
    manifest["candidate_sha256"] = sha(output / "nxdn_frame_candidate.c")
    (output / "vectors.json").write_text(json.dumps(manifest, indent=2) + "\n", newline="\n")
    return manifest


if __name__ == "__main__":
    prepare(sys.argv[1])
