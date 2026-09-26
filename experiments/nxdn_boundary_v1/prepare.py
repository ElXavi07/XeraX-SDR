"""Create registered boundary-screen inputs once, without receiver code."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct

ROOT = Path(__file__).resolve().parents[2]


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def generate(recovery, observation, out):
    out.mkdir(parents=True, exist_ok=False)
    (out / "vectors").mkdir()
    sources = [(recovery, "897035e6a439272d50312bcf7286b41e031bd61bdfdbba02ec775f1fc521c602"),
               (observation, "c1433cbded3233b24b501ce318578c0e7a2cadc5b9260a7530663920309cbf5c")]
    manifests = []
    for folder, digest in sources:
        need(sha(folder / "manifest.json") == digest, "Frozen parent manifest changed")
        manifests.append(json.loads((folder / "manifest.json").read_text()))
    result = {"schema": 1, "domain": "discriminator_samples", "rate_hz": 48000, "symbol_rate": 2400,
              "samples_per_symbol": 20, "ramp": 8, "vectors": {"vectors": {}}, "waveforms": {}, "cases": []}

    def copy_file(folder, name, digest=None):
        source, target = folder / name, out / name
        need(not digest or sha(source) == digest, "Parent file changed: " + name)
        if target.exists():
            need(target.read_bytes() == source.read_bytes(), "Conflicting parent bytes")
        else:
            shutil.copy2(source, target)

    def copy_wave(which, name):
        folder, manifest = sources[which][0], manifests[which]
        wave = dict(manifest["waveforms"][name])
        result["waveforms"][name] = wave
        for key, digest in (("file", "sha256"), ("original_file", "original_sha256"),
                            ("lineage_file", "lineage_sha256"), ("occurrence_file", "occurrence_sha256")):
            if key in wave:
                copy_file(folder, wave[key], wave.get(digest))
        for frame in wave["frames"]:
            name_v = frame["vector"]
            meta = manifest["vectors"]["vectors"][name_v]
            copy_file(folder, "vectors/" + name_v, meta["sha256"])
            result["vectors"]["vectors"][name_v] = meta
        wave["boundary_parent"] = which
        wave["boundary_anchor"] = name if which == 1 or name in ("h0-warm_clean", "h0-warm_drop20") else None

    for payload in (0, 1):
        for scenario in ("warm_clean", "warm_sync_blank", "warm_sync_invert", "warm_repeat20", "bad_crc", "cold_clean"):
            copy_wave(0, f"h{payload}-{scenario}")
    for name in ("h0-warm_drop20", "h0-zero"):
        copy_wave(0, name)
    for name in ("scch_valid", "scch_wrong"):
        copy_wave(1, name)
    encoder_path = ROOT / "experiments/nxdn_frames/generate_vectors.py"
    need(sha(encoder_path) == "3e2c63b57dba137bbb35cdb9457a17deb9d0363fff8b8117e5d530e5990be9bd", "Encoder changed")
    enc = load(encoder_path, "boundary_independent_encoder")
    relaxed = bytearray((out / "vectors/h0-S.dibits").read_bytes())
    relaxed[1] ^= 2
    (out / "vectors/h0-S-relaxed.dibits").write_bytes(relaxed)
    meta = dict(result["vectors"]["vectors"]["h0-S.dibits"])
    meta.update(sha256=sha(out / "vectors/h0-S-relaxed.dibits"), boundary_sync_edit={"dibit": 1, "xor": 2})
    result["vectors"]["vectors"]["h0-S-relaxed.dibits"] = meta
    for label in ("canonical", "relaxed"):
        name = "gap5_" + label
        nrz = [float(enc.LEVELS[d]) for d in (1, 3) * 16 for _ in range(20)]
        frames = []
        for ordinal, kind in enumerate("CCSSSSSS"):
            if ordinal == 4:
                nrz += [0.0] * 100
            v = "h0-S-relaxed.dibits" if ordinal == 4 and label == "relaxed" else f"h0-{kind}.dibits"
            data = (out / "vectors" / v).read_bytes()
            frames.append({"ordinal": ordinal, "kind": kind, "start": len(nrz), "end": len(nrz) + 3840,
                           "vector": v, "sha256": sha(out / "vectors" / v)})
            nrz.extend(float(enc.LEVELS[d]) for d in data for _ in range(20))
        nrz += [float(enc.LEVELS[0])] * 1280
        samples = [sum(nrz[max(0, min(len(nrz) - 1, i + k - 4))] for k in range(8)) / 8 for i in range(len(nrz))]
        (out / (name + ".f32le")).write_bytes(struct.pack("<" + "f" * len(samples), *samples))
        result["waveforms"][name] = {
            "file": name + ".f32le", "sha256": sha(out / (name + ".f32le")), "samples": len(samples),
            "frames": frames, "scenario": name, "payload": 0, "edit": {"kind": "none", "source_start": 0, "count": 0},
            "boundary_generation": {"gap_before_frame": 4, "zero_samples_before_shaping": 100,
                                    "relaxed_dibit": 1 if label == "relaxed" else None}, "boundary_anchor": None}
    for name in result["waveforms"]:
        for chunk in (37, 512):
            result["cases"].append({"id": name + f"-c{chunk}", "waveform": name, "chunk": chunk, "fast": 0})
    need(len(result["waveforms"]) == 18 and len(result["cases"]) == 36, "Registered grid differs")
    (out / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"waveforms": 18, "cases": 36, "invocations": 144, "manifest_sha256": sha(out / "manifest.json")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("recovery", "observation", "output"):
        parser.add_argument(arg, type=Path)
    args = parser.parse_args()
    generate(args.recovery, args.observation, args.output)
