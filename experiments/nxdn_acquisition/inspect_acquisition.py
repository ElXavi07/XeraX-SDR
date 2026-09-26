"""Independent checks for the bounded NXDN discriminator acquisition observer.

This schema does not describe complex I/Q samples or validated protocol frames.
All indices are supplied discriminator samples, and a landmark is a generated
FSW symbol boundary, not the onset of RF energy. No decoder is run by analyze().
"""
import hashlib
import json
from pathlib import Path
import struct

SCHEMA = 1
DOMAIN = "discriminator_samples"
RATE = 48000
WAVEFORM_SAMPLES = 62080
PAYLOAD_LENGTH = 182
PAYLOAD_CYCLE = "0132230110322301"
SYNC_CODE = 28
RAMPS = (8, 14)
CHUNKS = (1, 37, 512)
MATRIX = {(ramp, offset, chunk) for ramp in RAMPS for offset in range(20)
          for chunk in CHUNKS}
MAX_LOG_BYTES = 4 * 1024 * 1024
UNAVAILABLE = {"original_iq_samples", "valid_frame_latency", "pcm_latency"}
FRAME = {"sync_code", "provider_end", "cache_pos", "cache_len", "payload"}
OBSERVED_FRAME = FRAME | {"consumed_end", "pop_count", "frame_index", "landmark"}
CASE = {"schema", "kind", "id", "ramp", "offset", "chunk", "domain", "rate_hz",
        "waveform_samples", "pop_trace", "baseline", "observed"} | UNAVAILABLE
SUMMARY = {"schema", "kind", "domain", "rate_hz", "cases", "lineage_control_checks",
           "failures"} | UNAVAILABLE


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def _keys(value, expected, label):
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("Missing or unknown fields in " + label)


def _integer(value, label, maximum=(1 << 63) - 1):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("Invalid integer: " + label)


def _scope(row):
    if type(row["schema"]) is not int or row["schema"] != SCHEMA:
        raise ValueError("Unsupported schema")
    if row["domain"] != DOMAIN or type(row["rate_hz"]) is not int or row["rate_hz"] != RATE:
        raise ValueError("Unsupported sample domain or rate")
    if any(row[key] is not None for key in UNAVAILABLE):
        raise ValueError("Unavailable original-IQ/frame/PCM measurements must remain null")


def _frame(frame, observed):
    _keys(frame, OBSERVED_FRAME if observed else FRAME, "frame")
    for key in frame:
        if key == "sync_code":
            # Failed sync is a legitimate observed outcome (DSD_SYNC_NONE=-1),
            # not malformed evidence. Keep it for the semantic failure report.
            if type(frame[key]) is not int or not -(1 << 31) <= frame[key] < (1 << 31):
                raise ValueError("Invalid signed sync code")
        elif key != "payload":
            _integer(frame[key], key)
    if not isinstance(frame["payload"], str) or len(frame["payload"]) > PAYLOAD_LENGTH:
        raise ValueError("Invalid payload representation")
    if any(char not in "0123" for char in frame["payload"]):
        raise ValueError("Payload must contain dibits")


def _case(row):
    _keys(row, CASE, "case")
    _scope(row)
    for key in ("ramp", "offset", "chunk", "waveform_samples"):
        _integer(row[key], key)
    if not isinstance(row["id"], str) or len(row["id"]) > 64:
        raise ValueError("Invalid case identity")
    if not isinstance(row["pop_trace"], str):
        raise ValueError("Invalid trace path")
    _keys(row["baseline"], {"frames", "callback_count"}, "baseline")
    _keys(row["observed"], {"frames", "callback_count", "skipped_samples", "lineage_errors"}, "observed")
    for branch in ("baseline", "observed"):
        _integer(row[branch]["callback_count"], branch + " callback_count")
        frames = row[branch]["frames"]
        if not isinstance(frames, list) or len(frames) > 2:
            raise ValueError("Invalid frame list")
        for frame in frames:
            _frame(frame, branch == "observed")
    for key in ("skipped_samples", "lineage_errors"):
        _integer(row["observed"][key], key)


def _trace_path(directory, name, ident):
    if name != ident + ".u32le" or "/" in name or "\\" in name or ":" in name:
        raise ValueError("Trace must be the named case artifact")
    path = (directory / name).resolve()
    if path.parent != directory:
        raise ValueError("Trace escaped artifact directory")
    return path


def _read_bounded(path, limit):
    with path.open("rb") as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Artifact exceeds fixed size bound: " + path.name)
    return raw


def analyze(log_path, artifact_dir):
    """Return measured-contract gates; malformed schemas raise ValueError.

    Every file is read once, and the same immutable bytes are validated and
    hashed. Semantic contradictions remain in the returned failure evidence.
    No timing or full-frame decoding superiority is inferred.
    """
    raw = _read_bounded(Path(log_path), MAX_LOG_BYTES)
    lines = raw.decode("utf-8").splitlines()
    if not lines or any(not line.strip() for line in lines) or len(lines) > 121:
        raise ValueError("Expected up to 120 case rows and one terminal summary")
    rows = [json.loads(line, object_pairs_hook=_object) for line in lines]
    for row in rows[:-1]:
        if not isinstance(row, dict) or row.get("kind") != "case":
            raise ValueError("Non-case before terminal summary")
        _case(row)
    summary = rows[-1]
    _keys(summary, SUMMARY, "terminal summary")
    if summary["kind"] != "summary":
        raise ValueError("Missing terminal summary")
    _scope(summary)
    for key in ("cases", "lineage_control_checks", "failures"):
        _integer(summary[key], key)

    directory = Path(artifact_dir).resolve()
    errors, seen, hashes, results = [], set(), {}, []

    def fail(case_id, reason):
        errors.append({"case": case_id, "reason": reason})

    if summary["cases"] != 120 or len(rows) - 1 != summary["cases"]:
        fail(None, "incomplete_declared_matrix")
    if summary["lineage_control_checks"] < 5:
        fail(None, "insufficient_reported_lineage_controls")
    if summary["failures"]:
        fail(None, "harness_reported_failures")
    checked_dibits = 0
    groups = {}
    for row in rows[:-1]:
        ident = row["id"]
        key = (row["ramp"], row["offset"], row["chunk"])
        expected_id = "r%d-o%d-c%d" % key
        if key not in MATRIX or ident != expected_id:
            fail(ident, "invalid_matrix_identity")
        if key in seen:
            fail(ident, "duplicate_case")
        seen.add(key)
        if row["waveform_samples"] != WAVEFORM_SAMPLES:
            fail(ident, "wrong_waveform_extent")
        path = _trace_path(directory, row["pop_trace"], ident)
        if str(path) in hashes:
            fail(ident, "reused_pop_artifact")
            continue
        data = _read_bounded(path, WAVEFORM_SAMPLES * 4)
        hashes[str(path)] = hashlib.sha256(data).hexdigest()
        if len(data) % 4:
            fail(ident, "unaligned_pop_trace")
            continue
        pops = [item[0] for item in struct.iter_unpack("<I", data)]
        observed, baseline = row["observed"], row["baseline"]
        if baseline["callback_count"] != 0:
            fail(ident, "disabled_observer_received_callbacks")
        if not pops or len(pops) != observed["callback_count"]:
            fail(ident, "callback_trace_count_mismatch")
        if observed["lineage_errors"]:
            fail(ident, "harness_reported_lineage_errors")
        if any(index < row["offset"] or index >= WAVEFORM_SAMPLES for index in pops):
            fail(ident, "pop_outside_source")
        if any(a >= b for a, b in zip(pops, pops[1:])):
            fail(ident, "nonincreasing_popped_indices")
        skipped = (pops[0] - row["offset"] + sum(b - a - 1 for a, b in zip(pops, pops[1:]))) if pops else None
        if skipped != observed["skipped_samples"]:
            fail(ident, "skipped_sample_count_mismatch")
        if len(baseline["frames"]) != 2 or len(observed["frames"]) != 2:
            fail(ident, "missing_two_sync_payload_observations")
        frames = []
        previous_pop = previous_frame = None
        for index, frame in enumerate(observed["frames"]):
            if index >= len(baseline["frames"]):
                break
            original = baseline["frames"][index]
            if any(original[field] != frame[field] for field in FRAME):
                fail(ident, "observer_changed_baseline_result")
            if frame["sync_code"] != SYNC_CODE:
                fail(ident, "not_nxdn_positive_sync")
            if not 0 < frame["cache_pos"] <= frame["cache_len"] <= row["chunk"]:
                fail(ident, "invalid_cache_bounds")
            if not row["offset"] < frame["consumed_end"] <= frame["provider_end"] <= WAVEFORM_SAMPLES:
                fail(ident, "invalid_consumed_provider_frontiers")
            if frame["consumed_end"] != frame["provider_end"] - (frame["cache_len"] - frame["cache_pos"]):
                fail(ident, "provider_read_ahead_mislabelled_as_consumed")
            count = frame["pop_count"]
            if not 1 <= count <= len(pops) or pops[count - 1] + 1 != frame["consumed_end"]:
                fail(ident, "sync_frontier_not_observed_pop")
            if previous_pop is not None and count <= previous_pop:
                fail(ident, "nonincreasing_sync_pop_count")
            previous_pop = count
            expected_frame = (frame["consumed_end"] - 640) // 3840
            if not 0 <= frame["frame_index"] < 16 or frame["frame_index"] != expected_frame:
                fail(ident, "contradictory_frame_index")
            if frame["landmark"] != 640 + frame["frame_index"] * 3840:
                fail(ident, "contradictory_generated_landmark")
            if previous_frame is not None and frame["frame_index"] != previous_frame + 1:
                fail(ident, "nonconsecutive_generated_units")
            previous_frame = frame["frame_index"]
            expected_payload = "".join(PAYLOAD_CYCLE[(frame["frame_index"] + n) % len(PAYLOAD_CYCLE)]
                                       for n in range(PAYLOAD_LENGTH))
            if frame["payload"] != expected_payload or original["payload"] != expected_payload:
                fail(ident, "payload_differs_from_independent_generator")
            else:
                checked_dibits += PAYLOAD_LENGTH * 2
            frames.append({"frame_index": frame["frame_index"], "landmark": frame["landmark"],
                           "consumed_end": frame["consumed_end"],
                           "fsw_landmark_to_sync_samples": frame["consumed_end"] - frame["landmark"],
                           "provider_read_ahead_samples": frame["provider_end"] - frame["consumed_end"]})
        signature = tuple((frame["frame_index"], frame["consumed_end"], frame["payload"])
                          for frame in observed["frames"])
        groups.setdefault((row["ramp"], row["offset"]), []).append((row["chunk"], signature))
        results.append({"id": ident, "popped_samples": len(pops), "skipped_samples": skipped, "frames": frames})
    if seen != MATRIX:
        fail(None, "missing_or_unexpected_matrix_cases")
    invariant_groups, invariant_failures = 0, []
    for key, observations in sorted(groups.items()):
        if sorted(chunk for chunk, _ in observations) != list(CHUNKS):
            invariant_failures.append({"ramp": key[0], "offset": key[1], "reason": "incomplete_chunk_group"})
        elif any(signature != observations[0][1] for _, signature in observations[1:]):
            invariant_failures.append({"ramp": key[0], "offset": key[1], "reason": "chunk_dependent_acquisition"})
        else:
            invariant_groups += 1
    return {"schema": SCHEMA, "scope": "generated discriminator sync and uncoded dibits only",
            "domain": DOMAIN, "rate_hz": RATE, "log_sha256": hashlib.sha256(raw).hexdigest(),
            "artifact_sha256": hashes, "case_count": len(rows) - 1,
            "independently_checked_dibits": checked_dibits,
            "reported_lineage_control_checks": summary["lineage_control_checks"],
            "contract_pass": not errors, "chunk_invariance_pass": invariant_groups == 40 and not invariant_failures,
            "gate_pass": not errors and invariant_groups == 40 and not invariant_failures,
            "errors": errors, "invariant_groups": invariant_groups, "invariance_errors": invariant_failures,
            "cases": results, "original_iq_samples": None, "valid_frame_latency": None, "pcm_latency": None,
            "limits": ["Landmarks describe generated FSW boundaries, not RF energy onset.",
                       "The payload is an uncoded known-dibit pattern, not CRC/FEC-validated NXDN frames.",
                       "Successful cache-pop lineage does not cover matched-filter handbacks in this profile.",
                       "Reported internal lineage controls are harness claims; binary/source provenance is external.",
                       "Provider/cache and payload checks are necessary consistency checks, not proof of omitted instrumentation."]}
