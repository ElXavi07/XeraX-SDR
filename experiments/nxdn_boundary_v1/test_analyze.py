"""Counterexamples for the boundary adapter; no native executable is invoked."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest import mock

import analyze


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def v2_fixture(directory):
    # Reuse only the archived synthetic fixture builder, with its imports bound
    # to the frozen checker. Counterexample mutations below are new and local.
    path = analyze.ROOT / "experiments/nxdn_observation_v2/test_analyze.py"
    analyze.require(sha(path.read_bytes()) == "4307f133b4a8c5cbdac219742869996cb106ca4a69a1d3a3dbf0ad99b4344a02", "Frozen test fixture changed")
    spec = importlib.util.spec_from_file_location("boundary_v2_test_fixture", path)
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(sys.modules, {"analyze": types.SimpleNamespace(**analyze.frozen_namespace())}):
        spec.loader.exec_module(module)
    return module.fixture(directory)


def transformed(directory, kind):
    directory = Path(directory); (directory / "vectors").mkdir()
    original = struct.pack("<6f", 1, -2, 3, -4, 5, -6)
    q, count = (2, 2) if kind not in ("none", "zero") else (0, 0)
    raw = original; origin = list(range(6))
    if kind == "invert":
        raw = struct.pack("<6f", 1, -2, -3, 4, 5, -6)
    elif kind == "repeat":
        raw = struct.pack("<8f", 1, -2, 3, -4, 3, -4, 5, -6); origin = [0, 1, 2, 3, 2, 3, 4, 5]
    elif kind == "drop":
        raw = struct.pack("<4f", 1, -2, 5, -6); origin = [0, 1, 4, 5]
    elif kind == "blank":
        raw = struct.pack("<6f", 1, -2, 0, 0, 5, -6)
    elif kind == "zero":
        raw = bytes(24)
    occur = [origin[:i].count(n) for i, n in enumerate(origin)]
    for name, value in (("original", original), ("wave", raw), ("origin", struct.pack("<" + "I" * len(origin), *origin)),
                        ("occur", struct.pack("<" + "I" * len(occur), *occur))):
        (directory / name).write_bytes(value)
    wave = {"scenario": kind, "frames": [], "samples": len(origin), "file": "wave", "sha256": sha(raw),
            "original_file": "original", "original_sha256": sha(original), "original_samples": 6,
            "lineage_file": "origin", "lineage_sha256": sha((directory / "origin").read_bytes()),
            "occurrence_file": "occur", "occurrence_sha256": sha((directory / "occur").read_bytes()),
            "edit": {"kind": kind, "source_start": q, "count": count}}
    return wave, {"vectors": {"vectors": {}}}


def gap_fixture(directory, relaxed=False):
    directory = Path(directory); (directory / "vectors").mkdir()
    vectors = {"h0-C.dibits": bytes([3, 0, 3, 1, 3, 3, 1, 1, 2, 1] + [0, 1, 2, 3] * 45 + [1, 0]),
               "h0-S.dibits": bytes([3, 0, 3, 1, 3, 3, 1, 1, 2, 1] + [3, 1] * 91)}
    altered = bytearray(vectors["h0-S.dibits"]); altered[1] ^= 2
    vectors["h0-S-relaxed.dibits"] = bytes(altered)
    metas = {}
    for name, raw in vectors.items():
        (directory / "vectors" / name).write_bytes(raw); metas[name] = {"sha256": sha(raw)}
    metas["h0-S-relaxed.dibits"]["boundary_sync_edit"] = {"dibit": 1, "xor": 2}
    level = {0: 8000, 1: 24000, 2: -8000, 3: -24000}
    raw_levels = [level[d] for d in (1, 3) * 16 for _ in range(20)]; frames = []
    for i, kind in enumerate("CCSSSSSS"):
        if i == 4: raw_levels.extend([0] * 100)
        name = "h0-S-relaxed.dibits" if relaxed and i == 4 else f"h0-{kind}.dibits"
        frames.append({"ordinal": i, "kind": kind, "vector": name, "start": len(raw_levels), "end": len(raw_levels) + 3840})
        raw_levels.extend(level[d] for d in vectors[name] for _ in range(20))
    raw_levels.extend([8000] * 1280)
    shape = [sum(raw_levels[max(0, min(len(raw_levels)-1, j))] for j in range(i-4, i+4)) / 8 for i in range(len(raw_levels))]
    raw = struct.pack("<" + "f" * len(shape), *shape); (directory / "wave").write_bytes(raw)
    wave = {"scenario": "gap5_relaxed" if relaxed else "gap5_canonical", "payload": 0, "samples": len(shape),
            "file": "wave", "sha256": sha(raw), "frames": frames,
            "edit": {"kind": "none", "source_start": 0, "count": 0},
            "boundary_generation": {"gap_before_frame": 4, "zero_samples_before_shaping": 100, "relaxed_dibit": 1 if relaxed else None}}
    return wave, {"vectors": {"vectors": metas}}


def ctx(symbols, confirmed=1):
    return {"symbols": symbols, "generation": 1, "profile": 1, "sps": 20, "rf": 2,
            "eligible": 1, "confirmed": confirmed, "owner": 1}


def policy_fixture(enabled=1):
    rows = [{"kind": "reset_begin"}, {"kind": "reset_end"},
            {"kind": "search_begin", "symbolcnt": 0, "hunt_idx": 1, "sps": 20, "rf_mod": 2, "confirmed": 0},
            {"kind": "search_end", "symbolcnt": 10, "hunt_idx": 1, "sps": 20, "rf_mod": 2, "confirmed": 0},
            {"kind": "frame_begin", "sync": 28, "frame": 0, "symbolcnt": 10, "hunt_idx": 1, "sps": 20, "rf_mod": 2, "confirmed": 0},
            {"kind": "frame_end", "frame": 0, "symbolcnt": 192, "hunt_idx": 1, "sps": 20, "rf_mod": 2, "confirmed": 1, "value": 2},
            {"kind": "search_begin", "symbolcnt": 192, "hunt_idx": 1, "sps": 20, "rf_mod": 2, "confirmed": 1},
            {"kind": "search_end", "symbolcnt": 587, "hunt_idx": 1, "sps": 20, "rf_mod": 2, "confirmed": 1}]
    anchor = ctx(192)
    records = [{"seq": 0, "kind": "configuration", "enabled": enabled},
               {"seq": 1, "kind": "reset", "reason": "carrier", "valid_before": 0, "valid_after": 0},
               {"seq": 2, "kind": "match", "next_frame": 0, "context": ctx(10, 0), "pattern": "3131331131",
                "decision": {"allow": 1, "would_block": 0, "canonical": 1, "window": 0, "age": 0,
                             "reason": "unarmed", "valid_before": 0, "valid_after": 0}, "anchor": None},
               {"seq": 3, "kind": "frame", "frame": 0, "begin": ctx(10, 0), "end": anchor, "result": 2,
                "armed": 1, "valid_before": 0, "valid_after": 1, "anchor": anchor}]
    cases = [(201, "3331331111", 1, 0, "expected_window"),
             (339, "3331331111", 0, 1, "off_phase"),
             (394, "1313113313", 2, 0, "canonical"),
             (587, "3331331111", 3, 0, "expected_window")]
    for symbol, pattern, window, would, reason in cases:
        records.append({"seq": len(records), "kind": "match", "next_frame": 1, "context": ctx(symbol), "pattern": pattern,
                        "decision": {"allow": int(not (enabled and would)), "would_block": would, "canonical": int(reason == "canonical"),
                                     "window": window, "age": symbol-192, "reason": reason, "valid_before": 1, "valid_after": 1},
                        "anchor": anchor})
    records.append({"seq": len(records), "kind": "summary", "enabled": enabled, "frames": 1, "matches": 5,
                    "resets": 1, "arms": 1, "vetoes": enabled, "errors": 0})
    return records, rows


def good_frame(ordinal, kind="S", scch_pass=True):
    bits = "0" * 25
    channel = {"channel": 7, "part": 0, "accepted": scch_pass, "exact_source_content": True, "correct": scch_pass,
               "bits": bits, "computed": 17, "received": 17 if scch_pass else 81}
    return {"source": {"ordinal": ordinal, "kind": kind}, "fully_sampled": True, "source_body_exact": True,
            "full_correct": kind != "V" or scch_pass, "supported_current_proof": kind != "V" or scch_pass,
            "end": {"frame": ordinal, "value": 2 if kind != "V" or scch_pass else 1, "confirmed": 1,
                    "symbolcnt": (ordinal + 1) * 192, "body": "0" * 182},
            "events": [{"kind": "voice_begin", "value": 3}] if kind == "V" else [],
            "channel_results": [channel] if kind == "V" else [], "quality_issues": []}


def complete_grid():
    manifest = {"waveforms": {}, "cases": []}; pairs = {}
    for name in sorted(analyze.REGISTERED_WAVES):
        scenario = name.split("-", 1)[1] if name.startswith("h") else name
        wave = {"scenario": scenario, "frames": []}
        if name.startswith("scch_"):
            wave["scch_expected"] = {"information_bits": "0" * 25, "computed_crc": 17,
                                     "transmitted_crc": 17 if name == "scch_valid" else 81,
                                     "crc_expected_pass": name == "scch_valid"}
        manifest["waveforms"][name] = wave
        for chunk in (37, 512):
            case = {"id": f"{name}-c{chunk}", "waveform": name, "chunk": chunk, "fast": 0}
            manifest["cases"].append(case); pairs[case["id"]] = {}
            for role in ("baseline", "candidate"):
                frames = [] if scenario in ("zero", "bad_crc") else [good_frame(3)]
                if name.startswith("scch_"):
                    frames += [good_frame(4, "V", name == "scch_valid"), good_frame(5, "V", name == "scch_valid")]
                elif name == "h0-warm_sync_invert" and role == "candidate": frames += [good_frame(6)]
                policy = {"measurement_pass": True, "enabled": int(role == "candidate"), "semantic": [{"mode": role}],
                          "matches": [{"decision": {"allow": 0}, "anchor": {"symbols": 768}}] if role == "candidate" else []}
                pairs[case["id"]][role] = {o: {"case": copy.deepcopy(case), "measurement_pass": True,
                    "input_validation": {"validated": True}, "summary": {"observed": o},
                    "semantic": [{"wave": name, "role": role}], "chunk_semantic": [{"wave": name, "role": role, "observed": o}],
                    "trace_sha256": "same-trace" if o else "empty", "policy": copy.deepcopy(policy),
                    "frames": copy.deepcopy(frames), "quality_issues": []} for o in (0, 1)}
    return pairs, manifest


class InputTests(unittest.TestCase):
    def test_all_registered_transform_kinds(self):
        for kind in ("none", "invert", "repeat", "drop", "blank", "zero"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as d:
                wave, manifest = transformed(d, kind)
                self.assertTrue(analyze.validate_inputs(wave, manifest, d)["validated"])

    def test_invert_is_bit_exact_and_occurrence_is_not_relabelable(self):
        with tempfile.TemporaryDirectory() as d:
            wave, manifest = transformed(d, "invert")
            raw = bytearray((Path(d) / "wave").read_bytes()); raw[0] ^= 1
            (Path(d) / "wave").write_bytes(raw); wave["sha256"] = sha(raw)
            with self.assertRaisesRegex(ValueError, "construction"):
                analyze.validate_inputs(wave, manifest, d)
        with tempfile.TemporaryDirectory() as d:
            wave, manifest = transformed(d, "repeat")
            raw = bytes(wave["samples"] * 4); (Path(d) / "occur").write_bytes(raw); wave["occurrence_sha256"] = sha(raw)
            with self.assertRaisesRegex(ValueError, "occurrence"):
                analyze.validate_inputs(wave, manifest, d)

    def test_lineage_tampering_even_with_updated_hash(self):
        with tempfile.TemporaryDirectory() as d:
            wave, manifest = transformed(d, "repeat")
            raw = struct.pack("<8I", *range(8)); (Path(d) / "origin").write_bytes(raw); wave["lineage_sha256"] = sha(raw)
            with self.assertRaisesRegex(ValueError, "lineage"):
                analyze.validate_inputs(wave, manifest, d)

    def test_both_preshaped_gap_constructions_and_bad_layout(self):
        for relaxed in (False, True):
            with self.subTest(relaxed=relaxed), tempfile.TemporaryDirectory() as d:
                wave, manifest = gap_fixture(d, relaxed)
                self.assertTrue(analyze.validate_inputs(wave, manifest, d)["gap_shaped"])
                wave["frames"][4]["start"] -= 100
                with self.assertRaisesRegex(ValueError, "layout"):
                    analyze.validate_inputs(wave, manifest, d)

    def test_gap_samples_cannot_be_inserted_after_shaping(self):
        with tempfile.TemporaryDirectory() as d:
            wave, manifest = gap_fixture(d)
            raw = bytearray((Path(d) / "wave").read_bytes())
            # A post-shaped gap has a hard edge instead of the registered ramp.
            raw[16000*4:16100*4] = bytes(400)
            (Path(d) / "wave").write_bytes(raw); wave["sha256"] = sha(raw)
            with self.assertRaisesRegex(ValueError, "construction"):
                analyze.validate_inputs(wave, manifest, d)

    def test_unchanged_frozen_checker_and_adapter_do_not_mutate_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            rows, trace, case, manifest = v2_fixture(d)
            original = copy.deepcopy(manifest)
            audit = analyze.inspect(rows, trace, case, manifest, d, 1)
            self.assertTrue(audit["measurement_pass"])
            self.assertTrue(audit["frames"][0]["full_correct"])
            self.assertEqual(audit["quality_issues"], [])
            self.assertEqual(manifest, original)
        with tempfile.TemporaryDirectory() as d:
            fake = Path(d) / "checker"; fake.write_text("raise RuntimeError('must not execute')")
            with mock.patch.object(analyze, "FROZEN", fake), self.assertRaisesRegex(ValueError, "Frozen"):
                analyze.frozen_namespace()

    def test_fec_corrected_content_can_support_proof_without_exact_raw_body(self):
        with tempfile.TemporaryDirectory() as d:
            rows, trace, case, manifest = v2_fixture(d)
            end = next(r for r in rows if r["kind"] == "frame_end")
            end["body"] = end["body"][:20] + "1" + end["body"][21:]
            audit = analyze.inspect(rows, trace, case, manifest, d, 1)
            frame = audit["frames"][0]
            self.assertFalse(frame["source_body_exact"])
            self.assertFalse(frame["full_correct"])
            self.assertTrue(frame["supported_current_proof"])
            self.assertEqual(frame["quality_issues"], [])

    def test_crc_valid_wrong_information_is_not_correct_source_proof(self):
        with tempfile.TemporaryDirectory() as d:
            rows, trace, case, manifest = v2_fixture(d)
            crc = analyze.frozen_namespace()["crc"]
            for row in rows:
                if row["kind"] == "crc":
                    row["bits"] = "1" + row["bits"][1:]
                    row["computed"] = row["received"] = crc(row["bits"], 6 if row["channel"] == 1 else 12)
            audit = analyze.inspect(rows, trace, case, manifest, d, 1)
            self.assertFalse(audit["frames"][0]["supported_current_proof"])
            self.assertIn("unsupported_current_proof", audit["frames"][0]["quality_issues"])


class PolicyTests(unittest.TestCase):
    def inspect(self, records, rows, enabled=1):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "policy.jsonl"; p.write_text("\n".join(json.dumps(r) for r in records) + "\n")
            return analyze.inspect_policy(p, rows, enabled)

    def test_known_arithmetic_baseline_tracking_and_candidate_veto(self):
        for enabled in (0, 1):
            records, rows = policy_fixture(enabled)
            audit = self.inspect(records, rows, enabled)
            self.assertTrue(audit["measurement_pass"])
            self.assertEqual(audit["vetoes"], enabled)
            self.assertEqual(audit["matches"][2]["decision"]["would_block"], 1)

    def test_fabricated_sticky_or_partial_frame_cannot_arm(self):
        for result, end_symbol in ((1, 192), (2, 191), (2, 193)):
            records, rows = policy_fixture()
            records[3]["result"] = rows[5]["value"] = result
            records[3]["end"]["symbols"] = rows[5]["symbolcnt"] = end_symbol
            with self.subTest(result=result, end=end_symbol), self.assertRaisesRegex(ValueError, "arming"):
                self.inspect(records, rows)

    def test_frame_counters_must_be_real_and_matches_must_be_in_hunt(self):
        records, rows = policy_fixture(); records[3]["begin"]["symbols"] += 1
        with self.assertRaisesRegex(ValueError, "real receiver|opening match"):
            self.inspect(records, rows)
        records, rows = policy_fixture(); records[4]["context"]["symbols"] = 100
        with self.assertRaisesRegex(ValueError, "search/context"):
            self.inspect(records, rows)

    def test_fixed_generation_eligibility_and_owner_not_optional(self):
        for key, value in (("generation", 2), ("eligible", 0), ("owner", 2)):
            records, rows = policy_fixture(); records[4]["context"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.inspect(records, rows)

    def test_canonical_block_and_bad_anchor_are_rejected(self):
        records, rows = policy_fixture(); records[6]["decision"]["allow"] = 0
        with self.assertRaisesRegex(ValueError, "arithmetic"):
            self.inspect(records, rows)
        records, rows = policy_fixture(); records[5]["anchor"] = {**records[5]["anchor"], "symbols": 193}
        with self.assertRaisesRegex(ValueError, "arithmetic"):
            self.inspect(records, rows)

    def test_missing_reset_or_frame_and_false_totals(self):
        records, rows = policy_fixture(); records[1]["reason"] = "profile"
        with self.assertRaisesRegex(ValueError, "carrier resets"):
            self.inspect(records, rows)
        records, rows = policy_fixture(); records[-1]["vetoes"] = 0
        with self.assertRaisesRegex(ValueError, "total"):
            self.inspect(records, rows)
        records, rows = policy_fixture(); records[3]["frame"] = 1
        with self.assertRaisesRegex(ValueError, "chronology"):
            self.inspect(records, rows)

    def test_expiry_is_strict_and_not_refreshed_by_match(self):
        records, rows = policy_fixture()
        records[-2]["context"]["symbols"] = 588
        rows[-1]["symbolcnt"] = 588
        records[-2]["decision"] = {"allow": 1, "would_block": 0, "canonical": 0, "window": 0,
                                    "age": 396, "reason": "expired", "valid_before": 1, "valid_after": 0}
        records[-2]["anchor"] = None
        self.assertTrue(self.inspect(records, rows)["measurement_pass"])
        records[-2]["decision"]["valid_after"] = 1
        with self.assertRaisesRegex(ValueError, "arithmetic"):
            self.inspect(records, rows)

    def test_unknown_sign_pattern_fails_open_without_arming(self):
        records, rows = policy_fixture()
        records[5]["pattern"] = "1111111111"
        records[5]["decision"].update(allow=1, would_block=0, reason="unknown_pattern")
        records[-1]["vetoes"] = 0
        self.assertTrue(self.inspect(records, rows)["measurement_pass"])

    def test_float_or_boolean_context_cannot_masquerade_as_counter(self):
        records, rows = policy_fixture(); records[4]["context"]["symbols"] = 201.0
        with self.assertRaisesRegex(ValueError, "policy symbols"):
            self.inspect(records, rows)
        records, rows = policy_fixture(); records[4]["context"]["eligible"] = True
        with self.assertRaisesRegex(ValueError, "policy eligible"):
            self.inspect(records, rows)


class ComparisonTests(unittest.TestCase):
    def test_complete_measured_gain_grid_passes(self):
        pairs, manifest = complete_grid(); result = analyze.compare(pairs, manifest)
        self.assertTrue(result["measurement_pass"], result["issues"])
        self.assertTrue(result["progression_pass"], result["issues"])
        self.assertEqual(result["expected_invocations"], 144)

    def test_missing_any_role_or_observer_or_case_fails_measurement(self):
        for missing in ("case", "role", "observer"):
            pairs, manifest = complete_grid(); cid = next(iter(pairs))
            if missing == "case": del pairs[cid]
            elif missing == "role": del pairs[cid]["candidate"]
            else: del pairs[cid]["candidate"][0]
            with self.subTest(missing=missing):
                self.assertFalse(analyze.compare(pairs, manifest)["measurement_pass"])

    def test_policy_observer_or_chunk_difference_fails(self):
        for observed in (0, 1):
            pairs, manifest = complete_grid()
            pairs["h0-warm_clean-c37"]["candidate"][observed]["policy"]["semantic"] = [{"changed": True}]
            result = analyze.compare(pairs, manifest)
            self.assertFalse(result["measurement_pass"])
            self.assertTrue(any(x["reason"] == "chunk_outcome_trace_or_policy_difference" for x in result["measurement_issues"]))

    def test_gap_retention_counterexample_overrides_helpful_h0_gain(self):
        pairs, manifest = complete_grid()
        for obs in (0, 1): pairs["gap5_relaxed-c37"]["candidate"][obs]["frames"] = []
        result = analyze.compare(pairs, manifest)
        self.assertFalse(result["progression_pass"])
        self.assertTrue(any(x["id"] == "gap5_relaxed-c37" for x in result["retention_losses"]))

    def test_baseline_unsupported_proof_also_fails_quality(self):
        pairs, manifest = complete_grid()
        pairs["h0-cold_clean-c37"]["baseline"][1]["quality_issues"] = [{"reason": "unsupported_current_proof"}]
        result = analyze.compare(pairs, manifest)
        self.assertTrue(result["measurement_pass"])
        self.assertFalse(result["progression_pass"])

    def test_gain_must_exist_in_both_chunks_with_warm_policy_exposure(self):
        for failure in ("no_gain", "no_veto", "cold_prefix"):
            pairs, manifest = complete_grid()
            for obs in (0, 1):
                audit = pairs["h0-warm_sync_invert-c512"]["candidate"][obs]
                if failure == "no_gain": audit["frames"] = audit["frames"][:1]
                elif failure == "no_veto": audit["policy"]["matches"] = []
                else: audit["frames"][0]["supported_current_proof"] = False
            with self.subTest(failure=failure):
                self.assertFalse(analyze.compare(pairs, manifest)["progression_pass"])

    def test_scch_wrong_control_still_requires_voice_plumbing_and_exact_content(self):
        pairs, manifest = complete_grid()
        pairs["scch_wrong-c37"]["candidate"][1]["frames"][1]["events"] = []
        result = analyze.compare(pairs, manifest)
        self.assertFalse(result["progression_pass"])
        self.assertTrue(any(x["reason"] == "clean_scch_voice_plumbing_loss" for x in result["quality_issues"]))


if __name__ == "__main__":
    unittest.main()
