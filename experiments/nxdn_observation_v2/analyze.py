"""Independent finite-observation checker; receiver failures remain measured outcomes.

No decoder, former inspector or generator is imported. Completion is a real
symbol-counter commit, not a nonzero returned dibit or a provider refill.
"""
import collections
import hashlib
import math
from pathlib import Path
import struct

OPTIONAL = {"crc", "lich", "scch", "voice_begin", "voice_end", "mbe_begin", "mbe_end", "audio_begin", "audio_end"}
PROVIDER_FIELDS = {"provided", "cache_pos", "cache_len", "read_start", "chunk"}
COUNTERS = {"lich": "v2_lich_events", "scch": "v2_scch_events", "voice_begin": "v2_voice_calls",
            "mbe_begin": "v2_mbe_calls", "audio_begin": "v2_audio_calls"}
CONFIG = {"observation_schema": 2, "datascope": 0, "audio_out": 0, "cosine_filter": 0,
          "scanner": 0, "trunk": 0, "trunk_scan": 0, "voice_gate": 0, "visit_ms": 0,
          "msize": 1, "ssize": 128, "nxdn48": 1, "pulse_digi_rate_out": 8000,
          "floating_point": 0, "dmr_stereo": 1}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, low, high, label):
    require(type(value) is int and low <= value <= high, "Invalid " + label)
    return value


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def crc(bits, width):
    require(width in (6, 7, 12) and isinstance(bits, str) and set(bits) <= {"0", "1"}, "Malformed CRC input")
    polynomial = (1 << width) | {6: 0x27, 7: 0x09, 12: 0x80F}[width]
    value = (((1 << width) - 1) << len(bits)) ^ (int(bits or "0", 2) << width)
    for shift in range(len(bits) - 1, -1, -1):
        if value & (1 << (width + shift)):
            value ^= polynomial << shift
    return value


def semantic(rows):
    ignored = {"seq", "frontier", "pops", "observed", "crcs", "skipped"}
    return [{k: v for k, v in r.items() if k not in ignored} for r in rows if r["kind"] not in OPTIONAL]


def chunk_semantic(rows):
    return [{k: v for k, v in r.items() if k not in PROVIDER_FIELDS} for r in rows]


def common_frontier(row, samples):
    if row["eof"]:
        require(row["cache_pos"] == row["cache_len"] == 0, "EOF cache not drained")
        return samples
    integer(row["cache_len"], 0, 4096, "cache length")
    integer(row["cache_pos"], 0, row["cache_len"], "cache position")
    result = row["read_start"] + row["cache_pos"]
    require(0 <= result <= row["provided"] <= samples, "Invalid common frontier")
    return result


def classify_call(call, samples):
    before = integer(call["before"], 0, samples, "call before")
    after = integer(call["after"], before, samples, "call after")
    eb, ea = [integer(call[k], 0, 1, k) for k in ("eof_before", "eof_after")]
    sb, sa = [integer(call[k], 0, 0xffffffff, k) for k in ("symbol_before", "symbol_after")]
    require(eb <= ea, "EOF reversed within call")
    advance, committed = after - before, (sa - sb) & 0xffffffff
    require(committed in (0, 1), "Unexpected symbol-counter transition")
    if ea == 0:
        require(committed == 1 and advance == 20, "Non-EOF call did not complete real 20-sample symbol")
        return "complete"
    require(committed == 0 and after == samples, "EOF call falsely completed or missed final frontier")
    if eb:
        require(before == samples and advance == 0, "Already-EOF call invented delivery")
        return "empty_after_eof"
    require(0 <= advance < 20, "EOF crossing has impossible partial span")
    return "partial_eof" if advance else "empty_first_eof"


def inspect_calls(begin, end, trace, samples, enabled):
    calls = end["body_calls"]
    require(len(calls) == len(end["body_positions"]) == len(end["body"]) == end["body_count"], "Incomplete per-dibit record")
    require(set(end["body"]) <= set("0123"), "Malformed returned body")
    previous = (common_frontier(begin, samples), begin["eof"], begin["symbolcnt"])
    classes = []
    consumed = []
    for call, position in zip(calls, end["body_positions"]):
        require((call["before"], call["eof_before"], call["symbol_before"]) == previous, "Discontinuous body calls")
        kind = classify_call(call, samples)
        require(position == (call["after"] if kind == "complete" else 0), "Invalid source-backed dibit position")
        if enabled:
            # Trace is already required to be the exact bounded delivered-index range.
            interval = trace[call["before"]:call["after"]]
            require(interval == list(range(call["before"], call["after"])), "Call interval lacks actual sample pops")
            consumed.extend(interval)
        previous = (call["after"], call["eof_after"], call["symbol_after"])
        classes.append(kind)
    require(previous == (common_frontier(end, samples), end["eof"], end["symbolcnt"]), "Body does not reach recorded end state")
    if enabled:
        require(consumed == trace[begin["pops"]:end["pops"]], "Frame pop trace is not partitioned by calls")
    return classes


def validate_crc(row, width, count):
    require(isinstance(row["bits"], str) and len(row["bits"]) == count, "Wrong CRC information length")
    integer(row["computed"], 0, (1 << width) - 1, "computed CRC")
    integer(row["received"], 0, (1 << width) - 1, "received CRC")
    require(crc(row["bits"], width) == row["computed"], "Independent CRC mismatch")
    for key in ("soft_pass", "fallback"):
        integer(row[key], 0, 1, key)
    require(row["fallback"] == 1 - row["soft_pass"], "Fallback contradicts soft outcome")
    require(not row["soft_pass"] or row["computed"] == row["received"], "Soft pass contradicts unchanged final checkwords")
    if width == 7:
        require(isinstance(row["check_bits"], str) and len(row["check_bits"]) == 7
                and set(row["check_bits"]) <= {"0", "1"}, "Malformed received CRC7 bits")
        require(int(row["check_bits"], 2) == row["received"], "Received CRC7 bits disagree")
        integer(row["direction"], 0, 1, "SCCH direction")


def lich_from_body(body, seed):
    require(len(body) >= 8, "Missing LICH dibits")
    seed = 228 if seed == 0 else min(seed, 511)
    result = 0
    for dibit in map(int, body[:8]):
        value = dibit ^ ((seed & 1) << 1)
        result = (result << 1) | (value >> 1)
        seed = (seed >> 1) | ((((seed >> 4) ^ seed) & 1) << 8)
    return result


def validate_lich(frame):
    require(len(frame["lich"]) == 1, "Frame lacks exactly one LICH decision")
    row = frame["lich"][0]
    full = lich_from_body(frame["end"]["body"], frame["begin"]["pn95"])
    value = full >> 1
    parity = sum((full >> i) & 1 for i in range(1 if value in (0x08, 0x4a, 0x48, 0x46) else 4, 8)) & 1
    require((row["full_lich"], row["lich"], row["parity_received"], row["parity_computed"])
            == (full, value, full & 1, parity), "LICH observation disagrees with real returned dibits")
    integer(row["result"], 0, 1, "LICH result")
    require(isinstance(row["reason"], str) and bool(row["reason"]), "Missing LICH reason")
    require(not row["result"] or (full & 1) == parity, "Accepted bad LICH parity")
    for key in ("voice", "facch", "pich_tch"):
        integer(row[key], 0, 3, key)
    for key in ("scch", "idas", "sacch"):
        integer(row[key], 0, 1, key)
    # The registered known profiles and the prior incidental Japanese DCR path.
    expected = {0x41: (0, 0, 0, 0, 1, 3), 0x77: (3, 1, 0, 1, 0, 0), 0x48: (0, 0, 3, 0, 0, 0)}
    if row["result"] and value in expected:
        require(tuple(row[k] for k in ("voice", "scch", "pich_tch", "idas", "sacch", "facch")) == expected[value],
                "Known LICH profile flags disagree")
    require(frame["end"]["body_count"] == (182 if row["result"] else 8), "LICH decision/body length disagree")
    if row["result"] and value in (0x41, 0x77, 0x48):
        expected_channels = [(1, 0), (2, 1), (2, 2)] if value == 0x41 else []
        require([(e["channel"], e["part"]) for e in frame["crcs"]] == expected_channels, "Known profile CRC6/12 observation incomplete")
    if not row["result"]:
        require(not frame["crcs"] and not frame["scch"], "Rejected LICH has channel observations")
    for event in frame["scch"]:
        require(row["result"] == 1 and row["scch"] == 1 and event["direction"] == value % 2,
                "SCCH result does not belong to applied profile")
    require(len(frame["scch"]) == int(bool(row["result"] and row["scch"])), "Applied SCCH path lacks final observation")
    require(row["symbolcnt"] == frame["end"]["body_calls"][7]["symbol_after"], "LICH decision is not after eight dibit calls")
    require(row["frontier"] == frame["end"]["body_calls"][7]["after"], "LICH decision sample boundary differs")
    expected_reason = "accepted" if row["result"] else ("parity_reject" if (full & 1) != parity else "unsupported_profile")
    require(row["reason"] == expected_reason, "LICH reason contradicts fixed conventional path")
    if value in (0x41, 0x77, 0x48):
        voices = [e for e in frame["events"] if e["kind"] == "voice_begin"]
        # nxdn_process_voice_and_mbe gates on confirmation after channel decode.
        # The LICH snapshot precedes that evidence. End-frame accounting preserves
        # sticky confirmation, so the end snapshot witnesses this fixed path's gate.
        confirmed = integer(frame["end"]["confirmed"], 0, 1, "end confirmation")
        expected_calls = int(bool(row["result"] and row["voice"] and confirmed))
        require(len(voices) == expected_calls, "Voice calls disagree with profile/confirmation guard")
        require(all(e["value"] == row["voice"] for e in voices), "Voice wrapper format differs from applied profile")
        require(all(e["confirmed"] == 1 for e in voices), "Voice call began without confirmation")


def validate_audio(row):
    require(row["pcm_domain"] == "internal_post_gain_float160_and_staged_short160", "Wrong internal PCM domain")
    integer(row["float_finite"], 0, 160, "float finite count")
    # Nonfinite receiver output is observable behavior, not invented recorder
    # failure. These statistics deliberately cover only the finite elements.
    fn = integer(row["float_nonzero"], 0, row["float_finite"], "finite float nonzero count")
    sn = integer(row["short_nonzero"], 0, 160, "short nonzero count")
    fp, energy = row["float_peak"], row["float_energy"]
    require(all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in (fp, energy)), "Malformed float statistics")
    require((fn == 0) == (fp == 0) == (energy == 0), "Inconsistent float statistics")
    require(energy + max(1e-15, energy * 1e-5) >= fp * fp
            and energy <= 160 * fp * fp + max(1e-15, energy * 1e-5), "Impossible float energy")
    peak = integer(row["short_peak"], 0, 32768, "short peak")
    require((sn == 0) == (peak == 0), "Inconsistent short statistics")
    integer(row["short_checksum"], 0, 0xffffffff, "short checksum")
    if sn == 0:
        checksum = 2166136261
        for _ in range(320): checksum = (checksum * 16777619) & 0xffffffff
        require(row["short_checksum"] == checksum, "Zero short buffer checksum differs")


def read_inputs(wave, manifest, inputs):
    inputs = Path(inputs).resolve()
    def read(relative, expected=None):
        path = (inputs / relative).resolve()
        require(path.is_relative_to(inputs), "Input escaped directory")
        raw = path.read_bytes()
        if expected:
            require(hashlib.sha256(raw).hexdigest() == expected, "Input hash mismatch")
        return raw
    samples = integer(wave["samples"], 1, 100000, "input sample count")
    raw = read(wave["file"], wave["sha256"])
    require(len(raw) == 4 * samples and all(math.isfinite(v[0]) for v in struct.iter_unpack("<f", raw)), "Malformed finite input")
    if "lineage_file" in wave:
        raw_map = read(wave["lineage_file"], wave["lineage_sha256"])
        require(len(raw_map) % 4 == 0 and len(raw_map) >= samples * 4, "Short lineage map")
        origin = list(struct.unpack("<" + "I" * (len(raw_map) // 4), raw_map))[:samples]
    else:
        origin = list(range(samples))
    if "original_file" in wave:
        original = read(wave["original_file"], wave["original_sha256"])
        n = integer(wave["original_samples"], samples if wave["edit"]["kind"] != "drop" else 1, 100000, "original length")
        require(len(original) == 4 * n, "Original waveform length differs")
        edit = wave["edit"]; q = integer(edit["source_start"], 0, n, "edit start")
        count = integer(edit["count"], 0, n - q, "edit count")
        expected_origin = list(range(n)); expected_wave = original
        if edit["kind"] == "prefix":
            require(q == samples and count == n - q, "Prefix definition differs")
            expected_origin = expected_origin[:q]; expected_wave = original[:q * 4]
        elif edit["kind"] == "drop":
            require(count > 0, "Empty declared deletion")
            expected_origin = expected_origin[:q] + expected_origin[q + count:]
            expected_wave = original[:q * 4] + original[(q + count) * 4:]
        elif edit["kind"] == "blank":
            require(count > 0, "Empty declared blank")
            expected_wave = original[:q * 4] + bytes(count * 4) + original[(q + count) * 4:]
        else:
            require(edit["kind"] == "none" and count == 0, "Unregistered input edit")
        require(origin == expected_origin and raw == expected_wave, "Declared waveform edit/lineage mismatch")
    vectors = {}
    for name, truth in manifest["vectors"]["vectors"].items():
        vector = read("vectors/" + name, truth.get("sha256"))
        require(len(vector) == 192 and set(vector) <= {0, 1, 2, 3}, "Malformed source vector")
        vectors[name] = vector
    return origin, vectors


def source_identity(frame, waveform, origin):
    end = frame["end"]
    if frame["begin"]["eof"] or end["eof"] or frame["begin"]["sync"] != 28 or not frame["classes"]:
        return None
    if any(c != "complete" for c in frame["classes"]) or end["body_count"] not in (8, 182):
        return None
    mapped = [origin[p - 1] + 1 for p in end["body_positions"]]
    matches = []
    for truth in waveform["frames"]:
        deviations = [p - (truth["start"] + (11 + i) * 20) for i, p in enumerate(mapped)]
        if all(-20 < d < 20 for d in deviations):
            matches.append({**truth, "deviation_min": min(deviations), "deviation_max": max(deviations)})
    require(len(matches) <= 1, "Ambiguous canonical attribution")
    return matches[0] if matches else None


def inspect(rows, trace_path, case, manifest, inputs, enabled):
    require(len(rows) >= 4 and [r["kind"] for r in rows[:2]] == ["configuration", "initialized"]
            and [r["kind"] for r in rows[-2:]] == ["completed", "summary"], "Missing recorder boundaries")
    require(all(rows[0].get(k) == v for k, v in CONFIG.items()), "Configuration contract changed")
    require([r["seq"] for r in rows] == list(range(len(rows))), "Nonconsecutive event sequence")
    require(sum(r["kind"] == "completed" for r in rows) == 1, "Repeated completion")
    summary = rows[-1]; wave = manifest["waveforms"][case["waveform"]]; samples = wave["samples"]
    require(summary["observed"] == enabled and summary["fast"] == case["fast"] == 0
            and summary["chunk"] == case["chunk"] and case["chunk"] in (37, 512), "Invocation identity mismatch")
    require(summary["errors"] == summary["starts"] == summary["tunes"] == 0, "Native recorder/backend error")
    require(summary["eof"] == 1 and summary["provided"] == summary["samples"] == samples, "Finite input not exhausted")
    origin, vectors = read_inputs(wave, manifest, inputs)
    raw = Path(trace_path).read_bytes()
    require(len(raw) % 4 == 0, "Partial trace word")
    trace = list(struct.unpack("<" + "I" * (len(raw) // 4), raw))
    require(trace == (list(range(samples)) if enabled else []), "Delivered trace is not the exact finite source")
    require(summary["pops"] == len(trace) and summary["skipped"] == 0, "Incorrect pop/gap summary")
    require(summary["frontier"] == (samples if enabled else 0), "Incorrect final observed frontier")
    allowed = OPTIONAL | {"configuration", "initialized", "completed", "summary", "search_begin", "search_end",
        "reset_begin", "reset_end", "dispatch_begin", "dispatch_end", "frame_begin", "frame_end", "backend_rate", "backend_reacquire"}
    for key in ("provided", "frontier", "pops", "eof"):
        require(all(a[key] <= b[key] for a, b in zip(rows, rows[1:])), "Nonmonotone " + key)
    frames, searches, resets, stack = [], [], [], []
    search = reset = dispatch = active = last_sync = None
    counters = collections.Counter(); classes = collections.Counter()
    for row in rows:
        kind, fid = row["kind"], row["frame"]
        require(kind in allowed, "Unknown event kind")
        integer(row["eof"], 0, 1, "event EOF")
        integer(row["provided"], 0, samples, "provider position")
        integer(row["pops"], 0, len(trace), "event pop count")
        require(row["frontier"] == row["pops"], "Observed event frontier disagrees with pop trace")
        if "audio_indices" in row:
            require(len(row["audio_indices"]) == 4 and all(type(x) is int and 0 <= x <= 1000000 for x in row["audio_indices"]), "Invalid audio indices")
        if kind in OPTIONAL:
            require(enabled and active is not None and "end" not in active and fid == active["begin"]["frame"], "Optional event outside observed frame")
            counters[kind] += 1
            active["events"].append(row)
        if kind == "search_begin":
            require(search is None and dispatch is None and active is None, "Nested search")
            search = row
        elif kind == "search_end":
            require(search is not None, "Unpaired search")
            searches.append({"begin": search, "end": row}); search = None; last_sync = row["value"]
        elif kind == "reset_begin":
            require(reset is None and dispatch is None and active is None, "Nested reset")
            reset = row
        elif kind == "reset_end":
            require(reset is not None, "Unpaired reset")
            resets.append({"begin": reset, "end": row}); reset = None
        elif kind == "dispatch_begin":
            require(dispatch is None and active is None and search is None and reset is None
                    and row["sync"] == last_sync and row["sync"] in (28, 29), "Unowned dispatch")
            require(fid == len(frames), "Dispatch id discontinuity")
            dispatch = {"begin": row}; last_sync = None
        elif kind == "frame_begin":
            require(dispatch is not None and fid == dispatch["begin"]["frame"] and active is None, "Unowned frame")
            active = {"begin": row, "crcs": [], "lich": [], "scch": [], "events": []}
            require(row["sps"] == 20 and row["rf_mod"] == 2, "In-frame fixed discriminator profile changed")
        elif kind in ("crc", "scch"):
            if kind == "crc":
                require((row["channel"], row["part"]) in ((1, 0), (2, 1), (2, 2)), "Unknown CRC6/12 channel")
                validate_crc(row, 6 if row["channel"] == 1 else 12, 26 if row["channel"] == 1 else 80)
                active["crcs"].append(row)
            else:
                validate_crc(row, 7, 25); active["scch"].append(row)
        elif kind == "lich":
            active["lich"].append(row)
        elif kind.endswith("_begin") and kind.split("_")[0] in ("voice", "mbe", "audio"):
            category = kind.split("_")[0]
            require((category == "voice" and not stack) or (category == "mbe" and stack and stack[-1][0] == "voice")
                    or (category == "audio" and stack and stack[-1][0] == "mbe"), "Invalid voice/vocoder/audio nesting")
            stack.append((category, row))
        elif kind.endswith("_end") and kind.split("_")[0] in ("voice", "mbe", "audio"):
            category = kind.split("_")[0]
            require(stack and stack[-1][0] == category, "Unpaired voice/vocoder/audio event")
            _, start = stack.pop()
            require(start["frame"] == fid and start["value"] == row["value"], "Wrapper call identity changed")
            if category == "audio": validate_audio(row)
        elif kind == "frame_end":
            require(active is not None and fid == active["begin"]["frame"] and not stack and "end" not in active, "Unpaired frame end")
            active["end"] = row
            require(row["sps"] == 20 and row["rf_mod"] == 2, "In-frame fixed discriminator profile changed")
            active["classes"] = inspect_calls(active["begin"], row, trace, samples, enabled)
            classes.update(active["classes"])
            if enabled: validate_lich(active)
        elif kind == "dispatch_end":
            require(dispatch is not None and active is not None and "end" in active
                    and fid == active["begin"]["frame"], "Unpaired dispatch end")
            dispatch["end"] = row; active["dispatch"] = dispatch
            end = active["end"]
            integer(end["value"], 0, 2, "frame result")
            require(row["verdict"] == int(active["end"]["value"] == 0), "Result/verdict feedback differs")
            stamp = (row["profile_valid"], row["profile_idx"], row["profile_symbol"])
            expected_stamp = (1, end["hunt_idx"], end["symbolcnt"]) if end["value"] == 2 else (end["profile_valid"], end["profile_idx"], end["profile_symbol"])
            require(stamp == expected_stamp, "Profile proof stamp differs")
            active["source"] = source_identity(active, wave, origin)
            active["fully_sampled"] = active["end"]["body_count"] == 182 and all(c == "complete" for c in active["classes"])
            active["source_body_exact"] = (active["end"]["body"] == "".join(map(str, vectors[active["source"]["vector"]][10:10+active["end"]["body_count"]]))) if active["source"] else None
            frames.append(active); active = dispatch = None
    require(all(x is None for x in (search, reset, dispatch, active)) and not stack, "Unfinished event ownership")
    require(searches and resets, "Missing real engine search/reset")
    require(len(frames) == summary["frames"] == summary["dispatches"] and len(resets) == summary["resets"], "Boundary totals differ")
    require(counters["crc"] == summary["crcs"], "CRC event total differs")
    for kind, counter in COUNTERS.items():
        integer(summary[counter], 0, 100000, counter)
        if enabled: require(counters[kind] == summary[counter], "Detailed event count differs: " + counter)
    for kind, counter in (("backend_rate", "rate_calls"), ("backend_reacquire", "reacquire_calls")):
        require(sum(r["kind"] == kind for r in rows) == summary[counter], "Backend call total differs")
    return {"case": dict(case), "summary": summary, "configuration": rows[0], "frames": frames, "resets": resets,
            "searches": searches, "call_classes": dict(classes), "semantic": semantic(rows),
            "chunk_semantic": chunk_semantic(rows), "trace_sha256": hashlib.sha256(raw).hexdigest(),
            "scch_events": sum(len(f["scch"]) for f in frames), "measurement_pass": True}


def compare(pairs, manifest):
    issues = []; expected = {c["id"]: c for c in manifest["cases"]}; normalized = {}
    def fail(reason, **extra): issues.append({"reason": reason, **extra})
    if len(expected) != 18 or len(manifest["waveforms"]) != 9 or set(pairs) != set(expected): fail("incomplete_registered_grid")
    scenarios = {w["scenario"] for w in manifest["waveforms"].values()}
    if scenarios != {"warm_clean", "cold_sync_blank", "warm_drop20", "prefix_12360", "prefix_12361", "prefix_12380", "prefix_12521", "scch_valid", "scch_wrong"}: fail("registered_scenario_set_changed")
    for cid, case in expected.items():
        roles = pairs.get(cid, {})
        if len(roles) != 2 or {str(k) for k in roles} != {"0", "1"}:
            fail("missing_observer_pair", id=cid); continue
        audits = {int(k): v for k, v in roles.items()}; normalized[cid] = audits
        for enabled, audit in audits.items():
            if audit.get("case") != case or audit["summary"]["observed"] != enabled or not audit.get("measurement_pass"):
                fail("audit_identity_or_validity", id=cid, observed=enabled)
        if audits[0]["semantic"] != audits[1]["semantic"]: fail("observer_changed_common_outcomes", id=cid)
        wave = manifest["waveforms"][case["waveform"]]; scenario = wave["scenario"]; audit = audits[1]
        classes = audit["call_classes"]
        if scenario.startswith("prefix_"):
            cut = int(scenario.removeprefix("prefix_"))
            expected_class = "partial_eof" if cut in (12361, 12521) else "empty_first_eof"
            if classes.get(expected_class, 0) != 1 or not classes.get("empty_after_eof", 0): fail("missing_finite_cut_exposure", id=cid)
            target = [f for f in audit["frames"] if f["begin"]["eof"] == 0 and f["end"]["eof"] == 1]
            if len(target) != 1 or target[0]["source"] is not None: fail("truncation_attribution_or_exposure", id=cid)
            elif sum(c == "complete" for c in target[0]["classes"]) != {12360: 0, 12361: 0, 12380: 1, 12521: 8}.get(cut): fail("wrong_cut_call_boundary", id=cid)
        elif scenario == "cold_sync_blank":
            if not classes.get("empty_after_eof", 0): fail("legacy_eof_path_not_exposed", id=cid)
        elif scenario == "warm_clean":
            if not any(f["fully_sampled"] and f["source"] for f in audit["frames"]): fail("clean_source_unexposed", id=cid)
        elif scenario == "warm_drop20":
            matching = [f for f in audit["frames"] if any(e["result"] and e["lich"] == 0x77 and e["voice"] == 3 and e["scch"] for e in f["lich"])]
            if not any(f["scch"] and any(e["kind"] == "audio_end" for e in f["events"])
                       and f["begin"]["audio_indices"] != f["end"]["audio_indices"] for f in matching): fail("legacy_voice_staging_unexposed", id=cid)
        if "scch_expected" in wave:
            truth = wave["scch_expected"]
            registered = ("0" * 25, 17, 17 if scenario == "scch_valid" else 81, scenario == "scch_valid")
            if tuple(truth[k] for k in ("information_bits", "computed_crc", "transmitted_crc", "crc_expected_pass")) != registered: fail("registered_SCCH_oracle_changed", id=cid)
            source_frames = [f for f in audit["frames"] if f["source"] and f["source"]["kind"] == "V" and f["fully_sampled"]]
            if len(source_frames) != 2: fail("SCCH_control_sources_missing", id=cid)
            for frame in source_frames:
                if len(frame["scch"]) != 1: fail("SCCH_control_event_missing", id=cid); continue
                event = frame["scch"][0]
                if ((event["bits"], event["computed"], event["received"]) != (truth["information_bits"], truth["computed_crc"], truth["transmitted_crc"])
                    or (event["computed"] == event["received"]) != truth["crc_expected_pass"]): fail("SCCH_control_truth_disagreement", id=cid)
    for wave in manifest["waveforms"]:
        ids = {c["chunk"]: cid for cid, c in expected.items() if c["waveform"] == wave}
        if set(ids) != {37, 512} or any(cid not in normalized for cid in ids.values()): fail("missing_chunk_pair", waveform=wave); continue
        for enabled in (0, 1):
            a, b = [normalized[ids[c]][enabled] for c in (37, 512)]
            if a["chunk_semantic"] != b["chunk_semantic"] or a["trace_sha256"] != b["trace_sha256"]: fail("chunk_outcome_or_trace_difference", waveform=wave, observed=enabled)
    return {"measurement_pass": not issues, "issues": issues, "base_cases": len(normalized),
            "expected_invocations": 36, "scope": "finite recorder correctness and neutrality; no recovery or speech-success claim"}
