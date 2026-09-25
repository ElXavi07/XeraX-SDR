"""Create the nine registered clear air-frame records once, before native use."""
import argparse
import hashlib
import json
from pathlib import Path

import arithmetic

ROOT = Path(__file__).resolve().parents[2]
VCALL = bytes.fromhex("010020038504b1000000")
TRAILER = bytes.fromhex("080020038504b1000000")
SOURCE_SHA = "8f4116e67a4c950a524c8568caf17d550e9b0b0bbdac3f9e3761ce76c0056e41"
CHANNEL_SHA = "05ed6f2d7c548e6b6e94e81bb12534afde0c2e13301791a8f1d4d2778dd6eed3"
REPORT_SHA = "22e466257755e88281fc84987eb1a44687b9a51d2ac4af66a96fd9ae04df2c8b"
PRIMARY_SHA = "e5dda2c6b072ca4eda65d2c75c3f16550a6cafb52c8fd8e04f34c47363a24ca1"


def need(ok, message):
    if not ok: raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def generate(reference, primary, output):
    need(not output.exists(), "Existing corpus is immutable")
    source = reference / "inputs/linked-source.bin"
    channel = reference / "primary/channels9.bin"
    report = reference / "report.json"
    need(sha(source) == SOURCE_SHA and sha(channel) == CHANNEL_SHA and sha(report) == REPORT_SHA,
         "Earlier independent voice reference changed")
    need(sha(primary / "manifest.json") == PRIMARY_SHA, "Pinned primary manifest changed")
    primary_manifest = json.loads((primary / "manifest.json").read_text(encoding="utf-8"))
    for entry in primary_manifest["files"]:
        p = (primary / entry["path"]).resolve()
        need(p.is_relative_to(primary.resolve()), "Primary path escaped closure")
        data = p.read_bytes()
        need(len(data) == entry["bytes"] and hashlib.sha256(data).hexdigest() == entry["sha256"], "Primary source changed")
        need(hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == entry["git_blob_sha1"],
             "Primary Git blob changed")
    words = []
    raw_source = source.read_bytes()
    for start in range(0, 130, 13):
        data = format(int.from_bytes(raw_source[start:start + 13], "big"), "0104b")
        words.extend((data[:49], data[49:98]))
    need(len(words) == 20, "Original source count changed")
    vcall_bits = "".join(format(byte, "08b") for byte in VCALL)
    rows, records, raw_frames, air_frames = [], [], [], []
    grid = [("header", 0x83, 0, None, [], VCALL)]
    grid += [(f"voice{i}", 0xAE, 3 - i % 4, i % 4, list(range(4*i, 4*i+4)), bytes(10)) for i in range(5)]
    grid += [("facch_first", 0xA6, 2, 1, [0,1,2,3], VCALL),
             ("facch_second", 0xAA, 1, 2, [4,5,6,7], VCALL),
             ("trailer", 0x83, 0, None, [], TRAILER)]
    channels = channel.read_bytes()
    for identity, (name, lich, structure, fragment, quartet, facch) in enumerate(grid):
        info = format(structure, "02b") + "000001"
        info += "00010000" + "0" * 10 if fragment is None else vcall_bits[18*fragment:18*(fragment+1)]
        sacch = int(info + "0" * 6, 2).to_bytes(4, "big")
        voice = b""
        for pair in (quartet[:2], quartet[2:]):
            voice += (int(words[pair[0]] + words[pair[1]] + "0" * 6, 2).to_bytes(13, "big") if pair else bytes(13))
        record = bytes([lich]) + sacch + facch + voice
        need(len(record) == 41, "Record dimensions changed")
        raw, air = arithmetic.encode_record(record)
        need(len(raw) == 48 and len(air) == 48, "Frame dimensions changed")
        slots = [] if lich == 0x83 else ([2,3] if lich == 0xA6 else ([0,1] if lich == 0xAA else [0,1,2,3]))
        transmitted = [{"slot": slot, "source_id": quartet[slot]} for slot in slots]
        for item in transmitted:
            start = 12 + item["slot"] * 9
            expected = channels[item["source_id"]*9:(item["source_id"]+1)*9]
            need(raw[start:start+9] == expected, "Independent voice encoder no longer agrees with frozen word reference")
        rows.append({"id": identity, "name": name, "lich": lich, "structure": structure,
                     "fragment": fragment, "source_quartet": quartet, "transmitted_voice": transmitted,
                     "sacch_information": info, "facch_information": facch.hex(),
                     "record_sha256": hashlib.sha256(record).hexdigest(),
                     "raw_sha256": hashlib.sha256(raw).hexdigest(), "air_sha256": hashlib.sha256(air).hexdigest()})
        records.append(record); raw_frames.append(raw); air_frames.append(air)
    expected = b"".join(raw + air for raw, air in zip(raw_frames, air_frames))
    need(len(expected) == 864 and len(b"".join(records)) == 369, "Registered grid dimensions changed")
    output.mkdir(parents=True, exist_ok=False)
    for name, data in {"input.records41": b"".join(records), "expected.records96": expected,
                       "expected.raw48": b"".join(raw_frames), "expected.air48": b"".join(air_frames),
                       "linked-source.bin": raw_source, "voice-reference.channels9": channels,
                       "voice-reference-report.json": report.read_bytes(),
                       "primary-manifest.json": (primary / "manifest.json").read_bytes(),
                       "NXDNControl.cpp": (primary / "MMDVM-Host/NXDNControl.cpp").read_bytes()}.items():
        (output / name).write_bytes(data)
    save(output / "frames.json", rows)
    generation = [Path(__file__), Path(arithmetic.__file__),
                  ROOT / "experiments/nxdn_frames/generate_vectors.py", ROOT / "experiments/nxdn_voice_words_v1/encoding.py"]
    save(output / "manifest.json", {"schema": 1, "kind": "nxdn_air_v1", "frames": 9,
        "input_bytes": 369, "output_bytes": 864, "sacch_calls": 9, "facch_calls": 6, "voice_pair_calls": 12,
        "transmitted_voice_words": 24, "partial_second_sacch_cycle": True,
        "voice_reference_report_sha256": REPORT_SHA, "primary_manifest_sha256": PRIMARY_SHA,
        "generation_sources": {str(p.relative_to(ROOT)): sha(p) for p in generation},
        "files": {p.name: {"bytes": p.stat().st_size, "sha256": sha(p)} for p in sorted(output.iterdir())},
        "scope": "clear complete-frame construction only; no receiver, I/Q, speech, timing or privacy"})
    return {"frames": 9, "manifest_sha256": sha(output / "manifest.json")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("reference", "primary", "output"): parser.add_argument(name, type=Path)
    args = parser.parse_args()
    print(json.dumps(generate(args.reference.resolve(), args.primary.resolve(), args.output.resolve())))
