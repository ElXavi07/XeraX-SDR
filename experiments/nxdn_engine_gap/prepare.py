"""Prepare the preregistered finite waveform matrix and engine instrumentation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = {"clean_weak": "CCWWWW", "parity_gap": "CCWPWW", "crc_gap": "CCWCWW",
             "strong_gap": "CCSPWW", "reset_gap": "CCWzWWW", "strong_reset_gap": "CCSzWWW",
             "bad_crc": "CCCCCC", "zero": "CCCCCC"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def previous():
    path = ROOT / "experiments/nxdn_lich_gap/prepare.py"
    registration = (ROOT / "docs/research/NXDN-ENGINE-GAP-PREREGISTRATION-2026-09-25.md").read_text()
    if f"`{sha(path)}`" not in registration:
        raise ValueError("Previous vector/patch policy drift")
    spec = importlib.util.spec_from_file_location("frozen_lich_gap", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    frozen = previous()
    vectors = frozen.prepare(output / "vectors")
    engine_path = ROOT / "upstream/dsd-neo/src/engine/engine.c"
    registration = (ROOT / "docs/research/NXDN-ENGINE-GAP-PREREGISTRATION-2026-09-25.md").read_text()
    for relative in ("upstream/dsd-neo/src/engine/dispatch/protocol_dispatch.c",
                     "upstream/dsd-neo/src/engine/dispatch/dispatch_nxdn.c"):
        if f"`{sha(ROOT / relative)}`" not in registration:
            raise ValueError(f"Registered dispatch source drift: {relative}")
    if f"`{sha(engine_path)}`" not in registration:
        raise ValueError("Engine source drift")
    engine = engine_path.read_text()
    marker = "void\nnoCarrier(dsd_opts* opts, dsd_state* state)"
    if engine.count(marker) != 1:
        raise ValueError("No-carrier definition changed")
    engine = engine.replace(marker, "void\nxerax_real_noCarrier(dsd_opts* opts, dsd_state* state)")
    engine = ('#include "observer_api.h"\n#define getFrameSync xerax_record_sync\n'
              '#define processFrame xerax_record_dispatch\n' + engine +
              '\nvoid xerax_run_live_loop(dsd_opts* opts, dsd_state* state) { live_scanner_main_loop(opts, state); }\n')
    (output / "engine_observed.c").write_text(engine, newline="\n")
    manifest = {"schema": 1, "domain": "discriminator_samples", "rate_hz": 48000,
                "symbol_rate": 2400, "samples_per_symbol": 20, "ramp": 8,
                "engine_source_sha256": sha(engine_path), "engine_observed_sha256": sha(output / "engine_observed.c"),
                "vectors": vectors, "waveforms": {}, "cases": []}
    encoder = frozen.load_encoder()
    levels = (8000., 24000., -8000., -24000.)
    for payload in range(2):
        for scenario, sequence in SCENARIOS.items():
            nrz = [levels[d] for d in (1, 3) * 16 for _ in range(20)]
            frames, gaps = [], []
            for kind in sequence:
                if kind == "z":
                    start = len(nrz)
                    nrz += [0.] * (2400 * 20)
                    gaps.append([start, len(nrz)])
                    continue
                data, meta = frozen.vector(encoder, payload, kind)
                frames.append({"ordinal": len(frames), "kind": kind, "start": len(nrz), "end": len(nrz) + 3840,
                               "vector": f"{payload}-{kind}.dibits", "sha256": meta["sha256"]})
                nrz += [levels[d] for d in data for _ in range(20)]
            nrz += [levels[0]] * (64 * 20)
            shaped = [sum(nrz[max(0, min(len(nrz) - 1, i + k - 4))] for k in range(8)) / 8 for i in range(len(nrz))]
            if scenario == "zero":
                shaped = [0.] * len(shaped)
                frames = []
            name = f"p{payload}-{scenario}"
            path = output / (name + ".f32le")
            path.write_bytes(struct.pack("<" + "f" * len(shaped), *shaped))
            manifest["waveforms"][name] = {"file": path.name, "samples": len(shaped), "sha256": sha(path),
                                           "frames": frames, "zero_gaps_before_shaping": gaps, "payload": payload, "scenario": scenario}
            for fast in (0, 1):
                for chunk in (37, 512):
                    manifest["cases"].append({"id": f"{name}-f{fast}-c{chunk}", "waveform": name,
                                              "fast": fast, "chunk": chunk})
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    prepare(sys.argv[1])
