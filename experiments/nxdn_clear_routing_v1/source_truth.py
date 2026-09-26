"""Read-only independent reconstruction of registered inputs, without encoders."""
import hashlib
import json
from pathlib import Path
import struct

PINS = {"reference/manifest.json": "17061018477b6451207758d6e0390b3ef623e88099f565bfc3416f1168127067",
        "reference/air-report.json": "867264df1b1f05eaa5db49d30e7287def90c3a32ebb3d9dcd47a0e2feb296f6f",
        "reference/primary.records96": "bedb3ae824c357e68e8d2883b808b357e228e74c7ce253acf0a41cf257234c0b",
        "reference/publication.json": "97b56f7d5ad4b4348b05daaa3915ebbcc926ff2a8c7bc40dc5220437fcb1016d",
        "reference/linked-source.bin": "8f4116e67a4c950a524c8568caf17d550e9b0b0bbdac3f9e3761ce76c0056e41",
        "reference/voice-reference.channels9": "05ed6f2d7c548e6b6e94e81bb12534afde0c2e13301791a8f1d4d2778dd6eed3"}
CONFIGS = (("primed", "primed", 0), ("cold_default", "cold", 0), ("cold_fast", "cold", 1),
           ("single_weak", "single_weak", 1), ("bad_lich", "bad_lich", 0), ("zero", "zero", 0),
           ("prefix_9999", "prefix_9999", 0), ("prefix_10000", "prefix_10000", 0), ("prefix_10001", "prefix_10001", 0))


def need(ok, message):
    if not ok: raise ValueError(message)


def unpack(raw):
    return bytes((b >> (6-2*i)) & 3 for b in raw for i in range(4))


def shape(frames):
    """Independent prefix-sum form of the declared centered eight-tap mean."""
    source = [24000 if (i//20) % 2 == 0 else -24000 for i in range(640)]
    level = {0: 8000, 1: 24000, 2: -8000, 3: -24000}
    for raw in frames:
        for dibit in unpack(raw): source += [level[dibit]] * 20
    source += [8000] * 1280
    padded = [source[0]] * 4 + source + [source[-1]] * 3
    sums = [0]
    for value in padded: sums.append(sums[-1] + value)
    return b"".join(struct.pack("<f", (sums[i+8] - sums[i])/8) for i in range(len(source)))


def verify(inputs, manifest, crc):
    inputs = Path(inputs).resolve()
    def read(name, pin=None):
        path = (inputs / name).resolve()
        need(path.is_relative_to(inputs) and path.is_file(), "Missing/escaped input: " + name)
        raw = path.read_bytes()
        if pin is not None: need(hashlib.sha256(raw).hexdigest() == pin, "Input hash mismatch: " + name)
        return raw
    refs = {name: read(name, pin) for name, pin in PINS.items()}
    air_manifest = json.loads(refs["reference/manifest.json"])
    expected_refs = {"reference/" + name for name in air_manifest["files"]} | set(PINS)
    need(set(manifest["reference_files"]) == expected_refs, "Reference inventory changed")
    for name, meta in manifest["reference_files"].items():
        raw = read(name, meta["sha256"]); need(len(raw) == meta["bytes"], "Reference size changed")
    for name, meta in air_manifest["files"].items():
        need(len(read("reference/" + name, meta["sha256"])) == meta["bytes"], "Pinned AIR file changed")
    need(manifest["schema"] == 1 and manifest["kind"] == "nxdn_clear_routing_v1"
         and manifest["domain"] == "discriminator_samples", "Input domain/schema changed")
    need(tuple(manifest[k] for k in ("rate_hz", "symbol_rate", "samples_per_symbol", "ramp")) == (48000, 2400, 20, 8), "Input rates/shaping changed")
    need(manifest["registration_commit"] == "d98ccd32ddc6cb4fa15bae07a91cf33e144df445"
         and manifest["product_baseline"] == "289a82f8fd9c0495b64bf948fd45413bc63261c4", "Registered source identities changed")
    cases = [{"id": f"{scenario}-c{chunk}", "configuration": scenario, "waveform": wave, "chunk": chunk, "fast": fast}
             for scenario, wave, fast in CONFIGS for chunk in (37, 512)]
    need(manifest["cases"] == cases, "Fixed invocation matrix changed")
    packed = refs["reference/primary.records96"]
    raw_frames = [packed[i*96:i*96+48] for i in range(9)]
    air = [packed[i*96+48:(i+1)*96] for i in range(9)]
    metadata = json.loads(read("reference/frames.json"))
    words = []
    for start in range(0, 130, 13):
        b = "".join(format(v, "08b") for v in refs["reference/linked-source.bin"][start:start+13])
        words += [b[:49], b[49:98]]
    channels = ["".join(format(v, "08b") for v in refs["reference/voice-reference.channels9"][i*9:i*9+9]) for i in range(20)]
    vector_truth = {}
    for i, row in enumerate(metadata):
        def control(info, width):
            return {"information_bits": info, "computed_crc": crc(info, width), "transmitted_crc": crc(info, width), "crc_expected_pass": True}
        vector_truth[f"r{i}.dibits"] = {"source_frame": i, "name": row["name"], "lich": row["lich"] >> 1,
            "full_lich": row["lich"], "sha256": hashlib.sha256(unpack(air[i])).hexdigest(), "raw48_hex": raw_frames[i].hex(),
            "sacch": control(row["sacch_information"], 6),
            "facch": None if row["lich"] == 0xae else control("".join(format(v, "08b") for v in bytes.fromhex(row["facch_information"])), 12),
            "transmitted_voice": row["transmitted_voice"], "source_quartet": row["source_quartet"]}
    altered_air = bytearray(air[1]); altered_air[4] ^= 1 << (7-34%8)
    altered_raw = bytearray(raw_frames[1]); altered_raw[4] ^= 1 << (7-34%8)
    vector_truth["r1_bad_lich.dibits"] = {**vector_truth["r1.dibits"], "full_lich": 0xaf,
        "sha256": hashlib.sha256(unpack(altered_air)).hexdigest(), "raw48_hex": altered_raw.hex(), "parity_valid": False}
    need(manifest["vectors"]["vectors"] == vector_truth, "Known vector metadata changed")
    vectors = {}
    for name, info in vector_truth.items():
        vectors[name] = read("vectors/" + name, info["sha256"])
        need(vectors[name] == unpack(altered_air if name == "r1_bad_lich.dibits" else air[info["source_frame"]]), "Vector bytes changed")
    ids = {"primed": [0] + list(range(9)), "cold": list(range(9)), "single_weak": [1],
           "bad_lich": [0] + list(range(9)), "zero": []}
    expected_waves = {"primed": shape([air[i] for i in ids["primed"]]), "cold": shape(air), "single_weak": shape([air[1]])}
    bad_frames = [air[i] for i in ids["primed"]]; bad_frames[2] = bytes(altered_air)
    expected_waves["bad_lich"] = shape(bad_frames)
    expected_waves["zero"] = bytes(len(expected_waves["primed"]))
    for cut in (9999, 10000, 10001):
        name = f"prefix_{cut}"; expected_waves[name] = expected_waves["primed"][:cut*4]; ids[name] = ids["primed"]
    need(set(manifest["waveforms"]) == set(expected_waves), "Waveform inventory changed")
    for name, expected in expected_waves.items():
        wave = manifest["waveforms"][name]; count = len(expected)//4
        need(wave["samples"] == count and wave["scenario"] == name, "Waveform shape/identity changed")
        need(read(wave["file"], wave["sha256"]) == expected, "Independent waveform reconstruction differs: " + name)
        need(read(wave["lineage_file"], wave["lineage_sha256"]) == b"".join(struct.pack("<I", i) for i in range(count)), "Source lineage differs")
        need(read(wave["occurrence_file"], wave["occurrence_sha256"]) == bytes(count*4), "Occurrence map differs")
        expected_frames = []
        for ordinal, i in enumerate(ids[name]):
            vector = "r1_bad_lich.dibits" if name == "bad_lich" and ordinal == 2 else f"r{i}.dibits"
            expected_frames.append({"ordinal": ordinal, "source_frame": i, "kind": metadata[i]["name"], "start": 640+3840*ordinal,
                "end": 640+3840*(ordinal+1), "vector": vector, "sha256": vector_truth[vector]["sha256"],
                "scored": not ((name in ("primed", "bad_lich") or name.startswith("prefix_")) and ordinal == 0)})
        need(wave["frames"] == expected_frames, "Canonical frame identities changed")
        original = "primed" if name in ("bad_lich", "zero") or name.startswith("prefix_") else name
        need(read(wave["original_file"], wave["original_sha256"]) == expected_waves[original]
             and wave["original_samples"] == len(expected_waves[original])//4, "Parent waveform changed")
        edit = ({"kind": "lich_parity_before_shaping", "frame_ordinal": 2, "full_frame_bit": 34} if name == "bad_lich"
                else {"kind": "zero"} if name == "zero" else {"kind": "prefix", "cut": count} if name.startswith("prefix_") else {"kind": "none"})
        need(wave["edit"] == edit, "Declared transform changed")
    return {"words": words, "channels": channels, "vectors": vector_truth, "dibits": vectors, "frames": metadata}
