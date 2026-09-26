"""Independent evidence checker for the registered nine-frame NXDN reference.

No arithmetic, historical encoder, or receiver module is imported. The known
source records are rebuilt directly; voice channel bytes and the primary Host
whitening constant are separately pinned artifacts, not receiver observations.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
SOURCE_SHA = "8f4116e67a4c950a524c8568caf17d550e9b0b0bbdac3f9e3761ce76c0056e41"
CHANNEL_SHA = "05ed6f2d7c548e6b6e94e81bb12534afde0c2e13301791a8f1d4d2778dd6eed3"
REPORT_SHA = "22e466257755e88281fc84987eb1a44687b9a51d2ac4af66a96fd9ae04df2c8b"
PRIMARY_SHA = "e5dda2c6b072ca4eda65d2c75c3f16550a6cafb52c8fd8e04f34c47363a24ca1"
CONTROL_SHA = "f52eb28581885be4dfc7500867dd43458385bad564ea45f6326f75133f2cb1a4"
PINS = {"MMDVM-Host": "590c531391dfd3146073afbc3956f70d42c62a46",
        "NXDNClients": "8950677e9876e577fb87b955cfa93bacd059209d"}
FILES = {"input.records41", "expected.records96", "expected.raw48", "expected.air48",
         "linked-source.bin", "voice-reference.channels9", "voice-reference-report.json",
         "primary-manifest.json", "NXDNControl.cpp", "frames.json"}
SOURCES = {"experiments/nxdn_air_v1/prepare.py", "experiments/nxdn_air_v1/arithmetic.py",
           "experiments/nxdn_frames/generate_vectors.py", "experiments/nxdn_voice_words_v1/encoding.py"}
VCALL = bytes.fromhex("010020038504b1000000")
TRAILER = bytes.fromhex("080020038504b1000000")
SUMMARY = {"schema": 1, "kind": "nxdn_air_primary", "frames": 9, "input_bytes": 369,
           "output_bytes": 864, "sacch_calls": 9, "facch_calls": 6, "voice_pair_calls": 12}
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def _need(ok, message):
    if not ok:
        raise ValueError(message)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _object(pairs):
    result = {}
    for key, value in pairs:
        _need(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result


def _nonfinite(value):
    raise ValueError("Nonfinite JSON token: " + value)


def _json(raw):
    return json.loads(raw, object_pairs_hook=_object, parse_constant=_nonfinite)


def _exact(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(_exact(actual[k], value) for k, value in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(_exact(a, b) for a, b in zip(actual, expected))
    return actual == expected


def _bits(raw):
    return "".join(str((byte >> shift) & 1) for byte in raw for shift in range(7, -1, -1))


def _source_words(source):
    words = []
    for offset in range(0, 130, 13):
        unit = source[offset:offset + 13]
        for start in (0, 49):
            words.append("".join(str((unit[i // 8] >> (7 - i % 8)) & 1) for i in range(start, start + 49)))
    return words


def _registered_grid():
    grid = [("header", 0x83, 0, None, [], VCALL)]
    for voice in range(5):
        grid.append(("voice" + str(voice), 0xAE, 3 - voice % 4, voice % 4,
                     list(range(voice * 4, voice * 4 + 4)), bytes(10)))
    grid.extend((("facch_first", 0xA6, 2, 1, [0, 1, 2, 3], VCALL),
                 ("facch_second", 0xAA, 1, 2, [4, 5, 6, 7], VCALL),
                 ("trailer", 0x83, 0, None, [], TRAILER)))
    return grid


def _read_files(directory, manifest):
    entries = manifest.get("files")
    _need(type(entries) is dict and set(entries) == FILES, "Input file inventory changed")
    result = {}
    for name in sorted(FILES):
        metadata = entries[name]
        _need(type(metadata) is dict and set(metadata) == {"bytes", "sha256"}, "File metadata shape changed")
        _need(type(metadata["bytes"]) is int and metadata["bytes"] >= 0
              and type(metadata["sha256"]) is str and HEX64.fullmatch(metadata["sha256"]), "Invalid file identity")
        path = (directory / name).resolve()
        _need(path.is_relative_to(directory), "Input path escaped directory")
        raw = path.read_bytes()
        _need(len(raw) == metadata["bytes"] and _sha(raw) == metadata["sha256"], "File hash/size changed: " + name)
        result[name] = raw
    return result


def _validate_sources(manifest):
    original = manifest.get("generation_sources")
    _need(type(original) is dict, "Generation source inventory missing")
    normalized = {name.replace("\\", "/"): digest for name, digest in original.items()}
    _need(len(normalized) == len(original) and set(normalized) == SOURCES, "Generation source inventory changed")
    for name, digest in normalized.items():
        _need(type(digest) is str and HEX64.fullmatch(digest), "Invalid generation-source hash")
        path = (ROOT / name).resolve()
        _need(path.is_relative_to(ROOT.resolve()), "Generation source path escaped repository")
        _need(_sha(path.read_bytes()) == digest, "Generation source changed: " + name)


def _whitening(data, manifest):
    _need(_sha(data["primary-manifest.json"]) == PRIMARY_SHA
          and manifest.get("primary_manifest_sha256") == PRIMARY_SHA, "Primary manifest identity changed")
    primary = _json(data["primary-manifest.json"])
    _need(primary.get("repositories") == PINS, "Primary repository pins changed")
    entries = [row for row in primary["files"] if row["path"] == "MMDVM-Host/NXDNControl.cpp"]
    _need(len(entries) == 1, "Primary Host source entry is not unique")
    source = data["NXDNControl.cpp"]
    entry = entries[0]
    _need(_sha(source) == entry["sha256"] == CONTROL_SHA and len(source) == entry["bytes"],
          "Primary whitening source identity changed")
    blob = hashlib.sha1(b"blob " + str(len(source)).encode("ascii") + b"\0" + source).hexdigest()
    _need(blob == entry["git_blob_sha1"] and entry["commit"] == PINS["MMDVM-Host"], "Primary Host Git identity changed")
    declarations = re.findall(rb"const\s+unsigned\s+char\s+SCRAMBLER\[\]\s*=\s*\{([^}]+)\}\s*;", source)
    _need(len(declarations) == 1, "Primary whitening declaration is not unique")
    tokens = declarations[0].strip().split(b",")
    _need(len(tokens) == 48 and all(re.fullmatch(rb"\s*0x[0-9a-fA-F]{2}U\s*", token) for token in tokens),
          "Primary whitening constant dimensions or syntax changed")
    mask = bytes(int(token.strip()[2:-1], 16) for token in tokens)
    _need(_bits(mask)[:20] == "0" * 20 and _bits(mask)[21::2] == "0" * 182, "Primary whitening domain changed")
    return mask


def validate_inputs(inputdir):
    """Reconstruct identities/records and check all frozen construction artifacts."""
    directory = Path(inputdir).resolve()
    manifest = _json((directory / "manifest.json").read_bytes())
    _need(type(manifest) is dict, "Input manifest must be an object")
    for key, value in {"schema": 1, "kind": "nxdn_air_v1", "frames": 9, "input_bytes": 369,
                       "output_bytes": 864, "sacch_calls": 9, "facch_calls": 6, "voice_pair_calls": 12,
                       "transmitted_voice_words": 24, "partial_second_sacch_cycle": True}.items():
        _need(_exact(manifest.get(key), value), "Input manifest value changed: " + key)
    data = _read_files(directory, manifest)
    _validate_sources(manifest)
    _need(len(data["linked-source.bin"]) == 130 and _sha(data["linked-source.bin"]) == SOURCE_SHA,
          "Known announcement source slice changed")
    channels = data["voice-reference.channels9"]
    _need(len(channels) == 74394 and _sha(channels) == CHANNEL_SHA, "Previously agreed voice channels changed")
    _need(_sha(data["voice-reference-report.json"]) == REPORT_SHA
          and manifest.get("voice_reference_report_sha256") == REPORT_SHA, "Voice reference report identity changed")
    previous = _json(data["voice-reference-report.json"])
    _need(all(previous.get(key) is True for key in ("measurement_pass", "progression_pass", "preservation_pass"))
          and previous.get("product_promotion") is False, "Voice reference gates changed")
    whitening = _whitening(data, manifest)
    _need(len(data["input.records41"]) == 369 and len(data["expected.raw48"]) == 432
          and len(data["expected.air48"]) == 432 and len(data["expected.records96"]) == 864, "Registered dimensions changed")
    words = _source_words(data["linked-source.bin"])
    raw_frames = [data["expected.raw48"][i:i + 48] for i in range(0, 432, 48)]
    air_frames = [data["expected.air48"][i:i + 48] for i in range(0, 432, 48)]
    _need(b"".join(raw + air for raw, air in zip(raw_frames, air_frames)) == data["expected.records96"],
          "Expected raw/air/interleaved files disagree")
    frames = _json(data["frames.json"])
    _need(type(frames) is list and len(frames) == 9, "Frame metadata count changed")
    reconstructed = []
    checked_voice = 0
    for identity, (name, lich, structure, fragment, quartet, facch) in enumerate(_registered_grid()):
        control = "00010000" + "0" * 10 if fragment is None else _bits(VCALL[:9])[fragment * 18:(fragment + 1) * 18]
        info = str(structure >> 1) + str(structure & 1) + "000001" + control
        sacch = int(info + "000000", 2).to_bytes(4, "big")
        pairs = bytes(26) if not quartet else b"".join(
            int(words[quartet[pair]] + words[quartet[pair + 1]] + "000000", 2).to_bytes(13, "big")
            for pair in (0, 2))
        record = bytes([lich]) + sacch + facch + pairs
        reconstructed.append(record)
        raw, air = raw_frames[identity], air_frames[identity]
        bits = _bits(raw)
        _need(bits[:20] == f"{0xCDF59:020b}", f"Sync changed in frame {identity}")
        logical_lich = bits[20:36:2]
        parity = sum(int(bit) for bit in logical_lich[:4]) % 2
        _need(logical_lich == f"{lich:08b}" and int(logical_lich[-1]) == parity
              and bits[21:36:2] == "1" * 8, f"LICH parity/profile/spacers changed in frame {identity}")
        _need(bytes(left ^ right for left, right in zip(raw, air)) == whitening,
              f"Raw/air primary whitening disagreement in frame {identity}")
        slots = [] if lich == 0x83 else ([2, 3] if lich == 0xA6 else [0, 1] if lich == 0xAA else [0, 1, 2, 3])
        transmitted = [{"slot": slot, "source_id": quartet[slot]} for slot in slots]
        for item in transmitted:
            start = 12 + 9 * item["slot"]
            expected = channels[9 * item["source_id"]:9 * (item["source_id"] + 1)]
            _need(raw[start:start + 9] == expected, f"Known voice interval changed in frame {identity} slot {item['slot']}")
            checked_voice += 1
        expected_metadata = {"id": identity, "name": name, "lich": lich, "structure": structure,
                             "fragment": fragment, "source_quartet": quartet, "transmitted_voice": transmitted,
                             "sacch_information": info, "facch_information": facch.hex(),
                             "record_sha256": _sha(record), "raw_sha256": _sha(raw), "air_sha256": _sha(air)}
        _need(_exact(frames[identity], expected_metadata), f"Frame identity/source metadata changed at {identity}")
    _need(b"".join(reconstructed) == data["input.records41"], "Registered input record bytes changed")
    _need(checked_voice == 24, "Transmitted voice count changed")
    _need(raw_frames[0][12:30] == raw_frames[0][30:] == raw_frames[6][12:30] == raw_frames[7][30:],
          "Repeated VCALL FACCH placement changed")
    _need(raw_frames[8][12:30] == raw_frames[8][30:], "Repeated trailer FACCH placement changed")
    return {"expected_records96": data["expected.records96"], "input_bytes": data["input.records41"],
            "frames": frames, "raw_frames": raw_frames, "air_frames": air_frames, "whitening": whitening}


def inspect_output(inputdir, output_path, summary_path):
    """Separate malformed evidence from same-size primary byte disagreement."""
    report = {"measurement_pass": False, "quality_pass": False, "pass": False, "issues": [],
              "measurement_issues": [], "quality_issues": [], "counts": {}, "details": []}
    try:
        inputs = validate_inputs(inputdir)
        actual = Path(output_path).read_bytes()
        report["counts"] = {"output_bytes": len(actual), "expected_bytes": 864, "different_bytes": 0,
                             "different_raw_bytes": 0, "different_air_bytes": 0, "different_frames": 0}
        if len(actual) != 864:
            report["measurement_issues"].append("Primary output must contain exactly nine 96-byte records")
        else:
            different_frames = set()
            for offset, (wanted, got) in enumerate(zip(inputs["expected_records96"], actual)):
                if wanted != got:
                    frame, within = divmod(offset, 96)
                    domain = "raw" if within < 48 else "air"
                    report["details"].append({"frame": frame, "domain": domain, "byte": within % 48,
                                              "expected": wanted, "actual": got})
                    report["counts"]["different_bytes"] += 1
                    report["counts"]["different_" + domain + "_bytes"] += 1
                    different_frames.add(frame)
            report["counts"]["different_frames"] = len(different_frames)
            if different_frames:
                report["quality_issues"].append("Primary raw/air bytes disagree with the frozen independent reference")
        summary = _json(Path(summary_path).read_bytes())
        _need(_exact(summary, SUMMARY), "Primary summary schema/counts changed")
        report["counts"].update({key: value for key, value in SUMMARY.items() if key not in ("schema", "kind", "output_bytes")})
        report["counts"]["known_voice_intervals"] = 24
    except (ValueError, OSError, KeyError, TypeError, OverflowError) as error:
        report["measurement_issues"].append(str(error))
    report["measurement_pass"] = not report["measurement_issues"]
    report["quality_pass"] = not report["quality_issues"]
    report["pass"] = report["measurement_pass"] and report["quality_pass"]
    report["issues"] = ["measurement: " + issue for issue in report["measurement_issues"]]
    report["issues"] += ["quality: " + issue for issue in report["quality_issues"]]
    return report
