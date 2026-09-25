"""Bounded boundary-policy adapter; frozen observation-v2 remains unchanged.

Input construction and policy arithmetic are independently checked here. Decoder
quality failures are returned as data, not converted into recorder exceptions.
"""
import collections
import copy
import hashlib
import json
import math
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT / "experiments/nxdn_observation_v2/analyze.py"
FROZEN_SHA = "bef0e7614fb39e9e0491ed422822710a780e245f6e70361bfeae73f2d3786198"
CANONICAL = {"3131331131", "1313113313"}
RELAXED = {"3331331131", "3131331111", "3331331111", "3131311131",
           "1113113313", "1313113333", "1113113333", "1313133313"}
IDENTITY = ("owner", "generation", "profile", "sps", "rf")
CONTEXT_FIELDS = set(IDENTITY) | {"symbols", "eligible", "confirmed"}
REGISTERED_WAVES = {f"h{p}-{s}" for p in (0, 1) for s in
                    ("warm_clean", "warm_sync_blank", "warm_sync_invert", "warm_repeat20", "bad_crc", "cold_clean")} | {
                        "h0-warm_drop20", "h0-zero", "scch_valid", "scch_wrong", "gap5_canonical", "gap5_relaxed"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, low, high, label):
    require(type(value) is int and low <= value <= high, "Invalid " + label)
    return value


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frozen_namespace():
    raw = FROZEN.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == FROZEN_SHA, "Frozen observation-v2 checker changed")
    namespace = {"__name__": "nxdn_boundary_frozen_observation", "__file__": str(FROZEN)}
    exec(compile(raw, str(FROZEN), "exec"), namespace)
    return namespace


def semantic(rows):
    return frozen_namespace()["semantic"](rows)


def validate_inputs(wave, manifest, inputs):
    """Validate actual transforms before removing the older transform metadata.

    The frozen checker still receives the original lineage, source vectors and
    frame truth. No source-attribution or recorder guard is replaced.
    """
    inputs = Path(inputs).resolve()

    def read(name, expected):
        path = (inputs / name).resolve()
        require(path.is_relative_to(inputs), "Input path escaped directory")
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == expected, "Input hash mismatch: " + name)
        return raw

    samples = integer(wave["samples"], 1, 100000, "sample count")
    raw = read(wave["file"], wave["sha256"])
    require(len(raw) == 4 * samples and all(math.isfinite(x[0]) for x in struct.iter_unpack("<f", raw)),
            "Malformed finite waveform")
    vectors = {}
    for name, meta in manifest["vectors"]["vectors"].items():
        vector = read("vectors/" + name, meta["sha256"])
        require(len(vector) == 192 and set(vector) <= {0, 1, 2, 3}, "Malformed numeric source vector")
        vectors[name] = vector
    frames = wave["frames"]
    require([f["ordinal"] for f in frames] == list(range(len(frames))), "Source ordinals differ")

    if "boundary_generation" in wave:
        label = wave["scenario"]
        require(label in ("gap5_canonical", "gap5_relaxed"), "Unregistered shaped-gap scenario")
        relaxed = label == "gap5_relaxed"
        require(wave["boundary_generation"] == {"gap_before_frame": 4, "zero_samples_before_shaping": 100,
                "relaxed_dibit": 1 if relaxed else None}, "Shaped-gap recipe changed")
        require(wave["edit"] == {"kind": "none", "source_start": 0, "count": 0}, "Gap has extra transform")
        require(len(frames) == 8 and wave["payload"] == 0, "Shaped-gap frame count/payload changed")
        altered = bytes([vectors["h0-S.dibits"][0], vectors["h0-S.dibits"][1] ^ 2]) + vectors["h0-S.dibits"][2:]
        require(vectors["h0-S-relaxed.dibits"] == altered, "Relaxed vector altered more than FSW dibit 1")
        metas = manifest["vectors"]["vectors"]
        require({k: v for k, v in metas["h0-S-relaxed.dibits"].items() if k not in ("sha256", "boundary_sync_edit")}
                == {k: v for k, v in metas["h0-S.dibits"].items() if k != "sha256"}, "Relaxed channel oracle changed")
        require(metas["h0-S-relaxed.dibits"]["boundary_sync_edit"] == {"dibit": 1, "xor": 2}, "Wrong FSW edit metadata")
        levels = (8000, 24000, -8000, -24000)
        unshaped = [levels[(i // 20) % 2 * 2 + 1] for i in range(640)]
        for ordinal, kind in enumerate("CCSSSSSS"):
            if ordinal == 4:
                unshaped += [0] * 100
            name = "h0-S-relaxed.dibits" if ordinal == 4 and relaxed else f"h0-{kind}.dibits"
            f = frames[ordinal]
            require((f["kind"], f["start"], f["end"], f["vector"]) ==
                    (kind, len(unshaped), len(unshaped) + 3840, name), "Shaped-gap frame layout changed")
            unshaped.extend(levels[d] for d in vectors[name] for _ in range(20))
        unshaped += [8000] * 1280
        # Sliding sum of an explicitly padded NRZ stream, independent of the
        # preparer's per-output clamped-index implementation.
        padded = [unshaped[0]] * 4 + unshaped + [unshaped[-1]] * 3
        total = sum(padded[:8]); shaped = []
        for i in range(len(unshaped)):
            shaped.append(total / 8)
            if i + 8 < len(padded):
                total += padded[i + 8] - padded[i]
        expected = struct.pack("<" + "f" * len(shaped), *shaped)
        origin = list(range(len(unshaped)))
        canonical_samples = len(unshaped)
    else:
        require("original_file" in wave, "Missing independently verifiable original waveform")
        original = read(wave["original_file"], wave["original_sha256"])
        canonical_samples = integer(wave["original_samples"], 1, 100000, "original length")
        require(len(original) == 4 * canonical_samples and
                all(math.isfinite(v[0]) for v in struct.iter_unpack("<f", original)), "Malformed original waveform")
        edit = wave["edit"]
        q = integer(edit["source_start"], 0, canonical_samples, "edit start")
        k = integer(edit["count"], 0, canonical_samples - q, "edit length")
        kind = edit["kind"]
        origin = list(range(canonical_samples)); expected = original
        if kind == "drop":
            require(k > 0, "Empty deletion")
            origin = origin[:q] + origin[q + k:]
            expected = original[:q * 4] + original[(q + k) * 4:]
        elif kind == "repeat":
            require(k > 0, "Empty repetition")
            origin = origin[:q] + origin[q:q + k] + origin[q:]
            expected = original[:q * 4] + original[q * 4:(q + k) * 4] + original[q * 4:]
        elif kind in ("invert", "blank"):
            require(k > 0, "Empty sync corruption")
            block = bytes(4 * k) if kind == "blank" else b"".join(struct.pack("<I", v[0] ^ 0x80000000)
                for v in struct.iter_unpack("<I", original[q * 4:(q + k) * 4]))
            expected = original[:q * 4] + block + original[(q + k) * 4:]
        elif kind == "zero":
            require(q == k == 0 and not frames, "Zero control carries an edit/source frame")
            expected = bytes(4 * canonical_samples)
        else:
            require(kind == "none" and q == k == 0, "Unregistered waveform transform")
    require(len(origin) == samples and expected == raw, "Declared construction differs from actual waveform")
    if "lineage_file" in wave:
        actual = read(wave["lineage_file"], wave["lineage_sha256"])
        require(actual == struct.pack("<" + "I" * samples, *origin), "Declared delivery lineage differs")
    else:
        require(origin == list(range(samples)), "Nonidentity transform lacks lineage")
    if "occurrence_file" in wave:
        counts = collections.Counter(); expected_occurrence = []
        for index in origin:
            expected_occurrence.append(counts[index]); counts[index] += 1
        actual = read(wave["occurrence_file"], wave["occurrence_sha256"])
        require(actual == struct.pack("<" + "I" * samples, *expected_occurrence), "Repeated origin occurrence differs")
    else:
        require(len(set(origin)) == len(origin), "Repeated delivery lacks occurrence identities")
    previous_end = 0
    for f in frames:
        require(previous_end <= f["start"] < f["end"] <= canonical_samples and f["end"] - f["start"] == 3840,
                "Invalid source frame coordinates")
        require(f["vector"] in vectors, "Missing source vector")
        if "sha256" in f:
            require(f["sha256"] == hashlib.sha256(vectors[f["vector"]]).hexdigest(), "Frame/vector hash differs")
        previous_end = f["end"]
    return {"validated": True, "edit": wave["edit"]["kind"], "gap_shaped": "boundary_generation" in wave,
            "samples": samples, "origin": origin}


def _frame_truth(frame, manifest, enabled, crc):
    source = frame["source"]
    meta = manifest["vectors"]["vectors"][source["vector"]] if source else {}
    results, issues = [], []
    for event in frame["crcs"] + frame["scch"]:
        scch = event["kind"] == "scch"
        channel, part = (7, 0) if scch else (event["channel"], event["part"])
        width = 7 if scch else 6 if channel == 1 else 12
        known = meta.get("scch") if scch else meta.get("sacch") if channel == 1 else meta.get(
            "facch_a" if part == 1 else "facch_b", meta.get("facch"))
        accepted = event["computed"] == event["received"]
        require(crc(event["bits"], width) == event["computed"], "Final CRC arithmetic differs")
        if known:
            require(crc(known["information_bits"], width) == known["computed_crc"], "Source CRC oracle arithmetic differs")
        exact = bool(known and (event["bits"], event["computed"], event["received"]) ==
                     (known["information_bits"], known["computed_crc"], known["transmitted_crc"]))
        results.append({"channel": channel, "part": part, "accepted": accepted,
                        "exact_source_content": exact, "correct": bool(exact and accepted),
                        "bits": event["bits"], "computed": event["computed"], "received": event["received"]})
        if accepted and not exact:
            issues.append("accepted_content_unattributed" if source is None else "incorrect_accepted_content")
    frame["channel_results"] = results
    correct = [c for c in results if c["correct"]]
    expected_channels = {(7, 0)} if "scch" in meta else {(1, 0), (2, 1), (2, 2)}
    frame["full_correct"] = bool(frame["fully_sampled"] and source and frame["source_body_exact"] and
        {(c["channel"], c["part"]) for c in correct} == expected_channels and len(results) == len(expected_channels))
    frame["supported_current_proof"] = bool(frame["end"]["value"] == 2 and frame["fully_sampled"] and source and correct)
    if enabled and frame["end"]["value"] == 2 and not frame["supported_current_proof"]:
        issues.append("unsupported_current_proof")
    if enabled:
        expected_evidence = 2 if any(c["accepted"] and c["channel"] == 2 for c in results) else int(any(c["accepted"] for c in results))
        # These are the complete observed short/strong-check paths. Other LICH
        # formats remain bounded by supported-current-proof, without pretending
        # uninstrumented checks did not occur.
        known_path = bool(frame["lich"] and (not frame["lich"][0]["result"] or frame["lich"][0]["lich"] in (0x41, 0x77)))
        if known_path:
            streak = 0 if expected_evidence in (0, 2) else min(255, frame["begin"]["streak"] + 1)
            confirmed = int(bool(frame["begin"]["confirmed"] or expected_evidence == 2 or
                                 (expected_evidence == 1 and streak >= 2)))
            proof = int(bool(confirmed and expected_evidence))
            expected = (confirmed, streak, expected_evidence, proof, 2 if proof else confirmed)
            actual = tuple(frame["end"][k] for k in ("confirmed", "streak", "evidence", "proved", "value"))
            if actual != expected:
                issues.append("confirmation_accounting_disagreement")
    frame["quality_issues"] = issues


def inspect(rows, trace_path, case, manifest, inputs, enabled):
    frozen = frozen_namespace()
    wave = manifest["waveforms"][case["waveform"]]
    validated = validate_inputs(wave, manifest, inputs)
    adapted = copy.deepcopy(manifest)
    # Only the transform branch is replaced by the preceding byte-exact check.
    # Original positions, occurrence identity, vectors and frame truth remain.
    adapted["waveforms"][case["waveform"]].pop("original_file", None)
    audit = frozen["inspect"](rows, trace_path, case, adapted, Path(inputs), enabled)
    audit["input_validation"] = {k: v for k, v in validated.items() if k != "origin"}
    audit["quality_issues"] = []
    for frame in audit["frames"]:
        _frame_truth(frame, manifest, enabled, frozen["crc"])
        audit["quality_issues"].extend({"frame": frame["end"]["frame"], "reason": x} for x in frame["quality_issues"])
    audit["attribution_limit"] = "Strict complete-body canonical attribution; unmatched accepted content is ungrounded, not proved false decoding."
    return audit


def _context(value):
    require(isinstance(value, dict) and set(value) == CONTEXT_FIELDS, "Policy context schema differs")
    for field in ("symbols", "generation"):
        integer(value[field], 0, 0xffffffff, "policy " + field)
    for field in ("eligible", "confirmed"):
        integer(value[field], 0, 1, "policy " + field)
    for field in ("profile", "sps", "rf"):
        integer(value[field], -1, 100000, "policy " + field)
    require(type(value["owner"]) is int and value["owner"] == 1, "Policy receiver identity differs")
    require(value["generation"] == 1 and value["eligible"] == 1, "Fixed stream generation/eligibility differs")
    return value


def _same(a, b):
    return all(a[k] == b[k] for k in IDENTITY)


def _lifetime(anchor, now):
    if anchor is None:
        return None, "unarmed"
    if not now["eligible"]:
        return None, "ineligible"
    if not now["confirmed"]:
        return None, "unconfirmed"
    if not _same(anchor, now):
        return None, "context_changed"
    if (now["symbols"] - anchor["symbols"]) % 2**32 > 395:
        return None, "expired"
    return anchor, None


def _decision(anchor, now, pattern, enabled):
    before = int(anchor is not None)
    age = (now["symbols"] - anchor["symbols"]) % 2**32 if before else 0
    anchor, reason = _lifetime(anchor, now)
    window = next((i for i, bounds in enumerate(((9, 11), (201, 203), (393, 395)), 1)
                   if bounds[0] <= age <= bounds[1]), 0) if anchor else 0
    canonical = int(pattern in CANONICAL)
    would = int(anchor is not None and pattern in RELAXED and not window)
    if anchor:
        reason = "canonical" if canonical else "unknown_pattern" if pattern not in RELAXED else "expected_window" if window else "off_phase"
    return anchor, {"allow": int(not (enabled and would)), "would_block": would, "canonical": canonical,
                    "window": window, "age": age, "reason": reason, "valid_before": before, "valid_after": int(anchor is not None)}


def inspect_policy(path, rows, enabled_policy):
    integer(enabled_policy, 0, 1, "enabled policy")
    records = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]
    require(len(records) >= 2 and records[0] == {"seq": 0, "kind": "configuration", "enabled": enabled_policy}, "Policy configuration differs")
    integer(records[0]["enabled"], 0, 1, "policy configuration enable")
    require([r["seq"] for r in records] == list(range(len(records))), "Policy sequence differs")
    require(all(type(r["seq"]) is int for r in records), "Policy sequence type differs")
    require(records[-1]["kind"] == "summary" and sum(r["kind"] == "summary" for r in records) == 1, "Missing/duplicate policy summary")
    starts = [r for r in rows if r["kind"] == "frame_begin"]
    ends = [r for r in rows if r["kind"] == "frame_end"]
    require(len(starts) == len(ends), "Policy source frame records unbalanced")
    # The sidecar has no global stdout sequence id. Bind each match to the
    # actual hunt interval between handlers, and bind carrier resets to the same
    # number of completed handlers. This checks chronology without pretending
    # the independent logs share a sequence counter.
    spans, carrier_stages = [], []
    seen = 0; search = None
    for row in rows:
        if row["kind"] == "frame_end": seen += 1
        if row["kind"] == "reset_begin": carrier_stages.append(seen)
        if row["kind"] == "search_begin": search = row
        if row["kind"] == "search_end":
            require(search is not None, "Unpaired real search for policy")
            spans.append((seen, search, row)); search = None
    anchor = None; counts = collections.Counter(); frame_records = []; matches = []; resets = []
    actual_carrier_stages = []; last_match_symbol = None
    for record in records[1:-1]:
        kind = record["kind"]
        if kind == "reset":
            require(record["reason"] in ("carrier", "acquisition", "profile"), "Unknown reset reason")
            for key in ("valid_before", "valid_after"): integer(record[key], 0, 1, "reset " + key)
            require(record["valid_before"] == int(anchor is not None) and record["valid_after"] == 0, "Policy reset validity differs")
            if record["reason"] == "carrier": actual_carrier_stages.append(counts["frames"])
            anchor = None; counts["resets"] += 1; resets.append(record)
        elif kind == "frame":
            fid = counts["frames"]
            require(record["frame"] == fid and fid < len(starts), "Policy frame chronology differs")
            begin, end = _context(record["begin"]), _context(record["end"])
            for key in ("armed", "valid_before", "valid_after"): integer(record[key], 0, 1, "frame " + key)
            opening = [m for m in matches if m["next_frame"] == fid and m["context"]["symbols"] == begin["symbols"]]
            require(len(opening) == 1 and opening[0]["decision"]["allow"] == 1
                    and opening[0]["pattern"] in CANONICAL | RELAXED
                    and starts[fid]["sync"] == (28 if opening[0]["pattern"][0] == "3" else 29),
                    "Real frame lacks its allowed policy opening match")
            for context, real in ((begin, starts[fid]), (end, ends[fid])):
                require(real["frame"] == fid and all(context[a] == real[b] for a, b in
                    (("symbols", "symbolcnt"), ("profile", "hunt_idx"), ("sps", "sps"), ("rf", "rf_mod"), ("confirmed", "confirmed"))),
                    "Policy frame context contradicts real receiver")
            require(record["result"] == ends[fid]["value"], "Policy frame result differs")
            require(record["valid_before"] == int(anchor is not None), "Policy pre-frame validity differs")
            anchor, _ = _lifetime(anchor, begin); anchor, _ = _lifetime(anchor, end)
            compatible = bool(begin["eligible"] and end["eligible"] and end["confirmed"] and _same(begin, end))
            if not compatible:
                anchor = None
            armed = int(compatible and record["result"] == 2 and (end["symbols"] - begin["symbols"]) % 2**32 == 182)
            if armed:
                anchor = dict(end)
            require(record["armed"] == armed and record["valid_after"] == int(anchor is not None) and record["anchor"] == anchor,
                    "Policy frame arming/anchor differs")
            counts["arms"] += armed; counts["frames"] += 1; frame_records.append(record)
        elif kind == "match":
            require(record["next_frame"] == counts["frames"], "Policy match frame chronology differs")
            now = _context(record["context"])
            require(last_match_symbol is None or now["symbols"] > last_match_symbol, "Policy match counters repeat/reverse")
            last_match_symbol = now["symbols"]
            intervals = [(a, b) for number, a, b in spans if number == counts["frames"]
                         and a["symbolcnt"] <= now["symbols"] <= b["symbolcnt"]]
            require(intervals and any(all(now[key] in (a[real], b[real]) for key, real in
                (("profile", "hunt_idx"), ("sps", "sps"), ("rf", "rf_mod"), ("confirmed", "confirmed")))
                for a, b in intervals), "Policy match is outside real receiver search/context")
            require(isinstance(record["pattern"], str) and len(record["pattern"]) == 10 and set(record["pattern"]) <= {"1", "3"},
                    "Invalid observed sign-match pattern")
            for key in ("allow", "would_block", "canonical", "valid_before", "valid_after"):
                integer(record["decision"][key], 0, 1, "decision " + key)
            integer(record["decision"]["age"], 0, 0xffffffff, "decision age")
            integer(record["decision"]["window"], 0, 3, "decision window")
            anchor, decision = _decision(anchor, now, record["pattern"], enabled_policy)
            require(record["decision"] == decision and record["anchor"] == anchor, "Policy match arithmetic/anchor differs")
            counts["matches"] += 1; counts["vetoes"] += int(not decision["allow"]); matches.append(record)
        else:
            raise ValueError("Unknown policy record kind")
    summary = records[-1]
    require(summary["enabled"] == enabled_policy and summary["errors"] == 0, "Policy summary errors/identity")
    require(counts["frames"] == len(starts), "Missing policy frame record")
    require(actual_carrier_stages == carrier_stages, "Policy carrier resets differ from real reset chronology")
    for key in ("frames", "matches", "resets", "arms", "vetoes"):
        require(type(summary[key]) is int and summary[key] == counts[key], "Policy total differs: " + key)
    return {"measurement_pass": True, "enabled": enabled_policy, "semantic": records, "summary": summary,
            "frames": frame_records, "matches": matches, "resets": resets, "arms": counts["arms"], "vetoes": counts["vetoes"],
            "limit": "Frame contexts and carrier resets are tied to stdout; fixed generation/owner and acquisition/profile reset provenance depend on bound runtime source."}


def _sets(audit):
    bodies, proofs, correct, channels = set(), set(), set(), set()
    for f in audit["frames"]:
        if not f["source"] or not f["fully_sampled"]:
            continue
        ordinal = f["source"]["ordinal"]
        if f["source_body_exact"]: bodies.add(ordinal)
        if f["supported_current_proof"]: proofs.add(ordinal)
        if f["full_correct"]: correct.add(ordinal)
        for c in f["channel_results"]:
            if c["correct"]: channels.add((ordinal, c["channel"], c["part"]))
    return {"bodies": bodies, "proofs": proofs, "correct": correct, "channels": channels}


def _plumbing(audit):
    return [{"ordinal": f["source"]["ordinal"], "body": f["end"]["body"],
             "channels": f["channel_results"],
             "events": [{k: v for k, v in e.items() if k not in {"seq", "frame", "provided", "frontier", "pops",
                         "cache_pos", "cache_len", "read_start", "chunk"}} for e in f["events"]
                        if e["kind"] in {"voice_begin", "voice_end", "mbe_begin", "mbe_end", "audio_begin", "audio_end"}]}
            for f in audit["frames"] if f["source"] and f["source"]["kind"] == "V" and f["fully_sampled"]]


def compare(pairs, manifest):
    measurement, quality, losses, gains = [], [], [], {}
    def fail(target, reason, **details): target.append({"reason": reason, **details})
    cases = manifest.get("cases", []); expected = {c["id"]: c for c in cases}; normalized = {}
    if (len(cases) != 36 or len(expected) != 36 or set(manifest.get("waveforms", {})) != REGISTERED_WAVES
            or set(pairs) != set(expected)):
        fail(measurement, "incomplete_registered_grid")
    for cid, case in expected.items():
        if case != {"id": f'{case["waveform"]}-c{case["chunk"]}', "waveform": case["waveform"], "chunk": case["chunk"], "fast": 0} or case["chunk"] not in (37, 512):
            fail(measurement, "case_identity_changed", id=cid)
        roles = pairs.get(cid, {})
        if set(roles) != {"baseline", "candidate"}:
            fail(measurement, "missing_role", id=cid); continue
        normalized[cid] = {}
        for role, mode in (("baseline", 0), ("candidate", 1)):
            observations = roles[role]
            if len(observations) != 2 or {str(k) for k in observations} != {"0", "1"}:
                fail(measurement, "missing_observer_pair", id=cid, role=role); continue
            audits = {int(k): v for k, v in observations.items()}; normalized[cid][role] = audits
            for observed, audit in audits.items():
                policy = audit.get("policy", {})
                if (audit.get("case") != case or not audit.get("measurement_pass") or audit.get("summary", {}).get("observed") != observed
                        or not audit.get("input_validation", {}).get("validated")
                        or not policy.get("measurement_pass") or policy.get("enabled") != mode):
                    fail(measurement, "audit_identity_or_validity", id=cid, role=role, observed=observed)
            if audits[0].get("semantic") != audits[1].get("semantic") or audits[0].get("policy", {}).get("semantic") != audits[1].get("policy", {}).get("semantic"):
                fail(measurement, "observer_changed_common_or_policy", id=cid, role=role)
            for issue in audits[1].get("quality_issues", []):
                fail(quality, "receiver_quality", id=cid, role=role, detail=issue)
        if set(normalized[cid]) != {"baseline", "candidate"}:
            continue
        baseline, candidate = [normalized[cid][r][1] for r in ("baseline", "candidate")]
        old, new = _sets(baseline), _sets(candidate)
        for category in old:
            missing = old[category] - new[category]
            if missing:
                loss = {"id": cid, "category": category, "missing": sorted(missing)}
                losses.append(loss); fail(quality, "baseline_source_loss", **loss)
        wave = manifest["waveforms"][case["waveform"]]
        if wave["scenario"] in ("warm_clean", "cold_clean"):
            for role, value in (("baseline", old), ("candidate", new)):
                if not value["correct"]: fail(quality, "clean_correct_source_unexposed", id=cid, role=role)
        if wave["scenario"] in ("bad_crc", "zero"):
            for role, audit in (("baseline", baseline), ("candidate", candidate)):
                if any(f["end"]["value"] == 2 for f in audit["frames"]):
                    fail(quality, "negative_control_current_proof", id=cid, role=role)
        if case["waveform"] in ("scch_valid", "scch_wrong"):
            truth = wave.get("scch_expected", {})
            expected_truth = ("0" * 25, 17, 17 if case["waveform"] == "scch_valid" else 81, case["waveform"] == "scch_valid")
            if tuple(truth.get(k) for k in ("information_bits", "computed_crc", "transmitted_crc", "crc_expected_pass")) != expected_truth:
                fail(quality, "registered_scch_oracle_changed", id=cid)
            a, b = _plumbing(baseline), _plumbing(candidate)
            if len(a) != 2 or len(b) != 2 or a != b or any(not x["events"] for x in a + b):
                fail(quality, "clean_scch_voice_plumbing_loss", id=cid)
            for role, audit in (("baseline", baseline), ("candidate", candidate)):
                for f in audit["frames"]:
                    if f["source"] and f["source"]["kind"] == "V" and f["fully_sampled"]:
                        expected_channel = [{"channel": 7, "part": 0, "accepted": expected_truth[3], "exact_source_content": True,
                                             "correct": expected_truth[3], "bits": expected_truth[0], "computed": 17, "received": expected_truth[2]}]
                        if f["channel_results"] != expected_channel:
                            fail(quality, "scch_control_content_loss", id=cid, role=role)
        if case["waveform"] in ("h0-warm_sync_invert", "h0-warm_repeat20"):
            warm = all(any(f["source"] and f["source"]["ordinal"] == 3 and f["supported_current_proof"]
                           and f["end"]["confirmed"] == 1 for f in a["frames"]) for a in (baseline, candidate))
            added = sorted(x for x in new["correct"] - old["correct"] if x >= 4)
            prefix_ends = {f["end"]["symbolcnt"] for f in candidate["frames"]
                           if f["source"] and f["source"]["ordinal"] == 3 and f["supported_current_proof"]}
            veto_exposure = any(m["decision"]["allow"] == 0 and m.get("anchor")
                                and m["anchor"]["symbols"] in prefix_ends for m in candidate.get("policy", {}).get("matches", []))
            gains[cid] = {"warm_exposure": warm, "veto_exposure": veto_exposure, "added_correct_source_frames": added}
    for wave in manifest.get("waveforms", {}):
        ids = {c["chunk"]: c["id"] for c in cases if c["waveform"] == wave}
        if set(ids) != {37, 512} or any(cid not in normalized for cid in ids.values()):
            fail(measurement, "missing_chunk_pair", waveform=wave); continue
        for role in ("baseline", "candidate"):
            for observed in (0, 1):
                a = normalized[ids[37]].get(role, {}).get(observed)
                b = normalized[ids[512]].get(role, {}).get(observed)
                if not a or not b:
                    fail(measurement, "missing_chunk_role", waveform=wave, role=role, observed=observed); continue
                if (a.get("chunk_semantic") != b.get("chunk_semantic") or a.get("trace_sha256") != b.get("trace_sha256")
                        or a.get("policy", {}).get("semantic") != b.get("policy", {}).get("semantic")):
                    fail(measurement, "chunk_outcome_trace_or_policy_difference", waveform=wave, role=role, observed=observed)
    improved = [wave for wave in ("h0-warm_sync_invert", "h0-warm_repeat20") if all(
        gains.get(f"{wave}-c{chunk}", {}).get("warm_exposure") and gains.get(f"{wave}-c{chunk}", {}).get("veto_exposure")
        and gains.get(f"{wave}-c{chunk}", {}).get("added_correct_source_frames")
        for chunk in (37, 512))]
    if not improved: fail(quality, "no_registered_warm_gain")
    return {"measurement_pass": not measurement, "progression_pass": not measurement and not quality,
            "issues": [{"gate": "measurement", **x} for x in measurement] + [{"gate": "quality", **x} for x in quality],
            "measurement_issues": measurement, "quality_issues": quality, "retention_losses": losses,
            "warm_gains": gains, "improved_scenarios": improved, "base_cases": len(expected), "expected_invocations": 144,
            "scope": "bounded discriminator recovery screen; archive equality and file/source preservation are runner gates"}
