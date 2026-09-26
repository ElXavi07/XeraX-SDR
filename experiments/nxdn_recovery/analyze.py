"""Registered recovery adapter: delivered lineage, final-channel truth and option comparison.

The frozen engine inspector remains the recorder-validity authority. Receiver
quality failures are returned as data, including ungrounded accepted content.
"""
import hashlib
import math
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT / "experiments/nxdn_engine_gap/analyze.py"
FROZEN_SHA = "76983513a67931f22347bc97b33e676a26f2350e6ab520c17f0ac5104136ee7b"
CHANNELS = ((1, 0), (2, 1), (2, 2))
GAIN_SAMPLES = 3360
MAX_DELAY = 20


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frozen_namespace():
    raw = FROZEN.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == FROZEN_SHA, "Frozen engine inspector changed")
    namespace = {"__name__": "nxdn_recovery_frozen_inspector", "__file__": str(FROZEN)}
    exec(compile(raw, str(FROZEN), "exec"), namespace)
    return namespace


def semantic(rows):
    return frozen_namespace()["semantic"](rows)


def crc(bits, width):
    """Polynomial long division, independent of the encoder's shift recurrence."""
    require(width in (6, 12) and set(bits) <= {"0", "1"}, "Invalid CRC input")
    polynomial = (1 << width) | {6: 0x27, 12: 0x80F}[width]
    value = ((1 << width) - 1) << len(bits)
    if bits:
        value ^= int(bits, 2) << width
    for shift in range(len(bits) - 1, -1, -1):
        if value & (1 << (width + shift)):
            value ^= polynomial << shift
    return value


def load_lineage(waveform, inputs):
    """Validate all edited floats and both coordinate/occurrence maps before attribution."""
    inputs = Path(inputs).resolve()

    def read(name, hash_name):
        path = (inputs / waveform[name]).resolve()
        require(path.is_relative_to(inputs), "Input path escapes the frozen input directory")
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == waveform[hash_name], "Input hash mismatch: " + name)
        return raw

    original = read("original_file", "original_sha256")
    delivered = read("file", "sha256")
    raw_origin = read("lineage_file", "lineage_sha256")
    raw_occurrence = read("occurrence_file", "occurrence_sha256")
    n, m = waveform["original_samples"], waveform["samples"]
    require(type(n) is int and type(m) is int and 0 < n <= 100000 and 0 < m <= 100000, "Invalid waveform size")
    require(len(original) == n * 4 and len(delivered) == m * 4, "Float waveform length mismatch")
    require(len(raw_origin) == len(raw_occurrence) == m * 4, "Lineage word count mismatch")
    for raw in (original, delivered):
        require(all(math.isfinite(v[0]) for v in struct.iter_unpack("<f", raw)), "Nonfinite input sample")
    origin = list(struct.unpack("<" + "I" * m, raw_origin))
    occurrence = list(struct.unpack("<" + "I" * m, raw_occurrence))
    edit = waveform["edit"]
    kind, q, k = edit["kind"], edit["source_start"], edit["count"]
    require(type(q) is int and type(k) is int and 0 <= q <= n and 0 <= k <= n - q, "Edit outside original waveform")
    expected_origin = list(range(n))
    expected = original
    if kind == "drop":
        require(k > 0, "Empty deletion")
        expected_origin = expected_origin[:q] + expected_origin[q + k:]
        expected = original[:4 * q] + original[4 * (q + k):]
    elif kind == "repeat":
        require(k > 0, "Empty repetition")
        expected_origin = expected_origin[:q] + expected_origin[q:q + k] + expected_origin[q:]
        expected = original[:4 * q] + original[4 * q:4 * (q + k)] + original[4 * q:]
    elif kind in ("blank", "invert"):
        require(k > 0, "Empty sync corruption")
        replacement = bytes(k * 4) if kind == "blank" else b"".join(
            struct.pack("<I", value[0] ^ 0x80000000)
            for value in struct.iter_unpack("<I", original[4 * q:4 * (q + k)]))
        expected = original[:4 * q] + replacement + original[4 * (q + k):]
    elif kind == "zero":
        expected = bytes(n * 4)
        require(not waveform["frames"], "Zero control must not carry source-frame truth")
    else:
        require(kind == "none" and k == 0, "Unknown or nonempty identity edit")
    require(origin == expected_origin, "Declared edit and origin map disagree")
    require(delivered == expected, "Declared edit and delivered waveform disagree")
    seen, expected_occurrence = {}, []
    for index in origin:
        expected_occurrence.append(seen.get(index, 0))
        seen[index] = seen.get(index, 0) + 1
    require(occurrence == expected_occurrence, "Repeated-sample occurrence labels disagree")
    ordinals = [f["ordinal"] for f in waveform["frames"]]
    require(len(ordinals) == len(set(ordinals)), "Repeated source ordinal")
    require(all(0 <= f["start"] < f["end"] <= n and f["end"] - f["start"] == 3840
                for f in waveform["frames"]), "Invalid canonical source-frame bounds")
    return origin


def source_identity(begin, end, waveform, origin):
    """Locate an ordinal by immutable positions, without requiring error-free slicing."""
    if begin["eof"] or end["eof"] or begin["sync"] != 28 or end["body_count"] not in (8, 182):
        return None
    positions = end["body_positions"]
    if not all(0 < p <= len(origin) for p in positions):
        return None
    if begin["frontier"] and not all(begin["frontier"] < p <= end["frontier"] for p in positions):
        return None
    mapped = [origin[p - 1] + 1 for p in positions]
    matches = []
    for frame in waveform["frames"]:
        deviations = [p - (frame["start"] + (11 + i) * 20) for i, p in enumerate(mapped)]
        if deviations and all(-20 < d < 20 for d in deviations):
            matches.append({"ordinal": frame["ordinal"], "kind": frame["kind"], "vector": frame["vector"],
                            "boundary_deviation_min": min(deviations), "boundary_deviation_max": max(deviations)})
    require(len(matches) <= 1, "Ambiguous canonical source attribution")
    return matches[0] if matches else None


def _expected_channel(truth, channel, part):
    if (channel, part) == (1, 0):
        return truth["sacch"]
    if channel == 2 and part in (1, 2):
        return truth.get("facch_a" if part == 1 else "facch_b", truth.get("facch"))
    return None


def _frame_truth(frame, manifest, observed):
    source, end, events = frame["source"], frame["end"], frame["crcs"]
    truth = manifest["vectors"]["vectors"][source["vector"]] if source else None
    issues, channels = [], []
    for event in events:
        width = 6 if event["channel"] == 1 else 12
        require(crc(event["bits"], width) == event["computed"], "Independent final CRC mismatch")
        accepted = event["computed"] == event["received"]
        known = _expected_channel(truth, event["channel"], event["part"]) if truth else None
        exact = bool(known and (event["bits"], event["computed"], event["received"]) ==
                     (known["information_bits"], known["computed_crc"], known["transmitted_crc"]))
        channels.append({"channel": event["channel"], "part": event["part"], "accepted": accepted,
                         "exact_source_content": exact, "correct": accepted and exact,
                         "soft_pass": event["soft_pass"], "fallback": event["fallback"]})
        if accepted and not exact:
            issues.append("accepted_content_unattributed" if source is None else "incorrect_accepted_content")
    frame["channel_results"] = channels
    frame["correct_channels"] = sum(c["correct"] for c in channels)
    frame["full_correct"] = bool(source and end["body_count"] == 182 and not end["eof"]
                                 and [(c["channel"], c["part"]) for c in channels] == list(CHANNELS)
                                 and all(c["correct"] for c in channels))
    frame["channel_truth"] = frame["full_correct"] if observed else None
    frame["supported_current_proof"] = bool(end["value"] == 2 and not end["eof"] and frame["correct_channels"])
    if observed and end["value"] == 2 and not frame["supported_current_proof"]:
        issues.append("unsupported_current_proof")
    frame["quality_issues"] = issues


def _accounting(frame):
    """Final evidence model only for the registered three-channel or rejected-LICH paths."""
    begin, end, events = frame["begin"], frame["end"], frame["crcs"]
    rejected = end["body_count"] == 8 and not events
    registered = (end["body_count"] == 182 and end["sacch_non_superframe"] == 1
                  and [(e["channel"], e["part"]) for e in events] == list(CHANNELS))
    if not (rejected or registered):
        frame["accounting_verified"] = False
        if end["value"] == 2:
            frame["quality_issues"].append("current_proof_on_unobserved_channel_path")
        return
    confirmed, streak, evidence = begin["confirmed"], begin["streak"], 0
    for event in events:
        if (event["confirmed"], event["streak"], event["evidence"]) != (confirmed, streak, evidence):
            frame["quality_issues"].append("pre_crc_accounting_disagreement")
        if event["computed"] != event["received"]:
            continue
        if event["channel"] == 2:
            confirmed, streak, evidence = 1, 0, 2
        elif evidence == 0:
            evidence = 1
            streak = min(streak + 1, 255)
            confirmed = int(bool(confirmed or streak >= 2))
    if evidence == 0:
        streak = 0
    proved = int(bool(confirmed and evidence))
    result = 2 if proved else confirmed
    frame["accounting_verified"] = True
    frame["expected_accounting"] = {"confirmed": confirmed, "streak": streak, "evidence": evidence,
                                    "proved": proved, "value": result}
    if any(end[key] != value for key, value in frame["expected_accounting"].items()):
        frame["quality_issues"].append("final_confirmation_or_return_disagreement")


def inspect(rows, trace_path, case, manifest, inputs, enabled):
    namespace = frozen_namespace()
    waveform = manifest["waveforms"][case["waveform"]]
    origin = None
    if not waveform.get("legacy", False):
        origin = load_lineage(waveform, inputs)
        namespace["source_identity"] = lambda begin, end, wave, vectors: source_identity(begin, end, wave, origin)
    audit = namespace["inspect"](rows, trace_path, case, manifest, Path(inputs), enabled)
    audit["case"] = dict(case)
    audit["trace_sha256"] = digest(trace_path)
    audit["legacy"] = bool(waveform.get("legacy", False))
    audit["quality_issues"] = list(audit["dispatch_deviations"])
    if not audit["reset_completed"]:
        audit["quality_issues"].append("reset_did_not_clear_confirmation")
    previous = rows[1]
    transitions = sorted([(f["begin"]["seq"], "frame", f) for f in audit["frames"]]
                         + [(r["begin"]["seq"], "reset", r) for r in audit["resets"]])
    for _, kind, item in transitions:
        begin, end = item["begin"], item["end"]
        if (begin["confirmed"], begin["streak"]) != (previous["confirmed"], previous["streak"]):
            audit["quality_issues"].append("unexplained_confirmation_transition")
        if kind == "frame":
            _frame_truth(item, manifest, enabled)
            if origin:
                item["canonical_body_positions"] = [origin[p - 1] + 1 for p in end["body_positions"] if p > 0]
            if enabled:
                _accounting(item)
            audit["quality_issues"].extend({"frame": end["frame"], "reason": issue} for issue in item["quality_issues"])
        previous = end
    audit["full_correct_frames"] = sum(f["full_correct"] for f in audit["frames"])
    audit["supported_current_proofs"] = sum(f["supported_current_proof"] for f in audit["frames"])
    audit["partial_supported_proofs"] = sum(f["supported_current_proof"] and not f["full_correct"] for f in audit["frames"])
    audit["attribution_limit"] = "Strict canonical boundary interval (-20,20); unmatched FEC content is ungrounded, not established false decoding."
    return audit


def _full_frames(audit):
    result, duplicates = {}, []
    for frame in audit["frames"]:
        if not frame["full_correct"] or not frame["source"]:
            continue
        ordinal = frame["source"]["ordinal"]
        if ordinal in result:
            duplicates.append(ordinal)
        else:
            result[ordinal] = frame
    return result, duplicates


def _warm_exposure(audit, fault_start):
    prefixes = [f for f in audit["frames"] if f["source"] and f["source"]["ordinal"] == 3
                and f["supported_current_proof"] and f["end"]["confirmed"] == 1
                and f["end"]["frontier"] <= fault_start]
    if len(prefixes) != 1:
        return False
    prefix = prefixes[0]
    return not any(r["begin"]["seq"] > prefix["end"]["seq"] and r["begin"]["frontier"] <= fault_start
                   for r in audit["resets"])


def _endpoint(frames, minimum_ordinal, fault_end):
    choices = [f for ordinal, f in frames.items() if ordinal >= minimum_ordinal and f["end"]["frontier"] > fault_end]
    if not choices:
        return None
    frame = min(choices, key=lambda f: f["end"]["frontier"])
    return {"ordinal": frame["source"]["ordinal"], "delivered_frontier": frame["end"]["frontier"],
            "canonical_frontier": frame.get("canonical_body_positions", [frame["end"]["frontier"]])[-1]}


def compare(pairs, manifest):
    """pairs[base_case_id][0 or 1] contains the corresponding observed inspect result."""
    issues, cases, normalized = [], [], {}
    expected = {c["id"]: c for c in manifest["cases"]}
    if set(pairs) != set(expected):
        issues.append({"reason": "incomplete_case_grid", "missing": sorted(set(expected) - set(pairs)),
                       "extra": sorted(set(pairs) - set(expected))})
    for cid, case in expected.items():
        roles = pairs.get(cid, {})
        if len(roles) != 2 or {str(k) for k in roles} != {"0", "1"}:
            issues.append({"id": cid, "reason": "incomplete_option_pair"})
            continue
        audits = {int(k): v for k, v in roles.items()}
        normalized[cid] = audits
        wave = manifest["waveforms"][case["waveform"]]
        for fast, audit in audits.items():
            if any(audit["case"].get(key) != value for key, value in {**case, "fast": fast}.items()):
                issues.append({"id": cid, "fast": fast, "reason": "audit_case_identity_disagreement"})
            if audit["summary"]["observed"] != 1:
                issues.append({"id": cid, "fast": fast, "reason": "comparison_requires_observed_audit"})
            issues.extend({"id": cid, "fast": fast, "detail": issue} for issue in audit["quality_issues"])
        if wave.get("legacy", False):
            continue
        source_maps = {fast: _full_frames(audit) for fast, audit in audits.items()}
        for fast, (_, duplicates) in source_maps.items():
            if duplicates:
                issues.append({"id": cid, "fast": fast, "reason": "duplicate_full_source_decodes", "ordinals": duplicates})
        before, after = source_maps[0][0], source_maps[1][0]
        losses = []
        for ordinal, frame in before.items():
            old_end = frame["end"]["frontier"]
            new_end = after.get(ordinal, {}).get("end", {}).get("frontier")
            if new_end is None or new_end > old_end + MAX_DELAY:
                losses.append({"ordinal": ordinal, "off_end": old_end, "on_end": new_end})
        if losses:
            issues.append({"id": cid, "reason": "lost_or_delayed_source_frames", "frames": losses})
        scenario, edit = wave["scenario"], wave["edit"]
        warm = scenario.startswith("warm_")
        target_ordinal = 4 if warm else 0
        target = next((f for f in wave["frames"] if f["ordinal"] == target_ordinal), None)
        fault_start = edit["source_start"] if edit["kind"] != "none" else (target["start"] if target else 0)
        fault_end = fault_start + (0 if edit["kind"] == "drop" else edit["count"])
        exposed = {fast: _warm_exposure(audit, fault_start) for fast, audit in audits.items()} if warm else {}
        endpoints = {fast: _endpoint(source_maps[fast][0], target_ordinal, fault_end) for fast in (0, 1)}
        gain = (endpoints[0]["delivered_frontier"] - endpoints[1]["delivered_frontier"]
                if all(endpoints.values()) else None)
        resets = {fast: [{"begin_frontier": r["begin"]["frontier"], "end_frontier": r["end"]["frontier"],
                          "before_confirmed": r["begin"]["confirmed"], "after_confirmed": r["end"]["confirmed"]}
                         for r in audit["resets"] if fault_start <= r["begin"]["frontier"]]
                  for fast, audit in audits.items()}
        if scenario in ("bad_crc", "zero") and any(f["end"]["value"] != 0 or any(c["accepted"] for c in f["channel_results"])
                                                   for a in audits.values() for f in a["frames"]):
            issues.append({"id": cid, "reason": "negative_control_acceptance"})
        if scenario.endswith("_clean") and not all(source_maps[fast][0] for fast in (0, 1)):
            issues.append({"id": cid, "reason": "unexposed_clean_control"})
        if warm and not all(exposed.values()):
            issues.append({"id": cid, "reason": "incomplete_warm_exposure"})
        cases.append({"id": cid, "waveform": case["waveform"], "scenario": scenario, "payload": wave["payload"],
                      "chunk": case["chunk"], "warm_exposure": exposed, "endpoints": endpoints,
                      "gain_samples": gain, "gain_ms": gain / 48 if gain is not None else None,
                      "resets_after_fault": resets, "source_frame_losses": losses,
                      "full_source_ordinals": {fast: sorted(source_maps[fast][0]) for fast in (0, 1)},
                      "frame_counts": {fast: len(audits[fast]["frames"]) for fast in (0, 1)}})
    # Cache/provider positions vary with chunking; consumed traces and receiver outcomes must not.
    frozen = frozen_namespace()
    for cid, case in expected.items():
        if case["chunk"] != 37 or cid not in normalized:
            continue
        other = next((c["id"] for c in expected.values() if c["waveform"] == case["waveform"] and c["chunk"] == 512), None)
        if other not in normalized:
            issues.append({"id": cid, "reason": "missing_chunk_pair"})
            continue
        for fast in (0, 1):
            a, b = normalized[cid][fast], normalized[other][fast]
            if a["trace_sha256"] != b["trace_sha256"] or frozen["chunk_signature"](a) != frozen["chunk_signature"](b):
                issues.append({"id": cid, "other": other, "fast": fast, "reason": "chunk_outcome_or_trace_difference"})
    by_key = {(c["scenario"], c["payload"], c["chunk"]): c for c in cases}
    for case in cases:
        prefix = "warm" if case["scenario"].startswith("warm_") else "cold"
        clean = by_key.get((prefix + "_clean", case["payload"], case["chunk"]))
        case["recovery_delay_vs_clean"] = {
            fast: (case["endpoints"][fast]["delivered_frontier"] - clean["endpoints"][fast]["delivered_frontier"]
                   if clean and case["endpoints"][fast] and clean["endpoints"][fast] else None)
            for fast in (0, 1)}
        # Delivered counts include the edit's inserted/deleted samples. Keep the
        # immutable-source counterpart so those counts are not called decoding cost.
        case["recovery_delay_vs_clean_canonical"] = {
            fast: (case["endpoints"][fast]["canonical_frontier"] - clean["endpoints"][fast]["canonical_frontier"]
                   if clean and case["endpoints"][fast] and clean["endpoints"][fast] else None)
            for fast in (0, 1)}
        case["recovery_delay_units"] = "samples; delivered and mapped immutable-source frontiers"
    qualifying = {"cold": [], "warm": []}
    for scenario in sorted({c["scenario"] for c in cases}):
        group = [c for c in cases if c["scenario"] == scenario]
        prefix = scenario.split("_")[0]
        if prefix not in qualifying or scenario.endswith("_clean"):
            continue
        if (len(group) == 4 and len({(c["payload"], c["chunk"]) for c in group}) == 4
                and all(c["gain_samples"] is not None and c["gain_samples"] >= GAIN_SAMPLES
                        and (prefix != "warm" or all(c["warm_exposure"].values())) for c in group)):
            qualifying[prefix].append(scenario)
    return {"quality_pass": not issues, "issues": issues, "cases": cases,
            "qualifying_cold_scenarios": qualifying["cold"], "qualifying_warm_scenarios": qualifying["warm"],
            "cold_improvement_pass": not issues and bool(qualifying["cold"]),
            "warm_improvement_pass": not issues and bool(qualifying["warm"]),
            "progression_pass": not issues and bool(qualifying["warm"])}
