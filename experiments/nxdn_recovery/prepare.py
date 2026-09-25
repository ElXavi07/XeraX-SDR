"""Registered NXDN recovery inputs; no product mutation or native execution."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
ENCODER_SHA = "3e2c63b57dba137bbb35cdb9457a17deb9d0363fff8b8117e5d530e5990be9bd"
WINDOWS_BINARY_SHA = "ace9de618e098fe4878607fc43ad0d0480c3a7e80f225b5bae7ea880900882fe"
FRAME_NORMALIZED_SHA = "457bc11c3672d7cffc6b70facd19afe1de3c6fa433d075d5f511bb44b8ad8181"
SCENARIOS = {
    "warm_clean": ("CCSSSSSS", "none", 0, 0),
    "warm_sync_blank": ("CCSSSSSS", "blank", 4, 200),
    "warm_sync_invert": ("CCSSSSSS", "invert", 4, 200),
    "warm_drop1": ("CCSSSSSS", "drop", 4, 1),
    "warm_repeat1": ("CCSSSSSS", "repeat", 4, 1),
    "warm_drop20": ("CCSSSSSS", "drop", 4, 20),
    "warm_repeat20": ("CCSSSSSS", "repeat", 4, 20),
    "cold_clean": ("SSSSSSSS", "none", 0, 0),
    "cold_sync_blank": ("SSSSSSSS", "blank", 0, 200),
    "cold_drop1": ("SSSSSSSS", "drop", 0, 1),
    "cold_repeat1": ("SSSSSSSS", "repeat", 0, 1),
    "bad_crc": ("CCCCCCCC", "none", 0, 0),
    "zero": ("CCCCCCCC", "zero", 0, 0),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_encoder():
    path = ROOT / "experiments/nxdn_frames/generate_vectors.py"
    require(sha(path) == ENCODER_SHA, "Independent encoder changed")
    spec = importlib.util.spec_from_file_location("recovery_frozen_encoder", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def vector(encoder, payload, kind):
    require(payload in (0, 1) and kind in ("S", "C"), "Undeclared payload or frame")
    lich = 0x41
    full = lich << 1
    full |= sum(encoder.bits(full >> 4, 4)) % 2
    lich_bits = tuple(v for bit in encoder.bits(full, 8) for v in (bit, 1))
    ran, tail10, tail72 = ((11, 0x155, 0x123456789ABCDEF012),
                          (53, 0x2D3, 0xFEDCBA9876543210AB))[payload]
    sacch_info = encoder.bits(0, 2) + encoder.bits(ran, 6) + encoder.bits(0x10, 8) + encoder.bits(tail10, 10)
    facch_info = encoder.bits(0x10, 8) + encoder.bits(tail72, 72)
    sacch, sacch_meta = encoder.channel(sacch_info, 6, kind == "C")
    facch, facch_meta = encoder.channel(facch_info, 12, kind == "C")
    data = encoder.to_dibits(encoder.bits(encoder.FSW, 20)) + encoder.whiten(encoder.to_dibits(lich_bits + sacch + facch + facch))
    require(len(data) == 192, "Wrong frame size")
    return data, {"payload": payload, "name": kind, "lich": lich, "full_lich": full,
                  "sacch": sacch_meta, "facch": facch_meta, "sha256": hashlib.sha256(data).hexdigest()}


def transform(samples, kind, position=0, count=0):
    require(kind in {"none", "zero", "blank", "invert", "drop", "repeat"}, "Undeclared transform")
    require(0 <= position <= len(samples) and 0 <= count <= len(samples) - position, "Fault outside source")
    original = list(range(len(samples)))
    if kind == "drop":
        mapped = original[:position] + original[position + count:]
        delivered = samples[:position] + samples[position + count:]
    elif kind == "repeat":
        mapped = original[:position] + original[position:position + count] + original[position:]
        delivered = samples[:position] + samples[position:position + count] + samples[position:]
    else:
        mapped = original
        delivered = list(samples)
        if kind == "zero":
            delivered = [0.] * len(samples)
        elif kind == "blank":
            delivered[position:position + count] = [0.] * count
        elif kind == "invert":
            delivered[position:position + count] = [-x for x in samples[position:position + count]]
    occurrences, seen = [], {}
    for index in mapped:
        occurrences.append(seen.get(index, 0))
        seen[index] = seen.get(index, 0) + 1
    return delivered, mapped, occurrences


def packed(path, values, code):
    path.write_bytes(struct.pack("<" + code * len(values), *values))


def prepare(output, anchor):
    output, anchor = Path(output), Path(anchor)
    output.mkdir(parents=True, exist_ok=False)
    (output / "vectors").mkdir()
    encoder = load_encoder()
    manifest = {"schema": 1, "domain": "discriminator_samples", "rate_hz": 48000,
                "symbol_rate": 2400, "samples_per_symbol": 20, "ramp": 8,
                "encoder_sha256": ENCODER_SHA, "vectors": {"vectors": {}}, "waveforms": {}, "cases": []}
    for payload in range(2):
        for kind in ("S", "C"):
            data, meta = vector(encoder, payload, kind)
            name = f"h{payload}-{kind}.dibits"
            (output / "vectors" / name).write_bytes(data)
            manifest["vectors"]["vectors"][name] = meta
        for scenario, (sequence, edit, frame_ordinal, count) in SCENARIOS.items():
            nrz = [float(encoder.LEVELS[d]) for d in (1, 3) * 16 for _ in range(20)]
            frames = []
            for kind in sequence:
                name = f"h{payload}-{kind}.dibits"
                data = (output / "vectors" / name).read_bytes()
                frames.append({"ordinal": len(frames), "kind": kind, "start": len(nrz), "end": len(nrz) + 3840,
                               "vector": name, "sha256": sha(output / "vectors" / name)})
                nrz.extend(float(encoder.LEVELS[d]) for d in data for _ in range(20))
            nrz += [float(encoder.LEVELS[0])] * 1280
            original = [sum(nrz[max(0, min(len(nrz) - 1, i + k - 4))] for k in range(8)) / 8 for i in range(len(nrz))]
            position = frames[frame_ordinal]["start"] if edit not in ("none", "zero") else 0
            if edit in ("drop", "repeat"):
                position += 217 if scenario.startswith("warm_") else 97
            delivered, mapped, occurrences = transform(original, edit, position, count)
            name = f"h{payload}-{scenario}"
            originals, path = output / (name + ".original.f32le"), output / (name + ".f32le")
            lineage, occurrence = output / (name + ".origin.u32le"), output / (name + ".occurrence.u32le")
            packed(originals, original, "f"); packed(path, delivered, "f")
            packed(lineage, mapped, "I"); packed(occurrence, occurrences, "I")
            manifest["waveforms"][name] = {"file": path.name, "sha256": sha(path), "samples": len(delivered),
                "original_file": originals.name, "original_sha256": sha(originals), "original_samples": len(original),
                "lineage_file": lineage.name, "lineage_sha256": sha(lineage),
                "occurrence_file": occurrence.name, "occurrence_sha256": sha(occurrence),
                "frames": [] if edit == "zero" else frames, "zero_gaps_before_shaping": [],
                "payload": payload, "scenario": scenario, "legacy": False,
                "edit": {"kind": edit, "source_start": position, "count": count}}
    old = json.loads((anchor / "inputs/manifest.json").read_text())
    reference = dict(old["waveforms"]["p0-clean_weak"])
    for frame in reference["frames"]:
        name = frame["vector"]
        p = anchor / "inputs/vectors" / name
        require(sha(p) == old["vectors"]["vectors"][name]["sha256"], "Legacy vector changed")
        (output / "vectors" / name).write_bytes(p.read_bytes())
        manifest["vectors"]["vectors"][name] = old["vectors"]["vectors"][name]
    path = anchor / "inputs" / reference["file"]
    require(sha(path) == reference["sha256"], "Legacy waveform changed")
    (output / reference["file"]).write_bytes(path.read_bytes())
    reference.update(legacy=True, legacy_waveform="p0-clean_weak", scenario="legacy_clean_weak")
    manifest["waveforms"]["legacy_clean_weak"] = reference
    for name in manifest["waveforms"]:
        for chunk in (37, 512):
            manifest["cases"].append({"id": f"{name}-c{chunk}", "waveform": name, "chunk": chunk})
    require(len(manifest["waveforms"]) == 27 and len(manifest["cases"]) == 54, "Registered matrix changed")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    prepare(sys.argv[1], sys.argv[2])
