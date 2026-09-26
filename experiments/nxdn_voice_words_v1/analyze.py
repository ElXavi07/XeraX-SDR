"""Independent evidence checker for the registered clear NXDN word study.

No encoder or production decoder is imported. Source truth is reconstructed
from pinned original bytes and the registered fixed ID sequence. Channel bytes
come from the frozen arithmetic artifact, checked against the external encoder
before they may supply the production probe. Measurement and content failures
remain separate; only their conjunction is an overall pass.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


WORDS = 8266
BASE_WORDS = 73
PROBE_CALLS = 27044
PINS = {"MMDVM-Host": "590c531391dfd3146073afbc3956f70d42c62a46",
        "NXDNClients": "8950677e9876e577fb87b955cfa93bacd059209d"}
PRIMARY_MANIFEST_SHA256 = "e5dda2c6b072ca4eda65d2c75c3f16550a6cafb52c8fd8e04f34c47363a24ca1"
LINKED_SHA256 = "8f4116e67a4c950a524c8568caf17d550e9b0b0bbdac3f9e3761ce76c0056e41"
SILENCE = bytes.fromhex("f0000000000078000000000000")
INPUT_FILES = {"input.pairs13", "expected.channels9", "linked-source.bin",
               "silence-source.bin", "words.json", "primary-manifest.json"}
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX18 = re.compile(r"[0-9a-f]{18}\Z")
PRIMARY_SUMMARY = {"schema": 1, "kind": "primary_voice_encoder", "records": 4133,
                   "words": WORDS, "input_bytes": 53729, "output_bytes": 74394,
                   "encode_calls": 4133}
PROBE_FIELDS = {"seq", "word", "mutation", "mode", "input", "status", "bits",
                "input_unchanged", "c0_errors", "protected_errors", "c4_errors",
                "total_errors", "flags"}


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _object(pairs):
    result = {}
    for key, value in pairs:
        _need(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result


def _bad_constant(value):
    raise ValueError("Nonfinite JSON token: " + value)


def _json(raw):
    return json.loads(raw, object_pairs_hook=_object, parse_constant=_bad_constant)


def _integer(value, expected=None):
    return type(value) is int and (expected is None or value == expected)


def _binary(value, length):
    return type(value) is str and len(value) == length and set(value) <= {"0", "1"}


def _extract_source(raw):
    # Traverse original byte/bit coordinates directly; ignore only the six
    # source padding bits at record positions 98..103.
    result = []
    for start in range(0, len(raw), 13):
        unit = raw[start:start + 13]
        for word_start in (0, 49):
            result.append("".join(str((unit[p // 8] >> (7 - p % 8)) & 1)
                                  for p in range(word_start, word_start + 49)))
    return result


def _source_rows(linked, silence):
    rows = []
    for label, values in (("announcement", _extract_source(linked)),
                          ("upstream_silence", _extract_source(silence))):
        rows.extend((label, i, bits) for i, bits in enumerate(values))
    rows.extend((("zero", 0, "0" * 49), ("ones", 0, "1" * 49)))
    rows.extend(("onehot", i, "".join("1" if j == i else "0" for j in range(49)))
                for i in range(49))
    for value in range(4096):
        field = "".join(str((value >> shift) & 1) for shift in range(11, -1, -1))
        rows.append(("sweep_a", value, field + "0" * 37))
    for value in range(4096):
        field = "".join(str((value >> shift) & 1) for shift in range(11, -1, -1))
        rows.append(("sweep_b", value, "0" * 12 + field + "0" * 25))
    rows.append(("pair_padding", 0, "0" * 49))
    return rows


def validate_inputs(inputdir):
    """Return (source strings, channel bytes) or raise ValueError/OSError.

    Original-source padding is independently checked as provenance. Every
    normalized paired record must instead have six zero pad bits. Reading the
    encoder source hash does not import or execute that source.
    """
    root = Path(inputdir).resolve()
    manifest = _json((root / "manifest.json").read_bytes())
    _need(type(manifest) is dict, "Input manifest must be an object")
    for key, value in {"schema": 1, "words": WORDS, "base_words": BASE_WORDS,
                       "pairs": 4133, "probe_calls": PROBE_CALLS}.items():
        _need(_integer(manifest.get(key), value), "Input manifest count changed: " + key)
    _need(manifest.get("kind") == "nxdn_voice_words_v1", "Wrong input kind")
    _need(manifest.get("primary_pins") == PINS, "Primary repository pins changed")
    files = manifest.get("files")
    _need(type(files) is dict and set(files) == INPUT_FILES, "Input file inventory changed")
    data = {}
    for name in sorted(INPUT_FILES):
        entry = files[name]
        path = (root / name).resolve()
        _need(path.is_relative_to(root), "Input file escaped directory")
        _need(type(entry) is dict and set(entry) == {"bytes", "sha256"}, "Invalid input file metadata")
        _need(_integer(entry["bytes"]) and entry["bytes"] >= 0, "Invalid input byte count")
        _need(type(entry["sha256"]) is str and HEX64.fullmatch(entry["sha256"]), "Invalid input hash")
        raw = path.read_bytes()
        _need(len(raw) == entry["bytes"] and _sha(raw) == entry["sha256"], "Input hash/size changed: " + name)
        data[name] = raw

    primary_raw = data["primary-manifest.json"]
    _need(manifest.get("primary_manifest_sha256") == PRIMARY_MANIFEST_SHA256
          and _sha(primary_raw) == PRIMARY_MANIFEST_SHA256, "Primary closure identity changed")
    primary = _json(primary_raw)
    _need(primary.get("repositories") == PINS, "Primary closure pins changed")
    primary_files = {}
    for entry in primary["files"]:
        name = entry["path"]
        _need(name not in primary_files, "Duplicate primary file")
        family = name.split("/", 1)[0]
        _need(family in PINS and entry["commit"] == PINS[family], "Wrong primary file commit")
        _need(type(entry["sha256"]) is str and HEX64.fullmatch(entry["sha256"])
              and type(entry["git_blob_sha1"]) is str and HEX40.fullmatch(entry["git_blob_sha1"]),
              "Invalid primary identity fields")
        primary_files[name] = entry["sha256"]
    _need(manifest.get("primary_files") == primary_files, "Primary file identity mapping changed")
    generation = manifest.get("generation_sources")
    _need(type(generation) is dict and set(generation) == {"prepare.py", "encoding.py"},
          "Generator identity inventory changed")
    for name, digest in generation.items():
        _need(type(digest) is str and HEX64.fullmatch(digest), "Invalid generator hash")
        _need(_sha(Path(__file__).with_name(name).read_bytes()) == digest, "Generator source changed: " + name)

    linked, silence = data["linked-source.bin"], data["silence-source.bin"]
    _need(len(linked) == 130 and _sha(linked) == LINKED_SHA256, "Registered announcement slice changed")
    _need(silence == SILENCE, "Registered silence pair changed")
    linked_padding = [linked[i] & 63 for i in range(12, 130, 13)]
    _need(type(manifest.get("linked_original_padding")) is list
          and all(_integer(v) for v in manifest["linked_original_padding"])
          and manifest["linked_original_padding"] == linked_padding, "Original announcement padding changed")
    _need(_integer(manifest.get("silence_original_padding"), silence[12] & 63),
          "Original silence padding changed")
    expected = _source_rows(linked, silence)
    rows = _json(data["words.json"])
    _need(type(rows) is list and len(rows) == WORDS and len(expected) == WORDS, "Source row count changed")
    for identity, (row, truth) in enumerate(zip(rows, expected)):
        kind, source_index, bits = truth
        _need(type(row) is dict and set(row) == {"id", "kind", "source_index", "bits"},
              f"Source row schema changed at {identity}")
        _need(_integer(row["id"], identity) and _integer(row["source_index"], source_index)
              and row["kind"] == kind and _binary(row["bits"], 49) and row["bits"] == bits,
              f"Source identity/label/content changed at {identity}")

    packed = data["input.pairs13"]
    _need(len(packed) == 53729, "Normalized source dimensions changed")
    _need(all(packed[i] & 63 == 0 for i in range(12, len(packed), 13)), "Normalized source padding is nonzero")
    sources = [truth[2] for truth in expected]
    _need(_extract_source(packed) == sources, "Normalized source packing changed")
    channels = data["expected.channels9"]
    _need(len(channels) == WORDS * 9, "Expected channel dimensions changed")
    return sources, [channels[i:i + 9] for i in range(0, len(channels), 9)]


def _report(stage):
    return {"stage": stage, "measurement_pass": False, "quality_pass": False, "pass": False,
            "measurement_issues": [], "quality_issues": [], "counts": {}, "details": []}


def _finish(report):
    report["measurement_pass"] = not report["measurement_issues"]
    report["quality_pass"] = not report["quality_issues"]
    report["pass"] = report["measurement_pass"] and report["quality_pass"]
    return report


def _primary_channels(path, expected, report):
    raw = Path(path).read_bytes()
    report["counts"]["channel_bytes"] = len(raw)
    if len(raw) != WORDS * 9:
        report["measurement_issues"].append("Primary channel output dimensions changed")
        return None
    actual = [raw[i:i + 9] for i in range(0, len(raw), 9)]
    mismatches = [i for i, pair in enumerate(zip(actual, expected)) if pair[0] != pair[1]]
    report["counts"]["channel_mismatches"] = len(mismatches)
    if mismatches:
        report["quality_issues"].append(f"Primary channel mismatches: {len(mismatches)}")
        report["details"].extend({"kind": "primary_mismatch", "word": i,
                                  "expected": expected[i].hex(), "actual": actual[i].hex()} for i in mismatches)
    return actual


def inspect_primary(inputdir, primary_channels_path, stdout_path):
    report = _report("primary")
    try:
        _, expected = validate_inputs(inputdir)
        _primary_channels(primary_channels_path, expected, report)
        summary = _json(Path(stdout_path).read_bytes())
        _need(type(summary) is dict and set(summary) == set(PRIMARY_SUMMARY), "Primary summary schema changed")
        for key, value in PRIMARY_SUMMARY.items():
            _need((type(summary[key]) is int and summary[key] == value) if type(value) is int
                  else (type(summary[key]) is str and summary[key] == value), "Primary summary changed: " + key)
        report["counts"].update({"records": 4133, "words": WORDS, "encode_calls": 4133})
    except (ValueError, OSError, KeyError, TypeError, OverflowError) as error:
        report["measurement_issues"].append(str(error))
    return _finish(report)


def _case_at(sequence):
    mode = "hard" if sequence % 2 == 0 else "soft"
    if sequence < WORDS * 2:
        return sequence // 2, -1, mode
    mutation_case = (sequence - WORDS * 2) // 2
    return mutation_case // 72, mutation_case % 72, mode


def _mutation_class(position):
    if position == -1:
        return "clean", None
    linear = 18 * (position % 4) + position // 4
    if linear < 24:
        return "protected_a", None
    if linear < 47:
        return "protected_b", None
    return "unprotected_c", 24 + linear - 47


def _validate_probe_row(row):
    _need(type(row) is dict and set(row) == PROBE_FIELDS, "Probe row schema changed")
    for name in ("seq", "word", "mutation", "status", "input_unchanged", "c0_errors",
                 "protected_errors", "c4_errors", "total_errors", "flags"):
        _need(_integer(row[name]), "Noninteger probe field: " + name)
    _need(row["mode"] in ("hard", "soft") and type(row["mode"]) is str, "Invalid probe mode")
    _need(type(row["input"]) is str and HEX18.fullmatch(row["input"]), "Invalid probe input hex")
    _need(row["input_unchanged"] in (0, 1), "Invalid immutable-input indicator")
    _need(0 <= row["flags"] <= 0xFFFFFFFF, "Invalid unsigned result flags")
    _need(type(row["bits"]) is list and len(row["bits"]) == 49
          and all(type(bit) is int for bit in row["bits"]), "Invalid decoder output shape")


def inspect_probe(inputdir, primary_channels_path, rows_path):
    report = _report("probe")
    counts = report["counts"]
    counts.update({"expected_calls": PROBE_CALLS, "rows": 0, "checked_calls": 0,
                   "clean": 0, "protected_a": 0, "protected_b": 0, "unprotected_c": 0,
                   "hard": 0, "soft": 0, "wrong_output": 0, "negative_status": 0, "changed_input": 0})
    try:
        sources, expected_channels = validate_inputs(inputdir)
        channels = _primary_channels(primary_channels_path, expected_channels, report)
        if channels is None or report["quality_issues"]:
            report["measurement_issues"].append("Probe cannot be grounded in an agreed primary channel corpus")
            return _finish(report)
        with Path(rows_path).open("r", encoding="utf-8") as stream:
            for sequence, line in enumerate(stream):
                counts["rows"] += 1
                try:
                    _need(sequence < PROBE_CALLS, "Unexpected extra probe row")
                    row = _json(line)
                    _validate_probe_row(row)
                    word, mutation, mode = _case_at(sequence)
                    _need(row["seq"] == sequence and row["word"] == word
                          and row["mutation"] == mutation and row["mode"] == mode,
                          "Probe identity/order differs from the registered sequence")
                    actual_input = bytearray(channels[word])
                    if mutation != -1:
                        actual_input[mutation // 8] ^= 1 << (7 - mutation % 8)
                    _need(row["input"] == actual_input.hex(), "Probe input differs from the exact registered mutation")
                    category, source_bit = _mutation_class(mutation)
                    truth = [int(bit) for bit in sources[word]]
                    if source_bit is not None:
                        truth[source_bit] ^= 1
                    counts["checked_calls"] += 1
                    counts[category] += 1
                    counts[mode] += 1
                    failures = []
                    if row["bits"] != truth:
                        counts["wrong_output"] += 1
                        failures.append("wrong_output")
                    if row["status"] < 0:
                        counts["negative_status"] += 1
                        failures.append("negative_status")
                    if row["input_unchanged"] != 1:
                        counts["changed_input"] += 1
                        failures.append("changed_input")
                    if failures:
                        report["details"].append({"seq": sequence, "word": word, "mutation": mutation,
                                                  "mode": mode, "category": category,
                                                  "source_bit": source_bit, "failures": failures,
                                                  "expected_bits": truth, "actual_bits": row["bits"],
                                                  "status": row["status"], "input_unchanged": row["input_unchanged"]})
                except (ValueError, KeyError, TypeError, OverflowError) as error:
                    report["measurement_issues"].append(f"Row {sequence}: {error}")
        if counts["rows"] != PROBE_CALLS:
            report["measurement_issues"].append(f"Probe row count {counts['rows']} != {PROBE_CALLS}")
        for name in ("wrong_output", "negative_status", "changed_input"):
            if counts[name]:
                report["quality_issues"].append(f"{name}: {counts[name]}")
    except (ValueError, OSError, KeyError, TypeError, OverflowError) as error:
        report["measurement_issues"].append(str(error))
    return _finish(report)
