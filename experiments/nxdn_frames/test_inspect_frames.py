"""Small synthetic complete-grid controls; no native receiver is executed."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

import generate_vectors
import inspect_frames as inspect


def event(truth, variant, name, frame_call=0, consumed=8320, pops=2):
    row = truth[variant][name]
    passing = row["computed_crc"] == row["transmitted_crc"]
    return {"frame_call": frame_call, "channel": 1 if name == "sacch" else 2,
            "part": {"sacch": 0, "facch_a": 1, "facch_b": 2}[name],
            "computed": row["computed_crc"], "received": row["transmitted_crc"],
            "soft_pass": int(passing), "fallback": int(not passing), "bits": row["information_bits"],
            "consumed_end": consumed, "pop_count": pops}


def empty_run():
    return {"frames": [], "events": [], "dispatches": [], "voice_requests": 0,
            "other_side_effects": 0, "errors": 0, "pop_count": 0, "skipped_samples": 0,
            "lineage_errors": 0, "source_frontier": 0, "exhausted": 1}


class IndependentFrameEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vector_dir = self.root / "vectors"
        self.manifest = generate_vectors.generate(self.vector_dir)
        self.truth = self.manifest["frames"]
        self.out = self.root / "evidence"
        self.out.mkdir()
        self.log = self.out / "cases.jsonl"
        self.rows = []
        for variant in inspect.VECTOR_HASHES:
            self.rows.append({"schema": 2, "kind": "direct", "variant": variant,
                              "events": [event(self.truth, variant, name, -1, 0, 0) for name in ("sacch", "facch_a", "facch_b")],
                              "errors": 0, "original_iq_samples": None, "pcm_latency": None})
        for scenario, ramp, offset, chunk in sorted(inspect.MATRIX):
            identity = "%s-r%d-o%d-c%d" % (scenario, ramp, offset, chunk)
            observed = empty_run()
            baseline = empty_run()
            indices = [16639]
            if scenario in ("valid", "mixed", "bad_crc", "bad_lich"):
                variant = {"valid": "valid", "mixed": "valid", "bad_crc": "wrong_all_crc", "bad_lich": "wrong_lich"}[scenario]
                events = [] if scenario == "bad_lich" else [event(self.truth, variant, name) for name in ("sacch", "facch_a", "facch_b")]
                result = 2 if variant == "valid" else 0
                frame = {"sync_code": 28, "provider_sync": 4680, "cache_sync_pos": 1, "cache_sync_len": 1,
                         "provider_end": 8320, "cache_end_pos": 1, "cache_end_len": 1,
                         "result": result, "confirmed": int(result == 2), "source_truncated": 0, "last_sync": 28,
                         "dispatch_begin": 0, "dispatch_end": 0, "voice_after": 0,
                         "crc_begin": 0, "crc_end": len(events), "sync_consumed": 4680,
                         "end_consumed": 8320, "pop_sync": 1, "pop_end": 2}
                observed["frames"] = [frame]
                observed["events"] = events
                original = copy.deepcopy(frame)
                original.update(crc_begin=0, crc_end=0, sync_consumed=None, end_consumed=None, pop_sync=0, pop_end=0)
                baseline["frames"] = [original]
                indices = [4679, 8319, 16639]
            observed.update(pop_count=len(indices), source_frontier=16640, skipped_samples=16640 - offset - len(indices))
            self.write_pops(identity, indices)
            self.rows.append({"schema": 2, "kind": "case", "id": identity, "scenario": scenario,
                              "ramp": ramp, "offset": offset, "chunk": chunk, "domain": inspect.DOMAIN,
                              "rate_hz": 48000, "waveform_samples": 16640, "pop_trace": identity + ".u32le",
                              "baseline": baseline, "observed": observed, "original_iq_samples": None, "pcm_latency": None})
        self.rows.append({"schema": 2, "kind": "summary", "cases": 156, "direct_cases": 3, "failures": 0,
                          "domain": inspect.DOMAIN, "rate_hz": 48000, "original_iq_samples": None, "pcm_latency": None})

    def write_pops(self, identity, values):
        (self.out / (identity + ".u32le")).write_bytes(b"".join(struct.pack("<I", value) for value in values))

    def case(self, scenario="valid"):
        return next(row for row in self.rows if row["kind"] == "case" and row["scenario"] == scenario)

    def run_check(self):
        self.log.write_text("".join(json.dumps(row) + "\n" for row in self.rows), encoding="utf-8")
        return inspect.analyze(self.log, self.out, self.vector_dir / "vectors.json")

    def test_complete_grid_passes_all_separate_gates(self):
        result = self.run_check()
        self.assertTrue(result["instrumentation_contract_pass"], result["instrumentation_errors"])
        self.assertTrue(result["direct_block_gate_pass"], result["direct_errors"])
        self.assertTrue(result["receiver_gate_pass"], result["receiver_errors"])
        self.assertTrue(result["gate_pass"])
        self.assertEqual(len(result["cases"]), 156)
        self.assertEqual(result["valid_complete_frames"], 126)
        self.assertEqual([row["passing_crc_events"] for row in result["direct_cases"]], [3, 0, 3])
        self.assertEqual(result["log_sha256"], hashlib.sha256(self.log.read_bytes()).hexdigest())

    def test_no_cold_acquisition_preserves_valid_measurement_failure(self):
        row = self.case()
        row["baseline"] = empty_run()
        row["observed"] = empty_run()
        row["observed"].update(pop_count=1, source_frontier=16640, skipped_samples=16639 - row["offset"])
        self.write_pops(row["id"], [16639])
        result = self.run_check()
        self.assertTrue(result["measurement_contract_pass"])
        self.assertFalse(result["receiver_gate_pass"])
        self.assertIn("no_true_valid_complete_frame", {item["reason"] for item in result["receiver_errors"]})

    def test_truncated_true_boundary_cannot_count_as_fully_supplied_success(self):
        row = self.case()
        for branch in ("baseline", "observed"):
            row[branch]["frames"][0]["source_truncated"] = 1
        result = self.run_check()
        self.assertTrue(result["measurement_contract_pass"])
        self.assertFalse(result["receiver_gate_pass"])
        reasons = {item["reason"] for item in result["receiver_errors"]}
        self.assertIn("source_truncated_current_proof", reasons)
        self.assertIn("no_true_valid_complete_frame", reasons)
        self.assertNotIn("false_or_nonprotocol_current_proof", reasons)
        case = next(case for case in result["cases"] if case["id"] == row["id"])
        self.assertEqual(case["valid_complete_frames"], 0)
        self.assertTrue(case["frames"][0]["source_truncated"])
        self.assertEqual(case["passing_crc_events"], 3)

    def test_truncated_off_boundary_proof_keeps_explicit_eof_qualification(self):
        row = self.case()
        for branch in ("baseline", "observed"):
            row[branch]["frames"][0].update(source_truncated=1, provider_sync=4240)
        row["observed"]["frames"][0]["sync_consumed"] = 4240
        self.write_pops(row["id"], [4239, 8319, 16639])
        result = self.run_check()
        self.assertTrue(result["measurement_contract_pass"])
        reasons = {item["reason"] for item in result["receiver_errors"]}
        self.assertIn("source_truncated_current_proof", reasons)
        self.assertNotIn("false_or_nonprotocol_current_proof", reasons)

    def test_truncation_flag_is_bounded_and_common_observer_parity(self):
        row = self.case()
        row["observed"]["frames"][0]["source_truncated"] = 1
        self.assertFalse(self.run_check()["instrumentation_contract_pass"])
        row["observed"]["frames"][0]["source_truncated"] = 2
        with self.assertRaises(ValueError):
            self.run_check()

    def test_false_sync_without_proof_is_recorded_not_malformed(self):
        row = self.case("random")
        source = copy.deepcopy(self.case())
        row["baseline"], row["observed"] = source["baseline"], source["observed"]
        for branch in ("baseline", "observed"):
            frame = row[branch]["frames"][0]
            frame.update(provider_sync=4240, provider_end=8000, result=0, confirmed=0, crc_end=0)
        row["observed"]["frames"][0].update(sync_consumed=4240, end_consumed=8000)
        row["observed"]["events"] = []
        self.write_pops(row["id"], [4239, 7999, 16639])
        result = self.run_check()
        self.assertTrue(result["gate_pass"], result)
        self.assertEqual(result["off_boundary_syncs"], 1)

    def test_false_sync_current_proof_fails_receiver_only(self):
        row = self.case()
        for branch in ("baseline", "observed"):
            row[branch]["frames"][0]["provider_sync"] = 4240
        row["observed"]["frames"][0]["sync_consumed"] = 4240
        self.write_pops(row["id"], [4239, 8319, 16639])
        result = self.run_check()
        self.assertTrue(result["measurement_contract_pass"])
        self.assertFalse(result["receiver_gate_pass"])
        self.assertIn("false_or_nonprotocol_current_proof", {item["reason"] for item in result["receiver_errors"]})

    def test_old_schema_one_is_rejected_not_silently_reinterpreted(self):
        for row in self.rows:
            row["schema"] = 1
        with self.assertRaises(ValueError):
            self.run_check()

    def test_inverted_nonproof_retained_as_valid_negative_measurement(self):
        row = self.case("random")
        source = copy.deepcopy(self.case())
        row["baseline"], row["observed"] = source["baseline"], source["observed"]
        for branch in ("baseline", "observed"):
            row[branch]["frames"][0].update(sync_code=29, last_sync=29, result=0, confirmed=0, crc_end=0)
        row["observed"]["events"] = []
        self.write_pops(row["id"], [4679, 8319, 16639])
        result = self.run_check()
        self.assertTrue(result["measurement_contract_pass"], result["instrumentation_errors"])
        self.assertTrue(result["receiver_gate_pass"], result["receiver_errors"])
        self.assertEqual(result["inverted_syncs"], 1)
        case = next(case for case in result["cases"] if case["id"] == row["id"])
        self.assertEqual(case["frames"][0]["sync_code"], 29)
        self.assertIsNone(case["frames"][0]["expected_variant"])

    def test_inverted_current_proof_cannot_match_positive_source_truth(self):
        row = self.case()
        for branch in ("baseline", "observed"):
            row[branch]["frames"][0].update(sync_code=29, last_sync=29)
        result = self.run_check()
        self.assertTrue(result["measurement_contract_pass"])
        self.assertFalse(result["receiver_gate_pass"])
        reasons = {item["reason"] for item in result["receiver_errors"]}
        self.assertIn("inverted_current_proof", reasons)
        self.assertIn("no_true_valid_complete_frame", reasons)
        case = next(case for case in result["cases"] if case["id"] == row["id"])
        self.assertEqual(case["valid_complete_frames"], 0)

    def test_unsupported_code_nine_is_not_relabelled_as_inverted_nxdn(self):
        row = self.case()
        for branch in ("baseline", "observed"):
            row[branch]["frames"][0]["sync_code"] = 9
        result = self.run_check()
        self.assertFalse(result["instrumentation_contract_pass"])
        self.assertIn("unsupported_sync_invocation", {item["reason"] for item in result["instrumentation_errors"]})

    def test_historical_confirmation_does_not_become_current_proof(self):
        row = self.case("bad_lich")
        for branch in ("baseline", "observed"):
            row[branch]["frames"][0].update(result=1, confirmed=1)
        self.assertTrue(self.run_check()["gate_pass"])
        for branch in ("baseline", "observed"):
            row[branch]["frames"][0]["result"] = 2
        result = self.run_check()
        self.assertTrue(result["measurement_contract_pass"])
        self.assertFalse(result["receiver_gate_pass"])

    def test_actual_crc_checked_even_when_receiver_reports_failure(self):
        row = self.case("bad_crc")
        row["observed"]["events"][0]["computed"] ^= 1
        result = self.run_check()
        self.assertFalse(result["instrumentation_contract_pass"])
        self.assertIn("computed_crc_disagrees_with_reported_information", {item["reason"] for item in result["instrumentation_errors"]})

    def test_relabelled_information_with_consistent_crc_still_fails_source_truth(self):
        row = self.case()
        crc = row["observed"]["events"][0]
        crc["bits"] = "1" + crc["bits"][1:]
        crc["computed"] = inspect._actual_crc(crc["bits"], 6)
        crc["received"] = crc["computed"]
        result = self.run_check()
        self.assertTrue(result["measurement_contract_pass"])
        self.assertFalse(result["receiver_gate_pass"])

    def test_final_hard_fallback_success_is_not_rejected_as_soft_failure(self):
        row = self.case()
        row["observed"]["events"][1].update(soft_pass=0, fallback=1)
        self.assertTrue(self.run_check()["gate_pass"])

    def test_mixed_source_ordinal_prevents_old_valid_payload_reuse(self):
        row = self.case("mixed")
        for branch in ("baseline", "observed"):
            frame = row[branch]["frames"][0]
            frame["provider_sync"] += 3840
            frame["provider_end"] += 3840
        row["observed"]["frames"][0]["sync_consumed"] += 3840
        row["observed"]["frames"][0]["end_consumed"] += 3840
        for crc in row["observed"]["events"]:
            crc["consumed_end"] += 3840
        self.write_pops(row["id"], [8519, 12159, 16639])
        result = self.run_check()
        self.assertTrue(result["measurement_contract_pass"])
        self.assertFalse(result["receiver_gate_pass"])
        self.assertIn("bad_crc_has_fresh_evidence", {item["reason"] for item in result["receiver_errors"]})

    def test_declared_boundary_tolerance_is_inclusive_and_fixed(self):
        row = self.case()
        for shift, expected in ((20, True), (21, False)):
            for branch in ("baseline", "observed"):
                row[branch]["frames"][0]["provider_sync"] = 4680 + shift
            row["observed"]["frames"][0]["sync_consumed"] = 4680 + shift
            self.write_pops(row["id"], [4679 + shift, 8319, 16639])
            result = self.run_check()
            self.assertTrue(result["measurement_contract_pass"])
            self.assertEqual(result["receiver_gate_pass"], expected)

    def test_side_effect_routing_failure_preserves_measurement_contract(self):
        row = self.case()
        for branch in ("baseline", "observed"):
            row[branch]["voice_requests"] = 1
            row[branch]["frames"][0]["voice_after"] = 1
        result = self.run_check()
        self.assertTrue(result["measurement_contract_pass"])
        self.assertFalse(result["receiver_gate_pass"])

    def test_each_evidence_file_read_once_and_hash_uses_validated_bytes(self):
        self.run_check()
        original = self.log.read_bytes()
        real_read = inspect._read
        reads = []
        def change_after_read(path, limit):
            reads.append(str(path))
            value = real_read(path, limit)
            if Path(path) == self.log:
                self.log.write_bytes(b"changed after captured read")
            return value
        with mock.patch.object(inspect, "_read", side_effect=change_after_read):
            result = inspect.analyze(self.log, self.out, self.vector_dir / "vectors.json")
        self.assertTrue(result["gate_pass"])
        self.assertEqual(len(reads), len(set(reads)))
        self.assertEqual(result["log_sha256"], hashlib.sha256(original).hexdigest())
        self.assertNotEqual(result["log_sha256"], hashlib.sha256(self.log.read_bytes()).hexdigest())

    def test_duplicate_half_or_missing_channel_fails_direct_gate(self):
        self.rows[0]["events"][2]["part"] = 1
        result = self.run_check()
        self.assertTrue(result["instrumentation_contract_pass"])
        self.assertFalse(result["direct_block_gate_pass"])

    def test_callback_frontier_cannot_pretend_earlier_sacch_availability(self):
        self.case()["observed"]["events"][0]["consumed_end"] = 5000
        result = self.run_check()
        self.assertFalse(result["instrumentation_contract_pass"])
        self.assertIn("crc_event_not_at_enclosing_frame_frontier", {item["reason"] for item in result["instrumentation_errors"]})

    def test_read_ahead_cannot_replace_consumed_sample(self):
        row = self.case()
        row["observed"]["frames"][0]["sync_consumed"] += 1
        result = self.run_check()
        self.assertFalse(result["instrumentation_contract_pass"])

    def test_pop_artifact_reordering_and_gap_mismatch_fail_contract(self):
        row = self.case()
        self.write_pops(row["id"], [8319, 4679, 16639])
        result = self.run_check()
        self.assertFalse(result["instrumentation_contract_pass"])
        self.assertIn("invalid_sample_lineage", {item["reason"] for item in result["instrumentation_errors"]})

    def test_disabled_observer_side_effect_parity_required(self):
        self.case()["baseline"]["frames"][0]["confirmed"] = 0
        self.assertFalse(self.run_check()["instrumentation_contract_pass"])

    def test_complete_grid_and_unique_identity_are_required(self):
        self.rows.pop(3)
        result = self.run_check()
        self.assertFalse(result["instrumentation_contract_pass"])
        self.assertIn("incomplete_case_matrix", {item["reason"] for item in result["instrumentation_errors"]})

    def test_vectors_cannot_be_changed_to_match_receiver_output(self):
        path = self.vector_dir / "vectors.json"
        self.manifest["frames"]["valid"]["sacch"]["information_bits"] = "0" * 26
        path.write_text(json.dumps(self.manifest))
        with self.assertRaises(ValueError):
            self.run_check()

    def test_vector_bytes_bound_to_frozen_hash(self):
        path = self.vector_dir / "valid.dibits"
        raw = bytearray(path.read_bytes())
        raw[-1] ^= 1
        path.write_bytes(raw)
        with self.assertRaises(ValueError):
            self.run_check()

    def test_unknown_fields_domains_and_nonfinite_or_duplicate_json_rejected(self):
        original = copy.deepcopy(self.rows)
        for field, value in (("domain", "complex_iq"), ("original_iq_samples", 123), ("rate_hz", 24000), ("extra", 1)):
            with self.subTest(field=field):
                self.rows = copy.deepcopy(original)
                self.case()[field] = value
                with self.assertRaises(ValueError):
                    self.run_check()
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}'):
            with self.assertRaises(ValueError):
                inspect._json(raw)

    def test_partial_pop_file_and_path_escape_rejected(self):
        row = self.case()
        (self.out / row["pop_trace"]).write_bytes(b"\0")
        with self.assertRaises(ValueError):
            self.run_check()
        row["pop_trace"] = "../other.u32le"
        with self.assertRaises(ValueError):
            self.run_check()


if __name__ == "__main__":
    unittest.main()
