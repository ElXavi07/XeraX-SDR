"""Frozen finite observation inputs; independent SCCH checkword, no decoder import."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct

ROOT = Path(__file__).resolve().parents[2]
ENCODER_SHA = "3e2c63b57dba137bbb35cdb9457a17deb9d0363fff8b8117e5d530e5990be9bd"
PARENT_MANIFEST_SHA = "897035e6a439272d50312bcf7286b41e031bd61bdfdbba02ec775f1fc521c602"
COPIED = ("h0-warm_clean", "h0-cold_sync_blank", "h0-warm_drop20")
CUTS = (12360, 12361, 12380, 12521)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encoder():
    path = ROOT / "experiments/nxdn_frames/generate_vectors.py"
    require(sha(path) == ENCODER_SHA, "Frozen independent encoder changed")
    spec = importlib.util.spec_from_file_location("observation_frozen_encoder", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def crc7(bits):
    state = 127
    for bit in bits:
        require(type(bit) is int and bit in (0, 1), "Invalid CRC input bit")
        feedback = bit ^ (state >> 6)
        state = ((state << 1) & 127) ^ (9 if feedback else 0)
    return state


def scch_vector(enc, wrong):
    information = (0,) * 25
    check = crc7(information)
    sent = check ^ (64 if wrong else 0)
    coded = enc.convolution(information + enc.bits(sent, 7) + (0,) * 4)
    transmitted = enc.interleave(enc.puncture(coded, 6, 5), 12, 5)
    lich = tuple(v for bit in enc.bits(0xEF, 8) for v in (bit, 1))
    data = enc.to_dibits(enc.bits(enc.FSW, 20)) + enc.whiten(enc.to_dibits(lich + transmitted) + bytes(144))
    require(len(data) == 192 and check == 17, "Independent SCCH shape/check mismatch")
    return data, {"information_bits": "0" * 25, "computed_crc": check, "transmitted_crc": sent,
                  "crc_width": 7, "crc_expected_pass": not wrong}


def pack_floats(values):
    return struct.pack("<" + "f" * len(values), *values)


def write_maps(output, name, count):
    origin, occurrence = output / (name + ".origin.u32le"), output / (name + ".occurrence.u32le")
    origin.write_bytes(struct.pack("<" + "I" * count, *range(count)))
    occurrence.write_bytes(bytes(count * 4))
    return {"lineage_file": origin.name, "lineage_sha256": sha(origin),
            "occurrence_file": occurrence.name, "occurrence_sha256": sha(occurrence)}


def prepare(parent, output):
    require(sha(parent / "manifest.json") == PARENT_MANIFEST_SHA, "Parent manifest changed")
    output.mkdir(parents=True, exist_ok=False); (output / "vectors").mkdir()
    old = json.loads((parent / "manifest.json").read_text())
    manifest = {"schema": 2, "kind": "nxdn_observation_v2", "rate_hz": 48000, "samples_per_symbol": 20,
                "parent_manifest_sha256": PARENT_MANIFEST_SHA, "vectors": {"vectors": {}}, "waveforms": {}, "cases": []}
    for name in ("h0-C.dibits", "h0-S.dibits"):
        metadata = old["vectors"]["vectors"][name]
        require(sha(parent / "vectors" / name) == metadata["sha256"], "Parent vector changed")
        shutil.copy2(parent / "vectors" / name, output / "vectors" / name)
        manifest["vectors"]["vectors"][name] = metadata
    for name in COPIED:
        wave = json.loads(json.dumps(old["waveforms"][name]))
        for field, hash_field in (("file", "sha256"), ("original_file", "original_sha256"),
                                  ("lineage_file", "lineage_sha256"), ("occurrence_file", "occurrence_sha256")):
            require(sha(parent / wave[field]) == wave[hash_field], "Parent waveform/map changed")
            shutil.copy2(parent / wave[field], output / wave[field])
        wave["anchor_waveform"] = name
        manifest["waveforms"][name] = wave
    clean = manifest["waveforms"]["h0-warm_clean"]
    clean_bytes = (output / clean["file"]).read_bytes()
    for cut in CUTS:
        name = f"prefix_{cut}"
        path = output / (name + ".f32le"); path.write_bytes(clean_bytes[:cut * 4])
        manifest["waveforms"][name] = {"file": path.name, "sha256": sha(path), "samples": cut,
            "original_file": clean["file"], "original_sha256": clean["sha256"], "original_samples": clean["samples"],
            "frames": [f for f in clean["frames"] if f["start"] < cut], "scenario": name, "payload": 0,
            "edit": {"kind": "prefix", "source_start": cut, "count": clean["samples"] - cut},
            **write_maps(output, name, cut)}
    enc = encoder()
    for wrong in (False, True):
        name = "scch_wrong" if wrong else "scch_valid"
        data, expected = scch_vector(enc, wrong)
        vector_name = name + ".dibits"
        (output / "vectors" / vector_name).write_bytes(data)
        manifest["vectors"]["vectors"][vector_name] = {"name": "V", "lich": 0x77, "full_lich": 0xEF,
            "sha256": sha(output / "vectors" / vector_name), "scch": expected, "voice_truth": "unspecified synthetic bits; no speech-validity claim"}
        nrz = [enc.LEVELS[d] for d in (1, 3) * 16 for _ in range(20)]
        frames = []
        for ordinal, kind in enumerate("CCSSVV"):
            selected = vector_name if kind == "V" else f"h0-{kind}.dibits"
            encoded = (output / "vectors" / selected).read_bytes()
            frames.append({"ordinal": ordinal, "kind": kind, "start": len(nrz), "end": len(nrz) + 3840,
                           "vector": selected, "sha256": sha(output / "vectors" / selected)})
            nrz.extend(enc.LEVELS[d] for d in encoded for _ in range(20))
        nrz.extend([8000] * 1280)
        wave = [sum(nrz[max(0, min(len(nrz) - 1, i + k - 4))] for k in range(8)) / 8 for i in range(len(nrz))]
        path = output / (name + ".f32le"); path.write_bytes(pack_floats(wave))
        manifest["waveforms"][name] = {"file": path.name, "sha256": sha(path), "samples": len(wave),
            "original_file": path.name, "original_sha256": sha(path), "original_samples": len(wave),
            "frames": frames, "scenario": name, "payload": 0, "scch_expected": expected,
            "edit": {"kind": "none", "source_start": 0, "count": 0}, **write_maps(output, name, len(wave))}
    for name in manifest["waveforms"]:
        for chunk in (37, 512):
            manifest["cases"].append({"id": f"{name}-c{chunk}", "waveform": name, "chunk": chunk, "fast": 0})
    require(len(manifest["cases"]) == 18, "Wrong registered matrix count")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parent", type=Path); parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = prepare(args.parent, args.output)
    print(json.dumps({"waves": len(result["waveforms"]), "base_cases": len(result["cases"]), "invocations": 36}))
