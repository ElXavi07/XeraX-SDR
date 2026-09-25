"""Independent clear-route evidence checker; no encoder/decoder is imported.

Known bits, source ownership, real API calls and synthesis status are distinct.
Faithful receiver-quality failures remain valid measurements.
"""
import collections
import hashlib
import json
from pathlib import Path
import struct
import types

ROOT = Path(__file__).resolve().parents[2]
FINITE_PATH = ROOT / "experiments/nxdn_observation_v2/analyze.py"
FINITE_SHA = "bef0e7614fb39e9e0491ed422822710a780e245f6e70361bfeae73f2d3786198"
_finite_bytes = FINITE_PATH.read_bytes()
if hashlib.sha256(_finite_bytes).hexdigest() != FINITE_SHA:
    raise ValueError("Frozen finite/CRC primitives changed")
finite = types.ModuleType("frozen_finite_contract")
finite.__file__ = str(FINITE_PATH)
exec(compile(_finite_bytes, str(FINITE_PATH), "exec"), finite.__dict__)
require, integer, crc = finite.require, finite.integer, finite.crc
SCENARIOS = ("primed", "cold_default", "cold_fast", "single_weak", "bad_lich", "zero",
             "prefix_9999", "prefix_10000", "prefix_10001")
DETAIL = finite.OPTIONAL | {"fec_input"}
ROUTE = {"route_begin", "route_end", "fec", "synthesis"}
PROFILES = {0x41: (0, 0, 0, 0, 1, 3), 0x57: (3, 0, 0, 0, 1, 0),
            0x53: (2, 0, 0, 0, 1, 1), 0x55: (1, 0, 0, 0, 1, 2),
            0x77: (3, 1, 0, 1, 0, 0), 0x48: (0, 0, 3, 0, 0, 0)}
SLOTS = {0: (), 1: (0, 1), 2: (2, 3), 3: (0, 1, 2, 3)}
RESULT_FIELDS = {"c0_errors", "protected_errors", "c4_errors", "total_errors", "flags"}


def bits(value, count, label):
    require(isinstance(value, str) and len(value) == count and set(value) <= {"0", "1"}, label)
    return value


def semantic(rows):
    ignored = {"seq", "frontier", "pops", "observed", "crcs", "skipped"}
    return [{k: v for k, v in row.items() if k not in ignored} for row in rows if row["kind"] not in DETAIL]


def chunk_semantic(rows):
    # Optional PCM content is descriptive and is deliberately not compared.
    return [{k: v for k, v in row.items() if k not in finite.PROVIDER_FIELDS} for row in semantic(rows)]


def dewhiten(body, seed):
    seed = 228 if seed == 0 else min(seed, 511)
    out = []
    for char in body:
        out.append(int(char) ^ ((seed & 1) << 1))
        seed = (seed >> 1) | ((((seed >> 4) ^ seed) & 1) << 8)
    return "".join(map(str, out))


def matrix_for(channel, reliability=None):
    bits(channel, 72, "Invalid channel word")
    matrix = ["0"] * 96
    rel = [0] * 96
    if reliability is not None:
        require(len(reliability) == 36, "Wrong channel reliability length")
        for v in reliability: integer(v, 0, 255, "channel reliability")
    for position, value in enumerate(channel):
        k = 18 * (position % 4) + position // 4
        row, col = ((0, 23-k) if k < 24 else (1, 46-k) if k < 47 else
                    (2, 57-k) if k < 58 else (3, 71-k))
        matrix[24*row+col] = value
        if reliability is not None: rel[24*row+col] = reliability[position//2]
    return "".join(matrix), rel


def validate_result(value):
    require(isinstance(value, dict) and set(value) == RESULT_FIELDS, "Malformed named FEC result")
    for key, v in value.items(): integer(v, 0, 0xffffffff, key)


def validate_call(row):
    call = row.get("call")
    require("call" in row, "Missing call-state observation")
    if call is None: return
    fields = {"present", "epoch", "phase", "protocol", "kind", "source", "target", "policy_target",
              "crypto", "algid", "kid", "audio_permitted", "media_active", "end_reason"}
    require(isinstance(call, dict) and set(call) == fields and call["present"] == 1, "Malformed call snapshot")
    integer(call["epoch"], 1, (1 << 64)-1, "call epoch")
    for key in fields - {"present", "epoch", "protocol"}: integer(call[key], 0, (1 << 64)-1, "call " + key)
    integer(call["protocol"], -1, 1000, "call protocol")
    integer(call["phase"], 0, 2, "call phase")
    integer(call["audio_permitted"], 0, 1, "audio permission")
    integer(call["media_active"], 0, 1, "media flag")


def source_at(frame, wave, indices):
    """Coordinates alone first; never identify an occurrence from returned bits."""
    if frame["begin"]["sync"] != 28 or not indices: return None
    if any(i >= len(frame["classes"]) or frame["classes"][i] != "complete" for i in indices): return None
    candidates = []
    for source in wave["frames"]:
        deviations = [frame["end"]["body_positions"][i] - (source["start"] + (11+i)*20) for i in indices]
        if all(-20 < v < 20 for v in deviations): candidates.append(source)
    require(len(candidates) <= 1, "Ambiguous source ownership")
    return candidates[0] if candidates else None


def validate_lich(frame):
    require(len(frame["lich"]) == 1, "Missing unique LICH observation")
    row = frame["lich"][0]
    full = finite.lich_from_body(frame["end"]["body"], frame["begin"]["pn95"])
    value = full >> 1
    parity = sum((full >> i) & 1 for i in range(1 if value in (8, 0x4a, 0x48, 0x46) else 4, 8)) & 1
    require((row["full_lich"], row["lich"], row["parity_received"], row["parity_computed"])
            == (full, value, full & 1, parity), "LICH telemetry differs from actual body")
    integer(row["result"], 0, 1, "LICH decision")
    require(not row["result"] or parity == (full & 1), "Accepted LICH has inconsistent parity observation")
    if row["result"] and value in PROFILES:
        require(tuple(row[k] for k in ("voice", "scch", "pich_tch", "idas", "sacch", "facch")) == PROFILES[value],
                "Known LICH route telemetry contradicts profile")
    require(frame["end"]["body_count"] == (182 if row["result"] else 8), "LICH/body call count differs")
    require(row["symbolcnt"] == frame["end"]["body_calls"][7]["symbol_after"]
            and row["frontier"] == frame["end"]["body_calls"][7]["after"], "LICH decision not after eight real calls")
    expected_reason = "accepted" if row["result"] else "parity_reject" if (full & 1) != parity else "unsupported_profile"
    require(row["reason"] == expected_reason, "LICH reason differs from conventional decision")
    if not row["result"]: require(not frame["crcs"] and not frame["scch"], "Rejected LICH has channel callbacks")
    if row["result"] and value in (0x41, 0x57, 0x53, 0x55):
        expected = [(1, 0)] + ([(2, 1), (2, 2)] if value == 0x41 else [(2, 0)] if value in (0x53, 0x55) else [])
        require([(r["channel"], r["part"]) for r in frame["crcs"]] == expected, "Missing/extra final channel callbacks")
    require(len(frame["scch"]) == int(bool(row["result"] and row["scch"])), "Missing/extra SCCH callback")


def inspect_routes(frame, enabled):
    """Validate recorder identities, not receiver quality; real wrong outputs survive."""
    route = None
    routes, calls, inputs = [], {}, {}
    for row in frame["events"]:
        kind = row["kind"]
        if kind not in ROUTE | {"fec_input"}: continue
        rid = integer(row["route_id"], 0, 100000, "route identity")
        if kind == "route_begin":
            require(route is None, "Nested routed word")
            integer(row["slot"], 0, 3, "voice slot"); integer(row["voice"], 1, 3, "voice selector")
            route = {"begin": row, "fec": [], "synthesis": [], "inputs": []}
        else:
            require(route is not None and rid == route["begin"]["route_id"], "Unowned route event")
            if kind == "route_end":
                require((row["slot"], row["voice"]) == (route["begin"]["slot"], route["begin"]["voice"]), "Route changed slot")
                route["end"] = row; routes.append(route); route = None
                continue
            cid = integer(row["call_id"], 0, 100000, "decoder call identity")
            if kind in ("fec", "fec_input"):
                require(row["mode"] in ("hard", "soft"), "Unknown decoder mode")
                depth = integer(row["depth"], 1, 32, "decoder depth")
                parent = row["parent_call_id"]
                require((depth == 1) == (parent is None), "Invalid decoder nesting identity")
                if parent is not None: integer(parent, 0, cid-1, "parent decoder identity")
                if kind == "fec_input":
                    require(enabled and cid not in inputs, "Duplicate/unobserved FEC input")
                    inputs[cid] = row; route["inputs"].append(row)
                    bits(row["matrix96"], 96, "Malformed input matrix")
                    bits(row["channel72"], 72, "Malformed channel input")
                    matrix, rel = matrix_for(row["channel72"], row["channel_reliability"])
                    # Nested transforms may legitimately have another input: only
                    # outer routing promises the directly mapped matrix.
                    if row["reliability"] is not None:
                        require(len(row["reliability"]) == 96, "Wrong matrix reliability length")
                        for v in row["reliability"]: integer(v, 0, 255, "matrix reliability")
                    require(isinstance(row["channel_dibits"], str) and len(row["channel_dibits"]) == 36
                            and set(row["channel_dibits"]) <= set("0123"), "Malformed channel dibits")
                    require(row["channel72"] == "".join(format(int(v), "02b") for v in row["channel_dibits"]),
                            "Two encodings of the same observed channel disagree")
                else:
                    require(cid not in calls, "Repeated completed decoder call")
                    calls[cid] = row; route["fec"].append(row)
                    require(row["outer"] == int(depth == 1), "Outer decoder flag contradicts depth")
                    status = integer(row["status"], -(1 << 31), (1 << 31)-1, "decoder status")
                    if status < 0: require(row["bits49"] is None and row["result"] is None, "Undefined negative decoder output inspected")
                    else: bits(row["bits49"], 49, "Malformed decoded word"); validate_result(row["result"])
                    integer(row["input_unchanged"], 0, 1, "decoder mutation flag")
                    require(row["input_unchanged"] == 1, "Real decoder input mutation")
                    if enabled:
                        require(cid in inputs, "FEC completion missing input observation")
                        start = inputs[cid]
                        require(all(row[k] == start[k] for k in ("route_id", "parent_call_id", "depth", "mode")), "FEC call identity changed")
            else:
                bits(row["input49"], 49, "Malformed synthesis input")
                validate_result(row["result_before"])
                integer(row["status"], -(1 << 31), (1 << 31)-1, "synthesis status")
                if row["status"] < 0: require(row["result_after"] is None, "Undefined synthesis result inspected")
                else: validate_result(row["result_after"])
                require(row["input_unchanged"] == 1, "Real synthesis input mutation")
                route["synthesis"].append(row)
    require(route is None, "Unfinished routed word")
    for item in routes:
        own = {r["call_id"]: r for r in item["fec"]}
        for row in item["fec"]:
            if row["parent_call_id"] is not None:
                parent = own.get(row["parent_call_id"])
                require(parent is not None and row["depth"] == parent["depth"]+1 and row["seq"] < parent["seq"], "Invalid completed nested FEC ownership")
        if enabled: require({r["call_id"] for r in item["inputs"]} == set(own), "Incomplete FEC observations")
        if enabled:
            for row in item["fec"]:
                require(inputs[row["call_id"]]["seq"] < row["seq"], "FEC return precedes input")
                if row["parent_call_id"] is not None:
                    require(inputs[row["parent_call_id"]]["seq"] < inputs[row["call_id"]]["seq"], "Nested input precedes parent input")
        # These wrappers are synchronous: every synthesis observation must follow
        # a completed successful outer decode, not merely share its route number.
        for synth in item["synthesis"]:
            require(any(r["outer"] and r["status"] >= 0 and r["seq"] < synth["seq"] for r in item["fec"]),
                    "Synthesis lacks prior initialized successful decoder context")
    frame["routes"] = routes
    return routes


def inspect_evidence(rows, raw_trace, case, wave, oracle, enabled):
    require(len(rows) >= 4 and [r["kind"] for r in rows[:2]] == ["configuration", "initialized"]
            and [r["kind"] for r in rows[-2:]] == ["completed", "summary"], "Missing recorder boundaries")
    config = {**finite.CONFIG, "routing_schema": 1, "search_enabled": 0, "initial_manual_key": 0,
              "initial_forced_cipher": 0, "initial_cipher": 0, "initial_keyloader": 0, "initial_aes_key_loaded": 0}
    require(all(rows[0].get(k) == v for k, v in config.items()), "Fixed recorder configuration changed")
    require(len(rows) <= 4096 and [r["seq"] for r in rows] == list(range(len(rows))), "Event count/sequence changed")
    require(sum(r["kind"] == "completed" for r in rows) == 1, "Repeated completion")
    summary, samples = rows[-1], wave["samples"]
    require(summary["observed"] == enabled and summary["fast"] == case["fast"]
            and summary["chunk"] == case["chunk"] and case["chunk"] in (37, 512), "Invocation identity mismatch")
    require(summary["errors"] == summary["starts"] == summary["tunes"] == 0, "Recorder/backend error")
    require(summary["eof"] == 1 and summary["provided"] == summary["samples"] == samples, "Finite input not exhausted")
    require(len(raw_trace) % 4 == 0, "Partial pop trace word")
    trace = [v[0] for v in struct.iter_unpack("<I", raw_trace)]
    require(trace == (list(range(samples)) if enabled else []), "Delivered trace differs from exact finite source")
    require(summary["pops"] == len(trace) and summary["skipped"] == 0
            and summary["frontier"] == (samples if enabled else 0), "Incorrect trace summary")
    allowed = DETAIL | ROUTE | {"configuration", "initialized", "completed", "summary", "search_begin", "search_end",
        "reset_begin", "reset_end", "dispatch_begin", "dispatch_end", "frame_begin", "frame_end", "backend_rate", "backend_reacquire"}
    for key in ("provided", "frontier", "pops", "eof"):
        require(all(a[key] <= b[key] for a, b in zip(rows, rows[1:])), "Nonmonotone " + key)
    frames, searches, resets, stack = [], [], [], []
    search = reset = dispatch = active = last_sync = None
    counters, classes = collections.Counter(), collections.Counter()
    for row in rows:
        kind, fid = row["kind"], row["frame"]
        require(kind in allowed, "Unknown event kind")
        integer(row["eof"], 0, 1, "event EOF"); integer(row["provided"], 0, samples, "provider end")
        integer(row["pops"], 0, len(trace), "pop count")
        require(row["frontier"] == row["pops"], "Observed frontier differs from delivered trace")
        if "cache_pos" in row:
            finite.common_frontier(row, samples); validate_call(row)
            for key in ("manual_key", "forced_cipher", "keyloader"):
                require(row[key] == 0, "Forbidden key/cipher intervention")
        if kind in DETAIL | ROUTE:
            require(active is not None and "end" not in active and fid == active["begin"]["frame"], "Event outside active frame")
            if kind in DETAIL: require(enabled, "Detailed event emitted while disabled")
            counters[kind] += 1; active["events"].append(row)
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
            require(fid == len(frames), "Dispatch identity discontinuity")
            dispatch = {"begin": row}; last_sync = None
        elif kind == "frame_begin":
            require(dispatch is not None and fid == dispatch["begin"]["frame"] and active is None, "Unowned frame")
            active = {"begin": row, "crcs": [], "lich": [], "scch": [], "events": []}
            require(row["sps"] == 20 and row["rf_mod"] == 2, "Fixed discriminator profile changed")
        elif kind in ("crc", "scch"):
            if kind == "crc":
                require((row["channel"], row["part"]) in ((1, 0), (2, 0), (2, 1), (2, 2)), "Unexpected CRC channel")
                finite.validate_crc(row, 6 if row["channel"] == 1 else 12, 26 if row["channel"] == 1 else 80)
                active["crcs"].append(row)
            else: finite.validate_crc(row, 7, 25); active["scch"].append(row)
        elif kind == "lich": active["lich"].append(row)
        elif kind.endswith("_begin") and kind.split("_")[0] in ("voice", "mbe", "audio"):
            category = kind.split("_")[0]
            require((category == "voice" and not stack) or (category == "mbe" and stack and stack[-1][0] == "voice")
                    or (category == "audio" and stack and stack[-1][0] == "mbe"), "Invalid voice nesting")
            stack.append((category, row))
        elif kind.endswith("_end") and kind.split("_")[0] in ("voice", "mbe", "audio"):
            category = kind.split("_")[0]
            require(stack and stack[-1][0] == category, "Unpaired voice event")
            _, start = stack.pop()
            require(start["frame"] == fid and start["value"] == row["value"], "Voice wrapper identity changed")
            if category == "audio": finite.validate_audio(row)
        elif kind == "frame_end":
            require(active is not None and fid == active["begin"]["frame"] and not stack and "end" not in active, "Unpaired frame end")
            active["end"] = row
            require(row["sps"] == 20 and row["rf_mod"] == 2, "Fixed in-frame profile changed")
            active["classes"] = finite.inspect_calls(active["begin"], row, trace, samples, enabled)
            classes.update(active["classes"])
            if enabled: validate_lich(active)
            inspect_routes(active, enabled)
        elif kind == "dispatch_end":
            require(dispatch is not None and active is not None and "end" in active
                    and fid == active["begin"]["frame"], "Unpaired dispatch end")
            dispatch["end"] = row; active["dispatch"] = dispatch
            end = active["end"]; integer(end["value"], 0, 2, "frame result")
            require(row["verdict"] == int(end["value"] == 0), "Result/feedback mismatch")
            stamp = (row["profile_valid"], row["profile_idx"], row["profile_symbol"])
            expected = (1, end["hunt_idx"], end["symbolcnt"]) if end["value"] == 2 else (end["profile_valid"], end["profile_idx"], end["profile_symbol"])
            require(stamp == expected, "Actual profile stamp feedback mismatch")
            active["source"] = source_at(active, wave, list(range(len(active["classes"]))))
            active["lich_source"] = source_at(active, wave, list(range(8)))
            active["fully_sampled"] = len(active["classes"]) == 182 and all(c == "complete" for c in active["classes"])
            frames.append(active); active = dispatch = None
    require(all(v is None for v in (search, reset, dispatch, active)) and not stack, "Unfinished event ownership")
    require(searches and resets, "Missing live engine search/reset")
    require(len(frames) == summary["frames"] == summary["dispatches"] and len(resets) == summary["resets"], "Boundary totals differ")
    require(counters["crc"] == summary["crcs"], "CRC total differs")
    for kind, counter in finite.COUNTERS.items():
        integer(summary[counter], 0, 100000, counter)
        if enabled: require(counters[kind] == summary[counter], "Detail count differs: " + counter)
    for kind, counter in (("backend_rate", "rate_calls"), ("backend_reacquire", "reacquire_calls")):
        require(sum(r["kind"] == kind for r in rows) == summary[counter], "Backend call total differs")
    all_routes = [r for f in frames for r in f["routes"]]
    require([r["begin"]["route_id"] for r in all_routes] == list(range(summary["route_words"])), "Routed identity/count differs")
    require(summary["v2_mbe_calls"] == summary["route_words"], "Underlying MBE wrapper and routed-word counts differ")
    fecs = [r for f in frames for r in f["events"] if r["kind"] == "fec"]
    synths = [r for f in frames for r in f["events"] if r["kind"] == "synthesis"]
    require(sorted(r["call_id"] for r in fecs) == list(range(len(fecs))), "FEC serial identities differ")
    require([r["call_id"] for r in synths] == list(range(len(synths))), "Synthesis serial identities differ")
    for key, value in {"fec_hard_calls": sum(r["mode"] == "hard" for r in fecs),
                       "fec_soft_calls": sum(r["mode"] == "soft" for r in fecs),
                       "fec_outer_calls": sum(r["outer"] == 1 for r in fecs),
                       "fec_nested_calls": sum(r["outer"] == 0 for r in fecs), "synthesis_calls": len(synths)}.items():
        require(summary[key] == value, "Common call count differs: " + key)
    for route in all_routes:
        require(route["begin"]["fec_outer"] == route["begin"]["syntheses"] == 0, "Dirty route begin counters")
        require(route["end"]["fec_outer"] == sum(r["outer"] == 1 for r in route["fec"])
                and route["end"]["syntheses"] == len(route["synthesis"]), "Route end counters differ")
    for frame in frames:
        for event in frame["events"]:
            if event["kind"] in ROUTE | {"fec_input", "crc", "scch"}:
                require((finite.common_frontier(event, samples), event["symbolcnt"], event["eof"])
                        == (finite.common_frontier(frame["end"], samples), frame["end"]["symbolcnt"], frame["end"]["eof"]),
                        "Post-body observation moved before/after actual collection")
        if enabled:
            decision = frame["lich"][0]
            require(all(decision["seq"] < r["seq"] for r in frame["events"] if r["kind"] in ROUTE | {"crc", "scch"}),
                    "Control/voice observation precedes LICH decision")
            if decision["lich"] in (0x41, 0x57, 0x53, 0x55) and frame["routes"]:
                require(all(r["seq"] < frame["routes"][0]["begin"]["seq"] for r in frame["crcs"]),
                        "Known channel observation moved after voice processing")
    quality = assess_frames(frames, wave, oracle, enabled, case["configuration"])
    return {"case": dict(case), "summary": summary, "frames": frames, "resets": resets, "searches": searches,
            "call_classes": dict(classes), "semantic": semantic(rows), "chunk_semantic": chunk_semantic(rows),
            "trace_sha256": hashlib.sha256(raw_trace).hexdigest(), "measurement_pass": True, **quality}


def assess_frames(frames, wave, oracle, enabled, scenario):
    issues, occurrences, unsafe = [], [], []
    def issue(reason, **extra): issues.append({"reason": reason, **extra})
    for frame in frames:
        fid = frame["begin"]["frame"]
        source = frame["lich_source"]
        truth = oracle["vectors"][source["vector"]] if source else None
        if source:
            vector = oracle["dibits"][source["vector"]]
            completed = [i for i, c in enumerate(frame["classes"]) if c == "complete"]
            exact = all(int(frame["end"]["body"][i]) == vector[10+i] for i in completed)
            frame["source_body_exact"] = exact
            if not exact: issue("source_body_bits_differ", frame=fid)
        else: frame["source_body_exact"] = None
        if enabled and source:
            if frame["lich"][0]["full_lich"] != truth["full_lich"]: issue("source_lich_bits_differ", frame=fid)
            for event in frame["crcs"]:
                expected = truth["sacch" if event["channel"] == 1 else "facch"]
                if expected is None or (event["bits"], event["computed"], event["received"]) != (
                        expected["information_bits"], expected["computed_crc"], expected["transmitted_crc"]):
                    issue("source_control_truth_differs", frame=fid, channel=event["channel"], part=event["part"])
        if enabled and frame["end"]["value"] == 2:
            grounded_proof = False
            for event in frame["crcs"]:
                if event["channel"] == 1: indices = list(range(8, 38))
                else:
                    second = event["part"] == 2 or (event["part"] == 0 and truth and truth["lich"] == 0x55)
                    indices = list(range(110, 182)) if second else list(range(38, 110))
                identity = source_at(frame, wave, list(range(8)) + indices)
                if identity is None: continue
                expected = oracle["vectors"][identity["vector"]]["sacch" if event["channel"] == 1 else "facch"]
                if expected and (event["bits"], event["computed"], event["received"]) == (
                        expected["information_bits"], expected["computed_crc"], expected["transmitted_crc"]):
                    grounded_proof = True
            if not grounded_proof: issue("current_proof_without_complete_known_channel", frame=fid)
        for route in frame["routes"]:
            begin, slot = route["begin"], route["begin"]["slot"]
            indices = list(range(38+36*slot, 74+36*slot))
            owned = all(i < len(frame["classes"]) and frame["classes"][i] == "complete" for i in indices)
            position = source_at(frame, wave, list(range(8)) + indices)
            route["complete_source_interval"] = owned
            route["source"] = position
            if route["synthesis"] and not owned:
                unsafe.append({"frame": fid, "route_id": begin["route_id"], "slot": slot,
                               "synthesis_calls": len(route["synthesis"])})
            if begin["confirmed"] != 1: issue("unconfirmed_voice_route", frame=fid, slot=slot)
            if slot not in SLOTS[begin["voice"]]: issue("slot_outside_actual_voice_selector", frame=fid, slot=slot)
            outer = [r for r in route["fec"] if r["outer"]]
            if len(outer) != 1: issue("routed_word_outer_decode_count", frame=fid, slot=slot)
            for synth in route["synthesis"]:
                preceding = [r for r in outer if r["seq"] < synth["seq"] and r["status"] >= 0]
                if len(preceding) != 1 or preceding[0]["bits49"] != synth["input49"]:
                    issue("clear_synthesis_input_changed_or_without_decode", frame=fid, slot=slot)
            if position is None:
                if owned: issue("unmatched_complete_voice_route", frame=fid, slot=slot)
                continue
            vector_truth = oracle["vectors"][position["vector"]]
            matches = [v for v in vector_truth["transmitted_voice"] if v["slot"] == slot]
            if len(matches) != 1 or not vector_truth.get("parity_valid", True):
                issue("stolen_or_rejected_source_voice_route", frame=fid, slot=slot); continue
            sid = matches[0]["source_id"]
            expected_word, expected_channel = oracle["words"][sid], oracle["channels"][sid]
            raw = dewhiten(frame["end"]["body"], frame["begin"]["pn95"])
            channel = "".join(format(int(v), "02b") for v in raw[indices[0]:indices[-1]+1])
            exact = channel == expected_channel and len(outer) == 1 and outer[0]["status"] >= 0 and outer[0]["bits49"] == expected_word
            exact = exact and len(route["synthesis"]) == 1 and route["synthesis"][0]["input49"] == expected_word
            if enabled:
                detailed = [r for r in route["inputs"] if r["outer"]]
                if len(detailed) != 1: exact = False
                else:
                    row = detailed[0]; matrix, reliability = matrix_for(row["channel72"], row["channel_reliability"])
                    exact = exact and row["channel72"] == channel and row["matrix96"] == matrix
                    exact = exact and row["reliability"] == (reliability if row["mode"] == "soft" else None)
            if not exact: issue("source_word_route_not_exact", frame=fid, slot=slot, source_id=sid)
            occurrences.append({"ordinal": position["ordinal"], "source_frame": position["source_frame"],
                                "slot": slot, "source_id": sid, "scored": position["scored"], "exact": bool(exact),
                                "route_id": begin["route_id"]})
    identities = [(o["ordinal"], o["slot"]) for o in occurrences]
    if len(identities) != len(set(identities)): issue("duplicate_source_occurrence")
    routing_pass = not issues
    primed_issues = []
    if scenario == "primed":
        scored = [f for f in frames if f["source"] and f["source"]["scored"] and f["fully_sampled"]]
        if [f["source"]["source_frame"] for f in scored] != list(range(9)):
            primed_issues.append({"reason": "primed_complete_scored_frame_exposure"})
        expected = [(s["ordinal"], v["slot"], v["source_id"]) for s in wave["frames"] if s["scored"]
                    for v in oracle["vectors"][s["vector"]]["transmitted_voice"]]
        actual = [(o["ordinal"], o["slot"], o["source_id"]) for o in occurrences if o["scored"]]
        if actual != expected or len(actual) != 24:
            primed_issues.append({"reason": "primed_24_occurrence_retention"})
        header = next((f for f in scored if f["source"]["source_frame"] == 0), None)
        trailer = next((f for f in scored if f["source"]["source_frame"] == 8), None)
        first_voice = next((f for f in scored if f["source"]["source_frame"] == 1), None)
        def good_call(call):
            return call is not None and (call["phase"], call["kind"], call["source"], call["target"], call["crypto"],
                call["algid"], call["kid"], call["audio_permitted"]) == (1, 2, 901, 1201, 1, 0, 0, 1)
        if header is None or header["end"]["value"] != 2 or not good_call(header["end"].get("call")):
            primed_issues.append({"reason": "header_strong_clear_call_not_exposed"})
        if first_voice is None or first_voice["end"]["ran"] != 1:
            primed_issues.append({"reason": "eligible_confirmed_SACCH_RAN_not_one"})
        call = trailer["end"].get("call") if trailer else None
        prior = header["end"].get("call") if header else None
        if call is None or prior is None or (call["epoch"], call["phase"], call["end_reason"], call["media_active"], call["audio_permitted"]) != (prior["epoch"], 2, 3, 0, 0):
            primed_issues.append({"reason": "known_call_not_terminated_by_trailer"})
        for frame in scored:
            if frame["source"]["source_frame"] in range(1, 8):
                for route in frame["routes"]:
                    if not good_call(route["begin"].get("call")) or (prior and route["begin"]["call"]["epoch"] != prior["epoch"]):
                        primed_issues.append({"reason": "known_clear_call_changed_during_route", "frame": frame["begin"]["frame"]})
    negative = []
    if enabled and scenario == "single_weak":
        exposed = [f for f in frames if f["source"] and f["source"]["source_frame"] == 1 and f["fully_sampled"]]
        if len(exposed) != 1 or len(exposed[0]["crcs"]) != 1 or exposed[0]["lich"][0]["result"] != 1:
            negative.append({"reason": "single_weak_control_not_exposed"})
        elif exposed[0]["end"]["confirmed"] != 0 or exposed[0]["crcs"][0]["computed"] != exposed[0]["crcs"][0]["received"]:
            negative.append({"reason": "single_weak_confirmation_or_crc_failure"})
        if any(f["routes"] or any(r["kind"] in ("voice_begin", "mbe_begin") for r in f["events"]) for f in frames):
            negative.append({"reason": "unexpected_single_weak_voice_call"})
    if enabled and scenario == "bad_lich":
        exposed = [f for f in frames if f["lich_source"] and f["lich_source"]["vector"] == "r1_bad_lich.dibits"]
        if len(exposed) != 1 or exposed[0]["lich"][0]["reason"] != "parity_reject":
            negative.append({"reason": "bad_LICH_rejection_not_exposed"})
        if any(f["routes"] or any(r["kind"] in ("voice_begin", "mbe_begin") for r in f["events"]) for f in exposed):
            negative.append({"reason": "unexpected_parity_rejected_voice_call"})
    if scenario == "zero":
        if any(f["routes"] or f["end"]["value"] == 2 or f["end"]["confirmed"] for f in frames):
            negative.append({"reason": "unexpected_zero_input_voice_or_proof"})
        if any(f["end"].get("call") is not None and f["end"]["call"]["source"] == 901 for f in frames):
            negative.append({"reason": "zero_input_known_call"})
    return {"routing_pass": routing_pass and not primed_issues, "negative_pass": not negative,
            "finite_voice_safety_pass": not unsafe, "source_occurrences": occurrences,
            "unsafe_synthesis": unsafe, "routing_issues": issues + primed_issues, "negative_issues": negative,
            "scope": "known clear source-bit routing; synthesis status and internal PCM are not intelligible speech or playback"}


def _truth_module():
    path = Path(__file__).with_name("source_truth.py")
    module = types.ModuleType("clear_routing_source_truth"); module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


def validate_inputs(inputs):
    path = Path(inputs) / "manifest.json"
    raw = path.read_bytes(); manifest = json.loads(raw)
    require(hashlib.sha256((Path(__file__).with_name("prepare.py")).read_bytes()).hexdigest() == manifest["generator_sha256"], "Frozen generator changed")
    _truth_module().verify(inputs, manifest, crc)
    return manifest


def inspect(rows, trace_path, case, manifest, inputs, enabled):
    require(case in manifest["cases"], "Unregistered case")
    oracle = _truth_module().verify(inputs, manifest, crc)
    return inspect_evidence(rows, Path(trace_path).read_bytes(), case, manifest["waveforms"][case["waveform"]], oracle, enabled)


def compare(pairs, manifest):
    measurement, quality, normalized = [], [], {}
    expected = {c["id"]: c for c in manifest["cases"]}
    if len(expected) != 18 or set(pairs) != set(expected): measurement.append({"reason": "incomplete_registered_grid"})
    if {c["configuration"] for c in expected.values()} != set(SCENARIOS): measurement.append({"reason": "registered_configuration_set_changed"})
    routing = negative = safety = True
    for cid, case in expected.items():
        values = pairs.get(cid, {})
        if len(values) != 2 or {str(k) for k in values} != {"0", "1"}:
            measurement.append({"reason": "missing_detail_pair", "id": cid}); continue
        roles = {int(k): v for k, v in values.items()}; normalized[cid] = roles
        for enabled, audit in roles.items():
            if audit.get("case") != case or audit.get("summary", {}).get("observed") != enabled or not audit.get("measurement_pass"):
                measurement.append({"reason": "audit_identity_or_integrity", "id": cid})
        if roles[0]["semantic"] != roles[1]["semantic"]:
            measurement.append({"reason": "detail_changed_common_outcomes", "id": cid})
        for enabled, audit in roles.items():
            routing &= audit["routing_pass"]; negative &= audit["negative_pass"]; safety &= audit["finite_voice_safety_pass"]
            quality.extend({**e, "id": cid, "observed": enabled} for e in audit["routing_issues"] + audit["negative_issues"])
            quality.extend({"reason": "unavailable_voice_interval_synthesized", "id": cid, "observed": enabled, **e} for e in audit["unsafe_synthesis"])
    for scenario in SCENARIOS:
        by_chunk = {c["chunk"]: cid for cid, c in expected.items() if c["configuration"] == scenario}
        if set(by_chunk) != {37, 512} or any(cid not in normalized for cid in by_chunk.values()):
            measurement.append({"reason": "missing_chunk_pair", "configuration": scenario}); continue
        for enabled in (0, 1):
            a, b = [normalized[by_chunk[c]][enabled] for c in (37, 512)]
            if a["chunk_semantic"] != b["chunk_semantic"] or a["trace_sha256"] != b["trace_sha256"]:
                measurement.append({"reason": "chunk_outcomes_or_trace_changed", "configuration": scenario, "observed": enabled})
    measured = not measurement
    return {"measurement_pass": measured, "routing_pass": bool(routing), "negative_pass": bool(negative),
            "finite_voice_safety_pass": bool(safety), "progression_pass": bool(measured and routing and negative and safety),
            "product_promotion": False, "expected_invocations": 36, "audited_invocations": sum(map(len, normalized.values())),
            "issues": measurement + quality, "measurement_issues": measurement, "quality_issues": quality}
