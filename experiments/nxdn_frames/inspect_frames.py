"""Independent evidence checks for generated NXDN control-frame research.

Sample positions are delivered discriminator samples, never original complex IQ.
Schema errors raise ValueError; observed receiver failures remain in the report.
No decoder or encoder is invoked by this module.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

DOMAIN = "discriminator_samples"
SCHEMA = 2
RATE = 48000
WAVEFORM_SAMPLES = 16640
VECTOR_HASHES = {
    "valid": "f9a9ddcf3005ff69815ac6edef66afbd9d2188bb17d327fcdb98c26f49d5c7ef",
    "wrong_all_crc": "14a140e5706e58ecd9b5d72ab96e6a5c1edbbc8f3f4072a019d0c5f174c6a7c9",
    "wrong_lich": "94f5a65aea462e1a4b046a3b32b47b7c2cf0cc61d19967c22490c358e11243ed",
}


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


def _integer(value, label, minimum=0, maximum=(1 << 63) - 1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Invalid integer: " + label)


def _read(path, limit):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Symlink evidence is not accepted: " + path.name)
    with path.open("rb") as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Evidence exceeds size limit: " + path.name)
    return raw


def _json(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite JSON constant: " + value)))


def _truth(vectors_path):
    """Bind metadata to the exact independently frozen numeric-dibit arrays."""
    path = Path(vectors_path).resolve()
    raw = _read(path, 256 * 1024)
    data = _json(raw)
    if data.get("schema") != 1 or data.get("kind") != "independent_nxdn_control_vectors":
        raise ValueError("Wrong vector manifest")
    if set(data.get("frames", {})) != set(VECTOR_HASHES):
        raise ValueError("Missing fixed vector variants")
    hashes = {str(path): hashlib.sha256(raw).hexdigest()}
    for variant, expected_hash in VECTOR_HASHES.items():
        row = data["frames"][variant]
        filename = variant + ".dibits"
        if row.get("file") != filename or row.get("sha256") != expected_hash:
            raise ValueError("Changed fixed vector identity")
        frame_raw = _read(path.parent / filename, 192)
        if hashlib.sha256(frame_raw).hexdigest() != expected_hash:
            raise ValueError("Changed fixed vector bytes")
        hashes[str(path.parent / filename)] = expected_hash
        if row.get("air_dibits") != list(frame_raw):
            raise ValueError("Vector array disagrees with frozen bytes")
        for channel, count, information, crc in (("sacch", 26, "00010111000100000000000000", 0x12),
                                                ("facch_a", 80, "00010000" + "0" * 72, 0x830),
                                                ("facch_b", 80, "00010000" + "0" * 72, 0x830)):
            channel_row = row.get(channel, {})
            width = 6 if count == 26 else 12
            transmitted = crc ^ ((1 << (width - 1)) if variant == "wrong_all_crc" else 0)
            if (channel_row.get("information_bits") != information or channel_row.get("computed_crc") != crc
                    or channel_row.get("transmitted_crc") != transmitted or channel_row.get("crc_width") != width
                    or channel_row.get("check_bits") != format(transmitted, "0%db" % width)):
                raise ValueError("Changed independently expected channel metadata")
        if row.get("lich_full_byte") != (0x82 if variant == "wrong_lich" else 0x83):
            raise ValueError("Changed expected LICH metadata")
    return data["frames"], hashes


UNAVAILABLE = {"original_iq_samples", "pcm_latency"}
COMMON = {"schema", "kind"} | UNAVAILABLE
CASE = COMMON | {"id", "scenario", "ramp", "offset", "chunk", "domain", "rate_hz", "waveform_samples", "pop_trace", "baseline", "observed"}
DIRECT = COMMON | {"variant", "events", "errors"}
SUMMARY = COMMON | {"cases", "direct_cases", "failures", "domain", "rate_hz"}
RUN = {"frames", "events", "dispatches", "voice_requests", "other_side_effects", "errors", "pop_count", "skipped_samples", "lineage_errors", "source_frontier", "exhausted"}
FRAME = {"sync_code", "provider_sync", "cache_sync_pos", "cache_sync_len", "provider_end", "cache_end_pos", "cache_end_len", "result", "confirmed", "source_truncated", "last_sync", "dispatch_begin", "dispatch_end", "voice_after", "crc_begin", "crc_end", "sync_consumed", "end_consumed", "pop_sync", "pop_end"}
CALLBACK_FRAME = {"crc_begin", "crc_end", "sync_consumed", "end_consumed", "pop_sync", "pop_end"}
CRC = {"frame_call", "channel", "part", "computed", "received", "soft_pass", "fallback", "bits", "consumed_end", "pop_count"}
SCENARIOS = ("valid", "bad_crc", "bad_lich", "mixed", "one_fsw", "zero", "random")
MATRIX = {(scenario, ramp, offset, chunk) for scenario in SCENARIOS for ramp in (8, 14)
          for offset in (range(20) if scenario == "valid" else (0,)) for chunk in (1, 37, 512)}


def _scope(row, domain=True):
    if type(row["schema"]) is not int or row["schema"] != SCHEMA:
        raise ValueError("Unsupported observation schema")
    if any(row[key] is not None for key in UNAVAILABLE):
        raise ValueError("Original-IQ and PCM measurements must remain null")
    if domain and (row["domain"] != DOMAIN or type(row["rate_hz"]) is not int or row["rate_hz"] != RATE):
        raise ValueError("Wrong sample domain/rate")


def _bit_string(value, length, label):
    if not isinstance(value, str) or len(value) != length or any(bit not in "01" for bit in value):
        raise ValueError("Invalid bit string: " + label)


def _event(event):
    _keys(event, CRC, "CRC event")
    for key in CRC - {"bits"}:
        _integer(event[key], key, -1 if key == "frame_call" else 0)
    if event["channel"] not in (1, 2) or event["part"] not in ((0,) if event["channel"] == 1 else (1, 2)):
        raise ValueError("Invalid channel/part")
    count, maximum = (26, 63) if event["channel"] == 1 else (80, 4095)
    _bit_string(event["bits"], count, "CRC information")
    if event["computed"] > maximum or event["received"] > maximum or event["soft_pass"] > 1 or event["fallback"] > 1:
        raise ValueError("CRC fields exceed declared width")


def _run(run, observed):
    _keys(run, RUN, "run")
    for key in RUN - {"frames", "events", "dispatches"}:
        _integer(run[key], key)
    if run["exhausted"] not in (0, 1):
        raise ValueError("Invalid exhaustion flag")
    for key, limit in (("frames", 16), ("events", 48), ("dispatches", 64)):
        if not isinstance(run[key], list) or len(run[key]) > limit:
            raise ValueError("Invalid bounded " + key)
    for event in run["events"]:
        _event(event)
    for dispatch in run["dispatches"]:
        _keys(dispatch, {"length", "bits"}, "dispatch")
        _integer(dispatch["length"], "dispatch length", maximum=512)
        _bit_string(dispatch["bits"], dispatch["length"], "dispatch")
    for frame in run["frames"]:
        _keys(frame, FRAME, "frame")
        for key in FRAME:
            if key in ("sync_consumed", "end_consumed") and not observed:
                if frame[key] is not None:
                    raise ValueError("Disabled observer has a sample frontier")
            else:
                _integer(frame[key], key, -(1 << 31) if key in ("sync_code", "last_sync") else 0)
        if frame["result"] not in (0, 1, 2) or frame["confirmed"] not in (0, 1) or frame["source_truncated"] not in (0, 1):
            raise ValueError("Invalid frame result/confirmation")


def _actual_crc(bit_string, width):
    # Polynomial long division is independent of the production register loop.
    polynomial = (1 << width) | (0x27 if width == 6 else 0x80F)
    dividend = (((1 << width) - 1) << len(bit_string)) ^ (int(bit_string, 2) << width)
    while dividend.bit_length() >= polynomial.bit_length():
        dividend ^= polynomial << (dividend.bit_length() - polynomial.bit_length())
    return dividend


def _event_key(event):
    return "sacch" if event["channel"] == 1 else ("facch_a" if event["part"] == 1 else "facch_b")


def _source_variant(scenario, frame_index):
    if scenario == "valid":
        return "valid"
    if scenario == "bad_crc":
        return "wrong_all_crc"
    if scenario == "bad_lich":
        return "wrong_lich"
    if scenario == "mixed":
        return ("valid", "valid", "wrong_all_crc", "wrong_lich")[frame_index]
    return None


def analyze(log_path, artifact_dir, vectors_path):
    """Read/hash each named file once; return contract and receiver gates."""
    truth, input_hashes = _truth(vectors_path)
    raw = _read(log_path, 16 * 1024 * 1024)
    lines = raw.decode("utf-8").splitlines()
    if not lines or len(lines) > 160 or any(not line.strip() for line in lines):
        raise ValueError("Expected at most 159 bounded observations and one summary")
    rows = [_json(line.encode("utf-8")) for line in lines]
    summary = rows[-1]
    _keys(summary, SUMMARY, "summary")
    _scope(summary)
    if summary["kind"] != "summary":
        raise ValueError("Missing terminal summary")
    for key in ("cases", "direct_cases", "failures"):
        _integer(summary[key], key)
    instrumentation, direct_errors, receiver = [], [], []
    hashes, results, direct_results, seen, direct_seen = {}, [], [], set(), set()
    directory = Path(artifact_dir).resolve()

    def fail(target, identity, reason):
        target.append({"case": identity, "reason": reason})

    def check_event(event, identity):
        width = 6 if event["channel"] == 1 else 12
        if event["computed"] != _actual_crc(event["bits"], width):
            fail(instrumentation, identity, "computed_crc_disagrees_with_reported_information")
        if event["fallback"] != 1 - event["soft_pass"]:
            fail(instrumentation, identity, "inconsistent_fallback_flag")
        if event["soft_pass"] and event["computed"] != event["received"]:
            fail(instrumentation, identity, "soft_pass_with_final_crc_failure")

    def exact_channels(events, variant):
        if [_event_key(event) for event in events] != ["sacch", "facch_a", "facch_b"]:
            return False
        return all(event["bits"] == truth[variant][_event_key(event)]["information_bits"]
                   and event["computed"] == truth[variant][_event_key(event)]["computed_crc"]
                   and event["received"] == truth[variant][_event_key(event)]["transmitted_crc"] for event in events)

    for row in rows[:-1]:
        if not isinstance(row, dict):
            raise ValueError("Observation must be an object")
        if row.get("kind") == "direct":
            _keys(row, DIRECT, "direct block")
            _scope(row, False)
            variant = row["variant"]
            if variant not in VECTOR_HASHES:
                raise ValueError("Unknown direct variant")
            _integer(row["errors"], "direct errors")
            if not isinstance(row["events"], list) or len(row["events"]) > 3:
                raise ValueError("Invalid direct events")
            if variant in direct_seen or seen:
                fail(instrumentation, variant, "duplicate_or_misordered_direct_case")
            direct_seen.add(variant)
            for event in row["events"]:
                _event(event)
                check_event(event, variant)
                if event["frame_call"] != -1 or event["consumed_end"] or event["pop_count"]:
                    fail(instrumentation, variant, "direct_block_claims_sample_or_frame_lineage")
            exact = exact_channels(row["events"], variant)
            if row["errors"] or not exact:
                fail(direct_errors, variant, "direct_channel_bits_or_crc_mismatch")
            direct_results.append({"variant": variant, "exact_channels": exact,
                                   "passing_crc_events": sum(event["computed"] == event["received"] for event in row["events"])})
            continue
        if row.get("kind") != "case":
            raise ValueError("Unknown observation kind")
        _keys(row, CASE, "case")
        _scope(row)
        for key in ("ramp", "offset", "chunk", "waveform_samples"):
            _integer(row[key], key)
        scenario = row["scenario"]
        if not isinstance(scenario, str):
            raise ValueError("Invalid scenario")
        coordinate = (scenario, row["ramp"], row["offset"], row["chunk"])
        identity = "%s-r%d-o%d-c%d" % coordinate
        if row["id"] != identity or row["pop_trace"] != identity + ".u32le":
            raise ValueError("Wrong case/artifact identity")
        if coordinate not in MATRIX or coordinate in seen:
            fail(instrumentation, identity, "unexpected_or_duplicate_matrix_coordinate")
        seen.add(coordinate)
        if row["waveform_samples"] != WAVEFORM_SAMPLES:
            fail(instrumentation, identity, "wrong_waveform_size")
        _run(row["baseline"], False)
        _run(row["observed"], True)
        baseline, observed = row["baseline"], row["observed"]
        for key in ("voice_requests", "other_side_effects", "errors", "exhausted", "dispatches"):
            if baseline[key] != observed[key]:
                fail(instrumentation, identity, "observer_changed_" + key)
        if any(baseline[key] for key in ("events", "pop_count", "skipped_samples", "lineage_errors", "source_frontier")):
            fail(instrumentation, identity, "disabled_observer_reported_callbacks")
        if observed["errors"] or observed["lineage_errors"]:
            fail(instrumentation, identity, "native_or_lineage_error")
        if observed["voice_requests"] or observed["other_side_effects"]:
            # A false acquisition may route into a capture sink. That is a
            # measured receiver outcome, not corrupt observer evidence.
            fail(receiver, identity, "unexpected_voice_or_other_side_effect")
        if observed["exhausted"] != 1:
            fail(instrumentation, identity, "finite_input_not_exhausted")
        projected = [{key: frame[key] for key in FRAME - CALLBACK_FRAME} for frame in observed["frames"]]
        original = [{key: frame[key] for key in FRAME - CALLBACK_FRAME} for frame in baseline["frames"]]
        if projected != original:
            fail(instrumentation, identity, "observer_changed_frame_result_or_dispatch")
        for frame in baseline["frames"]:
            if any(frame[key] for key in ("crc_begin", "crc_end", "pop_sync", "pop_end")):
                fail(instrumentation, identity, "disabled_observer_has_frame_callbacks")
        path = directory / row["pop_trace"]
        if path.resolve().parent != directory:
            raise ValueError("Artifact escaped output directory")
        pop_raw = _read(path, WAVEFORM_SAMPLES * 4)
        hashes[str(path)] = hashlib.sha256(pop_raw).hexdigest()
        if len(pop_raw) % 4:
            raise ValueError("Partial u32 pop artifact")
        pops = tuple(value[0] for value in struct.iter_unpack("<I", pop_raw))
        if len(pops) != observed["pop_count"]:
            fail(instrumentation, identity, "pop_count_disagrees_with_artifact")
        if any(value < row["offset"] or value >= WAVEFORM_SAMPLES for value in pops) or any(a >= b for a, b in zip(pops, pops[1:])):
            fail(instrumentation, identity, "invalid_sample_lineage")
        frontier = pops[-1] + 1 if pops else 0
        skipped = frontier - row["offset"] - len(pops) if pops else 0
        if observed["source_frontier"] != frontier or observed["skipped_samples"] != skipped:
            fail(instrumentation, identity, "final_frontier_or_gap_count_mismatch")

        def point(count, end):
            return 0 < count <= len(pops) and pops[count - 1] + 1 == end

        for event in observed["events"]:
            check_event(event, identity)
        previous_pop, previous_crc, previous_dispatch, previous_voice = 0, 0, 0, 0
        good_frames, false_syncs, false_crc, frame_results = 0, 0, 0, []
        for frame_index, frame in enumerate(observed["frames"]):
            if frame["sync_code"] not in (28, 29):
                fail(instrumentation, identity, "unsupported_sync_invocation")
            if frame["result"] in (1, 2) and frame["confirmed"] != 1:
                fail(instrumentation, identity, "proof_or_history_without_confirmation")
            if not previous_voice <= frame["voice_after"] <= observed["voice_requests"]:
                fail(instrumentation, identity, "voice_count_not_causal")
            previous_voice = frame["voice_after"]
            if not (previous_pop < frame["pop_sync"] <= frame["pop_end"] <= len(pops)):
                fail(instrumentation, identity, "noncausal_frame_pop_interval")
            previous_pop = frame["pop_end"]
            if not point(frame["pop_sync"], frame["sync_consumed"]) or not point(frame["pop_end"], frame["end_consumed"]):
                fail(instrumentation, identity, "frame_frontier_not_popped_sample")
            for name, end, position, length in (("sync", frame["sync_consumed"], frame["cache_sync_pos"], frame["cache_sync_len"]),
                                                ("end", frame["end_consumed"], frame["cache_end_pos"], frame["cache_end_len"])):
                provider = frame["provider_" + name]
                if not 0 <= position <= length <= row["chunk"] or provider > WAVEFORM_SAMPLES or end != provider - (length - position):
                    fail(instrumentation, identity, "provider_read_ahead_reconciliation_failed")
            if not (frame["crc_begin"] == previous_crc <= frame["crc_end"] <= len(observed["events"])):
                fail(instrumentation, identity, "invalid_crc_event_partition")
            previous_crc = frame["crc_end"]
            if not (frame["dispatch_begin"] == previous_dispatch <= frame["dispatch_end"] <= len(observed["dispatches"])):
                fail(instrumentation, identity, "invalid_dispatch_partition")
            previous_dispatch = frame["dispatch_end"]
            events = observed["events"][frame["crc_begin"]:frame["crc_end"]]
            for event in events:
                if (event["frame_call"] != frame_index or event["consumed_end"] != frame["end_consumed"]
                        or event["pop_count"] != frame["pop_end"]):
                    fail(instrumentation, identity, "crc_event_not_at_enclosing_frame_frontier")
            matches = [index for index in range(4) if abs(frame["sync_consumed"] - (840 + 3840 * index)) <= 20]
            source_frame = matches[0] if matches else None
            # The frozen positive waveform cannot supply inverted-polarity
            # truth just because a wrong-polarity accept is near its landmark.
            variant = _source_variant(scenario, source_frame) if source_frame is not None and frame["sync_code"] == 28 else None
            exact = False
            if frame["source_truncated"]:
                # The real handler may run its CRC gates after its sample
                # provider reaches EOF. Keep those results, but never claim
                # they decode a fully supplied frame or an RF false positive.
                if frame["result"] == 2:
                    fail(receiver, identity, "source_truncated_current_proof")
            elif variant == "wrong_lich":
                if events or frame["result"] == 2:
                    fail(receiver, identity, "bad_lich_emitted_crc_or_current_proof")
            elif variant is not None:
                exact = exact_channels(events, variant)
                if not exact:
                    fail(receiver, identity, "true_frame_channel_bits_or_checks_differ")
                if variant == "wrong_all_crc" and (frame["result"] == 2 or any(event["computed"] == event["received"] for event in events)):
                    fail(receiver, identity, "bad_crc_has_fresh_evidence")
                if variant == "valid" and exact and frame["result"] == 2:
                    good_frames += 1
            elif frame["result"] == 2:
                fail(receiver, identity, "inverted_current_proof" if frame["sync_code"] == 29 else "false_or_nonprotocol_current_proof")
            if source_frame is None:
                false_syncs += 1
                false_crc += sum(event["computed"] == event["received"] for event in events)
            frame_results.append({"call": frame_index, "sync_consumed": frame["sync_consumed"],
                                  "sync_code": frame["sync_code"],
                                  "end_consumed": frame["end_consumed"], "source_frame": source_frame,
                                  "expected_variant": variant, "current_proof": frame["result"] == 2,
                                  "source_truncated": bool(frame["source_truncated"]),
                                  "exact_channels": exact, "crc_events": len(events)})
        if (previous_crc != len(observed["events"]) or previous_dispatch != len(observed["dispatches"])
                or previous_voice != observed["voice_requests"]):
            fail(instrumentation, identity, "unassociated_events_or_dispatches")
        if scenario in ("valid", "mixed") and not good_frames:
            fail(receiver, identity, "no_true_valid_complete_frame")
        results.append({"id": identity, "scenario": scenario, "valid_complete_frames": good_frames,
                        "inverted_syncs": sum(frame["sync_code"] == 29 for frame in observed["frames"]),
                        "off_boundary_syncs": false_syncs, "off_boundary_passing_crc_events": false_crc,
                        "crc_events": len(observed["events"]),
                        "passing_crc_events": sum(event["computed"] == event["received"] for event in observed["events"]),
                        "voice_requests": observed["voice_requests"], "other_side_effects": observed["other_side_effects"],
                        "frames": frame_results})
    if seen != MATRIX or summary["cases"] != 156 or len(results) != 156:
        fail(instrumentation, None, "incomplete_case_matrix")
    if direct_seen != set(VECTOR_HASHES) or summary["direct_cases"] != 3 or len(direct_results) != 3:
        fail(instrumentation, None, "incomplete_direct_matrix")
    if summary["failures"]:
        fail(instrumentation, None, "native_infrastructure_failures")
    contract = not instrumentation
    direct_pass = not direct_errors and len(direct_results) == 3
    receiver_pass = not receiver and len(results) == 156
    return {"schema": SCHEMA, "domain": DOMAIN, "rate_hz": RATE,
            "log_sha256": hashlib.sha256(raw).hexdigest(), "vector_sha256": input_hashes, "artifact_sha256": hashes,
            "instrumentation_contract_pass": contract, "direct_block_gate_pass": direct_pass,
            "measurement_contract_pass": contract and direct_pass, "receiver_gate_pass": receiver_pass,
            "gate_pass": contract and direct_pass and receiver_pass,
            "instrumentation_errors": instrumentation, "direct_errors": direct_errors, "receiver_errors": receiver,
            "cases": results, "direct_cases": direct_results,
            "valid_complete_frames": sum(case["valid_complete_frames"] for case in results),
            "off_boundary_syncs": sum(case["off_boundary_syncs"] for case in results),
            "inverted_syncs": sum(case["inverted_syncs"] for case in results),
            "original_iq_samples": None, "pcm_latency": None,
            "limits": ["Only generated discriminator-domain control frames are covered.",
                       "True-boundary classification uses a declared plus/minus20-sample FSW-end window, not original RF onset.",
                       "CRC callbacks execute after the entire frame body is read; no earlier SACCH latency is inferred.",
                       "Source-truncated completions retain CRC observations but cannot establish a fully supplied valid frame or RF false positive.",
                       "Dispatch sinks check observational parity, not the omitted application side effects.",
                       "Lineage binds declared successful pops; this is not full internal DSP state replay or performance evidence."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("artifacts", type=Path)
    parser.add_argument("vectors", type=Path)
    args = parser.parse_args(argv)
    result = analyze(args.log, args.artifacts, args.vectors)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["gate_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
