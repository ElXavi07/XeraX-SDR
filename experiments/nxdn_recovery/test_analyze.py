"""Synthetic falsification cases for the registered recovery checker; no native execution."""
import copy
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import analyze


def fixture(directory, outcomes=("good", "good", "good"), soft=1):
    directory = Path(directory)
    (directory / "vectors").mkdir()
    vector = bytes(192)
    (directory / "vectors/s").write_bytes(vector)
    metadata = {}
    for name, width, length in (("sacch", 6, 26), ("facch", 12, 80)):
        bits = "0" * length
        check = analyze.crc(bits, width)
        metadata[name] = {"information_bits": bits, "computed_crc": check, "transmitted_crc": check,
                          "crc_expected_pass": True}
    wave = {"scenario": "cold_clean", "payload": 0, "original_samples": 5000, "samples": 5000,
            "edit": {"kind": "none", "source_start": 0, "count": 0},
            "frames": [{"ordinal": 0, "kind": "S", "vector": "s", "start": 0, "end": 3840}]}
    blobs = {"original": struct.pack("<5000f", *([1.0] * 5000)),
             "wave": struct.pack("<5000f", *([1.0] * 5000)),
             "lineage": struct.pack("<5000I", *range(5000)), "occurrence": bytes(20000)}
    for filename, key, hash_key in (("original", "original_file", "original_sha256"),
                                   ("wave", "file", "sha256"), ("lineage", "lineage_file", "lineage_sha256"),
                                   ("occurrence", "occurrence_file", "occurrence_sha256")):
        (directory / filename).write_bytes(blobs[filename])
        wave[key] = filename
        wave[hash_key] = hashlib.sha256(blobs[filename]).hexdigest()
    case = {"id": "w-c37", "waveform": "w", "chunk": 37, "fast": 0}
    manifest = {"waveforms": {"w": wave}, "vectors": {"vectors": {"s": metadata}},
                "cases": [{k: v for k, v in case.items() if k != "fast"}]}
    state = {"confirmed": 0, "streak": 0, "evidence": 0, "proved": 0, "verdict": 1,
             "profile_valid": 0, "profile_idx": 0, "profile_symbol": 0, "hunt_idx": 2,
             "symbolcnt": 192, "sync": 28, "last_sync": 28, "sacch_non_superframe": 1,
             "audio_indices": [0, 0, 0, 0]}
    rows = []

    def add(kind, frontier=0, frame=-1, **extra):
        row = {"seq": len(rows), "kind": kind, "provided": frontier, "frontier": frontier,
               "pops": frontier, "eof": int(frontier == 5000), "frame": frame, "value": 0, **state, **extra}
        rows.append(row)
        return row

    add("configuration", **{k: 0 for k in ("audio_out", "cosine_filter", "scanner", "trunk", "trunk_scan", "voice_gate", "visit_ms")},
        msize=1, ssize=128, nxdn48=1)
    add("initialized")
    add("reset_begin")
    add("reset_end")
    add("search_begin")
    add("search_end", 200, value=28)
    add("dispatch_begin", 200, 0)
    add("frame_begin", 200, 0)
    for (channel, part), outcome in zip(analyze.CHANNELS, outcomes):
        width, length = (6, 26) if channel == 1 else (12, 80)
        bits = ("1" + "0" * (length - 1)) if outcome == "wrong_pass" else "0" * length
        computed = analyze.crc(bits, width)
        received = computed ^ int(outcome == "failed")
        add("crc", 3840, 0, channel=channel, part=part, bits=bits, computed=computed, received=received,
            soft_pass=soft, fallback=1 - soft)
        if computed == received:
            if channel == 2:
                state.update(confirmed=1, streak=0, evidence=2)
            elif state["evidence"] == 0:
                state.update(streak=state["streak"] + 1, evidence=1)
                state["confirmed"] = int(state["streak"] >= 2 or state["confirmed"])
    if not state["evidence"]:
        state["streak"] = 0
    state["proved"] = int(bool(state["confirmed"] and state["evidence"]))
    result = 2 if state["proved"] else state["confirmed"]
    # Intentionally unequal sliced body: independent FEC truth must still be credited.
    add("frame_end", 3840, 0, value=result, body="1" * 182, body_count=182,
        body_positions=list(range(220, 3841, 20)))
    state["verdict"] = int(result == 0)
    if result == 2:
        state.update(profile_valid=1, profile_idx=2, profile_symbol=192)
    add("dispatch_end", 3840, 0)
    add("search_begin", 3840)
    add("search_end", 5000, value=-1)
    add("completed", 5000)
    add("summary", 5000, observed=1, fast=0, chunk=37, errors=0, starts=0, tunes=0, samples=5000,
        skipped=0, frames=1, dispatches=1, resets=1, crcs=3, eof_reads=1, rate_calls=0, reacquire_calls=0)
    trace = directory / "trace.u32le"
    trace.write_bytes(struct.pack("<5000I", *range(5000)))
    return rows, trace, case, manifest


def compare_fixture():
    """A four-stratum cold gain with an honest warm null, all full off frames retained."""
    manifest = {"waveforms": {}, "cases": []}
    pairs = {}
    for scenario in ("warm_clean", "warm_sync_blank", "cold_clean", "cold_sync_blank"):
        for payload in (0, 1):
            wave_id = f"p{payload}-{scenario}"
            warm = scenario.startswith("warm")
            q = 16000 if warm else 640
            manifest["waveforms"][wave_id] = {
                "scenario": scenario, "payload": payload, "frames": [{"ordinal": n, "start": 640 + n * 3840}
                                                                          for n in range(8)],
                "edit": {"kind": "none" if scenario.endswith("clean") else "blank", "source_start": q, "count": 200}}
            for chunk in (37, 512):
                cid = f"{wave_id}-c{chunk}"
                case = {"id": cid, "waveform": wave_id, "chunk": chunk}
                manifest["cases"].append(case)
                pairs[cid] = {}
                for fast in (0, 1):
                    ordinals = (3, 5, 6) if warm else ((1, 2, 3) if fast == 0 else (0, 1, 2, 3))
                    frames = []
                    for n in ordinals:
                        frontier = 640 + (n + 1) * 3840
                        frames.append({"source": {"ordinal": n, "kind": "S"}, "full_correct": True,
                                       "supported_current_proof": True, "begin": {"seq": n * 10},
                                       "end": {"frontier": frontier, "seq": n * 10 + 5, "value": 2,
                                               "confirmed": 1, "streak": 0, "body": "0123"},
                                       "dispatch": {"end": {"verdict": 0}}, "crcs": [],
                                       "channel_results": [{"accepted": True}], "canonical_body_positions": [frontier]})
                    pairs[cid][fast] = {"case": {**case, "fast": fast}, "summary": {"observed": 1},
                                       "quality_issues": [], "frames": frames, "resets": [],
                                       "trace_sha256": f"same-{wave_id}-{fast}"}
    return pairs, manifest


class RecoveryChecker(unittest.TestCase):
    def test_independent_crc_matches_frozen_recurrence(self):
        old = analyze.frozen_namespace()["crc"]
        for width, length in ((6, 26), (12, 80)):
            for bits in ("0" * length, "1" * length, ("01" * length)[:length], format(12345, f"0{length}b")):
                self.assertEqual(analyze.crc(bits, width), old(bits, width))

    def test_fec_success_does_not_require_exact_sliced_dibits_or_soft_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            rows, trace, case, manifest = fixture(temp, soft=0)
            result = analyze.inspect(rows, trace, case, manifest, Path(temp), 1)
            self.assertEqual(result["full_correct_frames"], 1)
            self.assertEqual(result["quality_issues"], [])
            self.assertTrue(result["frames"][0]["supported_current_proof"])

    def test_one_good_channel_cannot_hide_an_incorrect_crc_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            rows, trace, case, manifest = fixture(temp, ("good", "wrong_pass", "good"))
            result = analyze.inspect(rows, trace, case, manifest, Path(temp), 1)
            frame = result["frames"][0]
            self.assertTrue(frame["supported_current_proof"])
            self.assertFalse(frame["full_correct"])
            self.assertIn("incorrect_accepted_content", frame["quality_issues"])

    def test_partial_valid_frame_is_not_automatically_an_unsupported_proof(self):
        with tempfile.TemporaryDirectory() as temp:
            rows, trace, case, manifest = fixture(temp, ("failed", "good", "failed"))
            result = analyze.inspect(rows, trace, case, manifest, Path(temp), 1)
            self.assertEqual(result["partial_supported_proofs"], 1)
            self.assertFalse(result["frames"][0]["full_correct"])
            self.assertEqual(result["quality_issues"], [])

    def test_first_weak_crc_cannot_supply_fresh_confirmation(self):
        with tempfile.TemporaryDirectory() as temp:
            rows, trace, case, manifest = fixture(temp, ("good", "failed", "failed"))
            result = analyze.inspect(rows, trace, case, manifest, Path(temp), 1)
            self.assertEqual(result["quality_issues"], [])
            self.assertEqual(result["supported_current_proofs"], 0)
            end = next(r for r in rows if r["kind"] == "frame_end")
            end.update(value=2, confirmed=1, proved=1)
            result = analyze.inspect(rows, trace, case, manifest, Path(temp), 1)
            self.assertIn("final_confirmation_or_return_disagreement", result["frames"][0]["quality_issues"])

    def test_unattributed_proof_is_ungrounded_not_silently_credited(self):
        with tempfile.TemporaryDirectory() as temp:
            rows, trace, case, manifest = fixture(temp)
            manifest["waveforms"]["w"]["frames"][0].update(start=40, end=3880)
            result = analyze.inspect(rows, trace, case, manifest, Path(temp), 1)
            frame = result["frames"][0]
            self.assertIsNone(frame["source"])
            self.assertIn("unsupported_current_proof", frame["quality_issues"])
            self.assertIn("accepted_content_unattributed", frame["quality_issues"])

    def test_lineage_tampering_fails_even_with_updated_file_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            _, _, _, manifest = fixture(temp)
            wave = manifest["waveforms"]["w"]
            path = Path(temp) / wave["lineage_file"]
            raw = bytearray(path.read_bytes()); raw[100:104] = struct.pack("<I", 99)
            path.write_bytes(raw); wave["lineage_sha256"] = hashlib.sha256(raw).hexdigest()
            with self.assertRaisesRegex(ValueError, "origin map disagree"):
                analyze.load_lineage(wave, Path(temp))

    def test_declared_repeat_allows_canonical_revisit_but_checks_occurrences(self):
        with tempfile.TemporaryDirectory() as temp:
            _, _, _, manifest = fixture(temp)
            wave = manifest["waveforms"]["w"]
            wave["edit"] = {"kind": "repeat", "source_start": 97, "count": 20}
            wave["samples"] += 20
            origin = list(range(97)) + list(range(97, 117)) + list(range(97, 5000))
            occurrence = [0] * 117 + [1] * 20 + [0] * (5000 - 117)
            original = (Path(temp) / wave["original_file"]).read_bytes()
            data = original[:388] + original[388:468] + original[388:]
            for key, hash_key, raw in (("file", "sha256", data),
                                       ("lineage_file", "lineage_sha256", struct.pack("<5020I", *origin)),
                                       ("occurrence_file", "occurrence_sha256", struct.pack("<5020I", *occurrence))):
                (Path(temp) / wave[key]).write_bytes(raw); wave[hash_key] = hashlib.sha256(raw).hexdigest()
            self.assertEqual(analyze.load_lineage(wave, temp), origin)
            occurrence[117] = 0
            raw = struct.pack("<5020I", *occurrence)
            (Path(temp) / wave["occurrence_file"]).write_bytes(raw)
            wave["occurrence_sha256"] = hashlib.sha256(raw).hexdigest()
            with self.assertRaisesRegex(ValueError, "occurrence labels"):
                analyze.load_lineage(wave, temp)

    def test_source_boundary_interval_is_strict_and_eof_never_proves_identity(self):
        wave = {"frames": [{"ordinal": 0, "kind": "S", "vector": "s", "start": 0}]}
        begin = {"eof": 0, "sync": 28, "frontier": 200}
        end = {"eof": 0, "frontier": 3840, "body_count": 182, "body_positions": list(range(220, 3841, 20))}
        self.assertEqual(analyze.source_identity(begin, end, wave, list(range(5000)))["ordinal"], 0)
        shifted = [i + 20 for i in range(5000)]
        self.assertIsNone(analyze.source_identity(begin, end, wave, shifted))
        end["eof"] = 1
        self.assertIsNone(analyze.source_identity(begin, end, wave, list(range(5000))))

    def test_cold_gain_never_passes_warm_improvement(self):
        pairs, manifest = compare_fixture()
        result = analyze.compare(pairs, manifest)
        self.assertTrue(result["quality_pass"], result["issues"])
        self.assertTrue(result["cold_improvement_pass"])
        self.assertFalse(result["warm_improvement_pass"])
        self.assertFalse(result["progression_pass"])

    def test_clean_relative_delivered_and_canonical_costs_stay_distinct(self):
        for count_change in (-20, 20):
            pairs, manifest = compare_fixture()
            for cid, audits in pairs.items():
                if "warm_sync_blank" in cid:
                    for audit in audits.values():
                        for frame in audit["frames"]:
                            if frame["source"]["ordinal"] >= 4:
                                frame["end"]["frontier"] += count_change
            result = analyze.compare(pairs, manifest)
            self.assertTrue(result["quality_pass"], result["issues"])
            case = next(c for c in result["cases"] if c["id"] == "p0-warm_sync_blank-c37")
            self.assertEqual(case["recovery_delay_vs_clean"], {0: count_change, 1: count_change})
            self.assertEqual(case["recovery_delay_vs_clean_canonical"], {0: 0, 1: 0})

    def test_warm_gain_requires_all_four_strata_and_all_quality_gates(self):
        pairs, manifest = compare_fixture()
        for cid, audits in pairs.items():
            if "warm_sync_blank" in cid:
                frame = copy.deepcopy(audits[1]["frames"][1])
                frame["source"]["ordinal"] = 4
                frame["begin"]["seq"] = 40
                frame["end"].update(frontier=19840, seq=45)
                frame["canonical_body_positions"] = [19840]
                audits[1]["frames"].insert(1, frame)
        result = analyze.compare(pairs, manifest)
        self.assertTrue(result["progression_pass"], result["issues"])
        self.assertEqual(result["qualifying_warm_scenarios"], ["warm_sync_blank"])
        failed_quality = copy.deepcopy(pairs)
        failed_quality["p0-warm_sync_blank-c37"][1]["quality_issues"].append("unsupported_current_proof")
        self.assertFalse(analyze.compare(failed_quality, manifest)["progression_pass"])
        for chunk in (37, 512):
            pairs[f"p1-warm_sync_blank-c{chunk}"][1]["frames"][1]["end"]["frontier"] = 23680 - analyze.GAIN_SAMPLES + 1
        result = analyze.compare(pairs, manifest)
        self.assertTrue(result["quality_pass"], result["issues"])
        self.assertFalse(result["progression_pass"])

    def test_missing_option_source_or_clean_control_blocks_progression(self):
        for mutation in ("pair", "source", "delay", "clean"):
            pairs, manifest = compare_fixture()
            cid = "p0-cold_sync_blank-c37"
            if mutation == "pair":
                del pairs[cid][1]
            elif mutation == "source":
                pairs[cid][1]["frames"] = pairs[cid][1]["frames"][:1]
            elif mutation == "delay":
                pairs[cid][1]["frames"][1]["end"]["frontier"] += 21
            else:
                pairs["p0-cold_clean-c37"][0]["frames"] = []
            self.assertFalse(analyze.compare(pairs, manifest)["quality_pass"], mutation)

    def test_reset_before_warm_fault_prevents_exposure(self):
        pairs, manifest = compare_fixture()
        audit = pairs["p0-warm_sync_blank-c37"][1]
        audit["resets"].append({"begin": {"seq": 36, "frontier": 16000, "confirmed": 1, "streak": 0},
                                "end": {"frontier": 16000, "confirmed": 0, "streak": 0}})
        result = analyze.compare(pairs, manifest)
        self.assertFalse(result["quality_pass"])
        case = next(c for c in result["cases"] if c["id"] == "p0-warm_sync_blank-c37")
        self.assertFalse(case["warm_exposure"][1])

    def test_chunk_trace_and_semantic_differences_are_not_ignored(self):
        for mutation in ("trace", "body"):
            pairs, manifest = compare_fixture()
            audit = pairs["p0-cold_clean-c512"][1]
            if mutation == "trace":
                audit["trace_sha256"] = "changed"
            else:
                audit["frames"][0]["end"]["body"] = "3333"
            result = analyze.compare(pairs, manifest)
            self.assertTrue(any(i.get("reason") == "chunk_outcome_or_trace_difference" for i in result["issues"]))

    def test_observer_projection_keeps_all_semantic_decisions(self):
        rows = [{"seq": 1, "kind": "frame_end", "pops": 1, "frontier": 1, "value": 0, "body": "01"}]
        other = copy.deepcopy(rows); other[0].update(seq=0, pops=0, frontier=0)
        self.assertEqual(analyze.semantic(rows), analyze.semantic(other))
        other[0]["value"] = 2
        self.assertNotEqual(analyze.semantic(rows), analyze.semantic(other))

    def test_frozen_inspector_hash_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.py"; path.write_text("raise RuntimeError('must not execute')")
            with patch.object(analyze, "FROZEN", path):
                with self.assertRaisesRegex(ValueError, "Frozen engine inspector changed"):
                    analyze.frozen_namespace()


if __name__ == "__main__":
    unittest.main()
