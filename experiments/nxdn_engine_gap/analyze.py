"""Audit finite engine traces; distinguish receiver behavior from recorder validity."""
import json
from pathlib import Path
import struct


def require(condition, message):
    if not condition:
        raise ValueError(message)


def crc(bits, width):
    # Independent bit recurrence: NXDN CRC6 x^6+x^5+x^2+x+1;
    # CRC12 x^12+x^11+x^3+x^2+x+1. Init all ones, no final xor.
    polynomial = {6: 0x27, 12: 0x80F}[width]
    register = (1 << width) - 1
    for bit in bits:
        feedback = (register >> (width - 1)) ^ int(bit)
        register = (register << 1) & ((1 << width) - 1)
        if feedback & 1:
            register ^= polynomial
    return register


def semantic(rows):
    ignored = {"seq", "frontier", "pops", "observed", "crcs", "skipped"}
    return [{k: v for k, v in row.items() if k not in ignored}
            for row in rows if row["kind"] != "crc"]


def source_identity(begin, end, waveform, vectors):
    if begin["eof"] or end["eof"] or begin["sync"] != 28:
        return None
    count = end["body_count"]
    if count not in (8, 182):
        return None
    if begin["frontier"] and not all(begin["frontier"] < p <= end["frontier"] for p in end["body_positions"]):
        return None
    matches = []
    for frame in waveform["frames"]:
        data = vectors[frame["vector"]]
        if end["body"] != "".join(map(str, data[10:10 + count])):
            continue
        deviations = [p - (frame["start"] + (11 + n) * 20) for n, p in enumerate(end["body_positions"])]
        # A declared one-symbol boundary interval, plus full returned body equality.
        # This locates a frame, not a claim of exact sample phase or RF latency.
        if all(-20 < d < 20 for d in deviations):
            matches.append({"ordinal": frame["ordinal"], "kind": frame["kind"], "vector": frame["vector"],
                            "boundary_deviation_min": min(deviations), "boundary_deviation_max": max(deviations)})
    require(len(matches) <= 1, "ambiguous complete source attribution")
    return matches[0] if matches else None


def inspect(rows, trace_path, case, manifest, inputs, enabled):
    require(len(rows) >= 3 and [r["kind"] for r in rows[:2]] == ["configuration", "initialized"]
            and rows[-1]["kind"] == "summary", "missing boundaries")
    configuration = {"audio_out": 0, "cosine_filter": 0, "scanner": 0, "trunk": 0, "trunk_scan": 0,
                     "voice_gate": 0, "visit_ms": 0, "msize": 1, "ssize": 128, "nxdn48": 1}
    require(all(rows[0][k] == v for k, v in configuration.items()), "configuration changed")
    require([r["seq"] for r in rows] == list(range(len(rows))), "event sequence omitted/duplicated")
    summary = rows[-1]
    waveform = manifest["waveforms"][case["waveform"]]
    require(summary["observed"] == enabled and summary["fast"] == case["fast"] and summary["chunk"] == case["chunk"], "case mismatch")
    require(summary["errors"] == summary["starts"] == summary["tunes"] == 0, "native recorder/backend error")
    require(summary["eof"] == 1 and summary["provided"] == summary["samples"] == waveform["samples"], "finite source not exhausted")
    raw = Path(trace_path).read_bytes()
    require(len(raw) % 4 == 0, "partial trace word")
    trace = list(struct.unpack("<" + "I" * (len(raw) // 4), raw))
    require(summary["pops"] == len(trace), "pop count mismatch")
    require(all(0 <= p < waveform["samples"] for p in trace), "sample outside source")
    require(all(a < b for a, b in zip(trace, trace[1:])), "duplicate or backwards source delivery")
    require(bool(trace) == bool(enabled), "observer trace enable mismatch")
    if trace:
        require(summary["frontier"] == trace[-1] + 1, "end frontier mismatch")
        require(summary["skipped"] == trace[-1] + 1 - len(trace), "gap accounting mismatch")
    vectors = {name: (inputs / "vectors" / name).read_bytes() for name in manifest["vectors"]["vectors"]}
    frames, active, dispatches, resets, searches = [], {}, {}, [], []
    reset_pending = search_pending = None
    dispatch_pending = frame_pending = last_search_result = None
    total_crc = 0
    allowed = {"configuration", "initialized", "completed", "summary", "search_begin", "search_end", "reset_begin",
               "reset_end", "dispatch_begin", "dispatch_end", "frame_begin", "frame_end", "crc", "backend_rate", "backend_reacquire"}
    require([r["kind"] for r in rows].count("completed") == 1 and rows[-2]["kind"] == "completed", "missing/misplaced completion")
    for key in ("provided", "pops", "frontier", "eof"):
        require(all(a[key] <= b[key] for a, b in zip(rows, rows[1:])), f"nonmonotone {key}")
    for row in rows:
        require(row["kind"] in allowed, "unknown event kind")
        require(0 <= row["provided"] <= waveform["samples"], "provider outside source")
        if enabled and row["pops"]:
            require(row["pops"] <= len(trace) and row["frontier"] == trace[row["pops"] - 1] + 1, "event trace frontier mismatch")
        if "audio_indices" in row:
            require(row["audio_indices"] == [0, 0, 0, 0], "unexpected audio-buffer side effect")
        kind, fid = row["kind"], row["frame"]
        if kind == "search_begin":
            require(search_pending is None and dispatch_pending is None, "nested search/dispatch")
            search_pending = row
        elif kind == "search_end":
            require(search_pending is not None, "unpaired search")
            searches.append({"begin": search_pending, "end": row}); search_pending = None
            last_search_result = row["value"]
        elif kind == "reset_begin":
            require(reset_pending is None and dispatch_pending is None, "nested reset/dispatch")
            reset_pending = row
        elif kind == "reset_end":
            require(reset_pending is not None, "unpaired reset")
            resets.append({"begin": reset_pending, "end": row}); reset_pending = None
        elif kind == "dispatch_begin":
            require(fid not in dispatches and dispatch_pending is None and search_pending is None
                    and reset_pending is None and row["sync"] == last_search_result and row["sync"] in (28, 29), "unowned/overlapping dispatch")
            dispatch_pending = fid; last_search_result = None
            dispatches[fid] = {"begin": row}
        elif kind == "frame_begin":
            require(fid == dispatch_pending and fid not in active and frame_pending is None, "unowned/repeated frame")
            frame_pending = fid
            active[fid] = {"begin": row, "crcs": []}
        elif kind == "crc":
            require(enabled and fid == frame_pending and fid in active and "end" not in active[fid], "CRC outside body")
            require(row["soft_pass"] in (0, 1) and row["fallback"] in (0, 1), "CRC flag outside boolean domain")
            require(row["fallback"] == 1 - row["soft_pass"], "fallback observation contradicts soft outcome")
            require(row["channel"] in (1, 2), "unexpected registered channel")
            width = 6 if row["channel"] == 1 else 12
            require(len(row["bits"]) == (26 if width == 6 else 80) and set(row["bits"]) <= {"0", "1"}, "malformed CRC info")
            require(crc(row["bits"], width) == row["computed"], "independent CRC mismatch")
            require(0 <= row["received"] < (1 << width), "received checkword out of range")
            active[fid]["crcs"].append(row); total_crc += 1
        elif kind == "frame_end":
            require(fid == frame_pending and fid in active and "end" not in active[fid], "unpaired frame")
            frame_pending = None
            require(len(row["body"]) == row["body_count"] == len(row["body_positions"]), "incomplete dibit trace")
            require(set(row["body"]) <= set("0123"), "invalid returned dibit")
            require(all(0 <= p <= waveform["samples"] for p in row["body_positions"]), "dibit frontier outside source")
            active[fid]["end"] = row
        elif kind == "dispatch_end":
            require(fid == dispatch_pending and frame_pending is None and fid in active and "end" in active[fid]
                    and "end" not in dispatches[fid], "unpaired dispatch")
            dispatch_pending = None
            dispatches[fid]["end"] = row
    require(reset_pending is None and search_pending is None and dispatch_pending is None and frame_pending is None, "unfinished control boundary")
    require(len(active) == len(dispatches) == summary["frames"] == summary["dispatches"], "missing frames")
    require(len(resets) == summary["resets"] and total_crc == summary["crcs"], "event totals mismatch")
    require(bool(searches) and bool(resets), "actual engine search/reset not observed")
    require(sum(r["kind"] == "backend_rate" for r in rows) == summary["rate_calls"]
            and sum(r["kind"] == "backend_reacquire" for r in rows) == summary["reacquire_calls"], "backend event totals mismatch")
    dispatch_deviations = []
    for fid, frame in active.items():
        require("end" in frame and "end" in dispatches[fid], "unfinished frame")
        frame["dispatch"] = dispatches[fid]
        begin, end = frame["begin"], frame["end"]
        dispatched = dispatches[fid]["end"]
        if dispatched["verdict"] != int(end["value"] == 0):
            dispatch_deviations.append(f"frame {fid}: result/verdict disagreement")
        stamp = (dispatched["profile_valid"], dispatched["profile_idx"], dispatched["profile_symbol"])
        expected_stamp = ((1, end["hunt_idx"], end["symbolcnt"]) if end["value"] == 2 else
                          (end["profile_valid"], end["profile_idx"], end["profile_symbol"]))
        if stamp != expected_stamp:
            dispatch_deviations.append(f"frame {fid}: profile proof stamp disagreement")
        if enabled and not end["eof"]:
            positions = end["body_positions"]
            require(all(a < b for a, b in zip(positions, positions[1:])), "non-progressing complete-body dibits")
            delivered = {p + 1 for p in trace[begin["pops"]:end["pops"]]}
            require(all(p in delivered for p in positions), "dibit position not backed by this body sample trace")
            if positions:
                require(positions[-1] == end["frontier"], "body last position differs from consumed frontier")
        frame["source"] = source_identity(frame["begin"], frame["end"], waveform, vectors)
        frame["channel_truth"] = None
        if frame["source"] and enabled:
            source = frame["source"]
            events = frame["crcs"]
            expected_count = 0 if source["kind"] == "P" else 3
            truth = manifest["vectors"]["vectors"][source["vector"]]
            good = len(events) == expected_count
            for event, ch, part, label in zip(events, (1, 2, 2), (0, 1, 2), ("sacch", "facch", "facch")):
                known = truth[label]
                good &= (event["channel"], event["part"], event["bits"], event["computed"], event["received"], bool(event["soft_pass"])) == (
                    ch, part, known["information_bits"], known["computed_crc"], known["transmitted_crc"], known["crc_expected_pass"])
            frame["channel_truth"] = bool(good)
        frames.append(frame)
    return {"summary": summary, "frames": frames, "resets": resets, "searches": searches,
            "dispatch_deviations": dispatch_deviations,
            "reset_completed": all(r["end"]["confirmed"] == r["end"]["streak"] == r["end"]["evidence"] == 0 for r in resets),
            "source_unattributed": sum(f["source"] is None for f in frames),
            "truncated_frames": sum(bool(f["end"]["eof"]) for f in frames)}


def quality(pair):
    """Use observed, independently attributed bodies, never nominal inputs alone."""
    bridges, corrected, issues, controls = [], [], [], []
    for cid, roles in pair.items():
        before, after = roles["baseline"], roles["candidate"]
        bf, af = before["frames"], after["frames"]
        for role, audit in roles.items():
            issues.extend(f"{cid}/{role}: {issue}" for issue in audit.get("dispatch_deviations", []))
        amap = {f["source"]["ordinal"]: f for f in af if f["source"]}
        for f in bf:
            if f["source"] and f["source"]["kind"] == "S" and f["channel_truth"] and f["end"]["value"] == 2:
                match = amap.get(f["source"]["ordinal"])
                if not match or not match["channel_truth"] or match["end"]["value"] != 2:
                    issues.append(f"{cid}: lost strong source {f['source']['ordinal']}")
        for f in af:
            if f["source"] and f["channel_truth"] is False:
                issues.append(f"{cid}: exact body channel truth changed")
            if ("-bad_crc-" in cid or "-zero-" in cid) and f["end"]["value"] == 2:
                issues.append(f"{cid}: current proof on negative input")
        for f in bf:
            if f["source"] and f["channel_truth"] is False:
                issues.append(f"{cid}: baseline exact body channel truth mismatch")
            if ("-bad_crc-" in cid or "-zero-" in cid) and f["end"]["value"] == 2:
                issues.append(f"{cid}: baseline current proof on negative input")
        for i in range(len(bf) - 2):
            triplet = bf[i:i + 3]
            if not all(f["source"] and f["channel_truth"] for f in triplet):
                continue
            w, p, w2 = triplet
            if [f["source"]["kind"] for f in triplet] != list("WPW") or w["begin"]["confirmed"] or w["begin"]["streak"]:
                continue
            if any(w["end"]["seq"] < r["begin"]["seq"] < w2["begin"]["seq"] for r in before["resets"]):
                continue
            if (w["end"]["value"], w["end"]["streak"], p["end"]["value"],
                w2["begin"]["confirmed"], w2["begin"]["streak"], w2["end"]["value"], w2["end"]["streak"]) != (0, 1, 0, 0, 1, 2, 2):
                continue
            bridge = {"id": cid, "ordinals": [f["source"]["ordinal"] for f in triplet]}
            bridges.append(bridge)
            target = [amap.get(n) for n in bridge["ordinals"]]
            next_weak = amap.get(bridge["ordinals"][-1] + 1)
            adjacent = (all(target) and any(af[j:j + 3] == target for j in range(len(af) - 2)))
            no_reset = (all(target) and next_weak and not any(target[0]["begin"]["seq"] < r["begin"]["seq"] < next_weak["end"]["seq"] for r in after["resets"]))
            fixed = (all(target) and all(f["channel_truth"] for f in target)
                     and target[0]["begin"]["confirmed"] == target[0]["begin"]["streak"] == 0
                     and [f["end"]["value"] for f in target] == [0, 0, 0]
                     and [f["end"]["streak"] for f in target] == [1, 0, 1]
                     and all(f["end"]["confirmed"] == 0 for f in target))
            subsequent = (next_weak and next_weak["source"]["kind"] == "W" and next_weak["channel_truth"]
                          and any(af[j:j + 4] == target + [next_weak] for j in range(len(af) - 3))
                          and next_weak["begin"]["confirmed"] == 0 and next_weak["begin"]["streak"] == 1
                          and next_weak["end"]["value"] == 2 and next_weak["end"]["confirmed"] == 1 and next_weak["end"]["streak"] == 2)
            if adjacent and no_reset and fixed and subsequent:
                corrected.append(bridge)
            else:
                issues.append(f"{cid}: baseline bridge not corrected on matching sources")
        # Retain entire common outcome for the registered consecutive-weak/sticky controls.
        if "-clean_weak-" in cid or "-strong_gap-" in cid:
            common = lambda fs: [(f["source"]["ordinal"], f["end"]["value"], f["end"]["confirmed"], f["dispatch"]["end"]["verdict"])
                                 for f in fs if f["source"]]
            retained = common(bf) == common(af)
            known = {f["source"]["ordinal"]: f for f in bf if f["source"] and f["channel_truth"]}
            if "-clean_weak-" in cid:
                exposed = all(n in known and known[n]["end"]["value"] == 2 for n in (4, 5))
            else:
                exposed = all(n in known and known[n]["end"]["value"] == result for n, result in ((2, 2), (3, 1), (4, 2)))
            controls.append({"id": cid, "retained": retained, "exposed": exposed, "sources": common(bf)})
            if not retained or not exposed:
                issues.append(f"{cid}: registered control outcomes changed")
        if not before["reset_completed"] or not after["reset_completed"]:
            issues.append(f"{cid}: reset completion did not clear confirmation")
    return {"baseline_bridges": bridges, "corrected_bridges": corrected, "issues": issues, "controls": controls,
            "progression_pass": bool(bridges) and bridges == corrected and not issues}


def chunk_signature(result):
    return {"frames": [(f["source"] and (f["source"]["ordinal"], f["source"]["kind"]), f["end"]["body"],
                         f["end"]["value"], f["end"]["confirmed"], f["end"]["streak"], f["dispatch"]["end"]["verdict"],
                         [(e["channel"], e["part"], e["bits"], e["computed"], e["received"]) for e in f["crcs"]])
                        for f in result["frames"]],
            "resets": [(r["begin"]["confirmed"], r["begin"]["streak"], r["end"]["confirmed"], r["end"]["streak"])
                       for r in result["resets"]]}
