"""Independent bounded positive and adversarial checks for acquisition traces."""
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest import mock

from inspect_acquisition import analyze


def payload(frame):
    cycle = "0132230110322301"
    return "".join(cycle[(frame + index) % 16] for index in range(182))


def fixture(directory):
    """Independent rectangular sample model; no production receiver imported."""
    rows = []
    for ramp in (8, 14):
        for offset in range(20):
            for chunk in (1, 37, 512):
                ident = "r%d-o%d-c%d" % (ramp, offset, chunk)
                frames = []
                for number, end in enumerate((840, 4680)):
                    delivered = offset + ((end - offset + chunk - 1) // chunk) * chunk
                    cache_pos = chunk - (delivered - end)
                    frames.append({"sync_code": 28, "provider_end": delivered,
                                   "cache_pos": cache_pos, "cache_len": chunk,
                                   "payload": payload(number), "consumed_end": end,
                                   "pop_count": end - offset, "frame_index": number,
                                   "landmark": 640 + number * 3840})
                (directory / (ident + ".u32le")).write_bytes(
                    b"".join(struct.pack("<I", i) for i in range(offset, 8320)))
                rows.append({"schema": 1, "kind": "case", "id": ident, "ramp": ramp,
                             "offset": offset, "chunk": chunk, "domain": "discriminator_samples",
                             "rate_hz": 48000, "waveform_samples": 62080,
                             "pop_trace": ident + ".u32le",
                             "baseline": {"frames": [{k: f[k] for k in
                                 ("sync_code", "provider_end", "cache_pos", "cache_len", "payload")}
                                for f in frames], "callback_count": 0},
                             "observed": {"frames": frames, "callback_count": 8320 - offset,
                                          "skipped_samples": 0, "lineage_errors": 0},
                             "original_iq_samples": None, "valid_frame_latency": None,
                             "pcm_latency": None})
    rows.append({"schema": 1, "kind": "summary", "domain": "discriminator_samples",
                 "rate_hz": 48000, "cases": 120, "lineage_control_checks": 5,
                 "failures": 0, "original_iq_samples": None,
                 "valid_frame_latency": None, "pcm_latency": None})
    return rows


class SyntheticAcquisitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temporary.name)
        cls.original = fixture(cls.directory)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.rows = copy.deepcopy(self.original)
        self.log = self.directory / "cases.jsonl"

    def result(self):
        self.log.write_text("".join(json.dumps(row) + "\n" for row in self.rows), encoding="utf-8")
        return analyze(self.log, self.directory)

    def fails(self, reason):
        result = self.result()
        self.assertFalse(result["gate_pass"])
        self.assertIn(reason, {error["reason"] for error in result["errors"]})

    def test_complete_independent_model(self):
        result = self.result()
        self.assertTrue(result["gate_pass"])
        self.assertEqual(result["independently_checked_dibits"], 120 * 2 * 182 * 2)
        self.assertEqual(result["invariant_groups"], 40)
        self.assertIsNone(result["valid_frame_latency"])
        self.assertEqual(len(result["artifact_sha256"]), 120)

    def test_original_iq_or_valid_frame_claim_rejected(self):
        for key in ("original_iq_samples", "valid_frame_latency", "pcm_latency"):
            with self.subTest(field=key):
                self.rows = copy.deepcopy(self.original)
                self.rows[0][key] = 0
                with self.assertRaises(ValueError):
                    self.result()

    def test_wrong_domain_and_rate_rejected(self):
        for key, value in (("domain", "source_complex_samples"), ("rate_hz", 2400)):
            with self.subTest(field=key):
                self.rows = copy.deepcopy(self.original)
                self.rows[0][key] = value
                with self.assertRaises(ValueError):
                    self.result()

    def test_unknown_field_rejected(self):
        self.rows[0]["valid_frame"] = True
        with self.assertRaises(ValueError):
            self.result()

    def test_boolean_counter_rejected(self):
        self.rows[0]["observed"]["callback_count"] = True
        with self.assertRaises(ValueError):
            self.result()

    def test_payload_alphabet_rejected(self):
        self.rows[0]["observed"]["frames"][0]["payload"] = "4" * 182
        with self.assertRaises(ValueError):
            self.result()

    def test_negative_sync_is_preserved_as_failure_evidence(self):
        for branch in ("baseline", "observed"):
            self.rows[0][branch]["frames"][0]["sync_code"] = -1
        self.rows[-1]["failures"] = 1
        self.fails("not_nxdn_positive_sync")

    def test_partial_payload_is_semantic_failure(self):
        for branch in ("baseline", "observed"):
            self.rows[0][branch]["frames"][0]["payload"] = payload(0)[:41]
        self.fails("payload_differs_from_independent_generator")

    def test_duplicate_json_key_rejected(self):
        self.result()
        raw = self.log.read_text()
        self.log.write_text(raw.replace('"schema": 1', '"schema": 1, "schema": 1', 1))
        with self.assertRaises(ValueError):
            analyze(self.log, self.directory)

    def test_truncated_or_nonterminal_summary_rejected(self):
        self.rows.pop()
        with self.assertRaises(ValueError):
            self.result()
        self.rows = copy.deepcopy(self.original)
        self.rows[0], self.rows[-1] = self.rows[-1], self.rows[0]
        with self.assertRaises(ValueError):
            self.result()

    def test_missing_case_fails_without_fake_success(self):
        self.rows.pop(0)
        self.fails("incomplete_declared_matrix")

    def test_duplicate_case_fails(self):
        self.rows[1] = copy.deepcopy(self.rows[0])
        self.fails("duplicate_case")

    def test_trace_traversal_rejected(self):
        self.rows[0]["pop_trace"] = "../outside.u32le"
        with self.assertRaises(ValueError):
            self.result()

    def test_exact_payload_oracle_rejects_consistent_fabrication(self):
        for branch in ("baseline", "observed"):
            self.rows[0][branch]["frames"][0]["payload"] = "0" * 182
        self.fails("payload_differs_from_independent_generator")

    def test_observer_changes_payload_or_cache_fails(self):
        self.rows[0]["baseline"]["frames"][0]["cache_pos"] = 0
        self.fails("observer_changed_baseline_result")

    def test_provider_highwater_is_not_consumed(self):
        frame = self.rows[2]["observed"]["frames"][0]
        self.assertGreater(frame["provider_end"], frame["consumed_end"])
        frame["consumed_end"] = frame["provider_end"]
        self.fails("provider_read_ahead_mislabelled_as_consumed")

    def test_frontier_must_be_a_successful_pop(self):
        self.rows[0]["observed"]["frames"][0]["pop_count"] -= 1
        self.fails("sync_frontier_not_observed_pop")

    def test_landmark_and_frame_index_verified(self):
        self.rows[0]["observed"]["frames"][0]["landmark"] += 1
        self.fails("contradictory_generated_landmark")
        self.rows = copy.deepcopy(self.original)
        self.rows[0]["observed"]["frames"][0]["frame_index"] = 1
        self.fails("contradictory_frame_index")

    def test_reported_control_and_failure_gates(self):
        self.rows[-1]["lineage_control_checks"] = 4
        self.fails("insufficient_reported_lineage_controls")
        self.rows = copy.deepcopy(self.original)
        self.rows[-1]["failures"] = 1
        self.fails("harness_reported_failures")

    def test_callback_count_and_disabled_observer(self):
        self.rows[0]["observed"]["callback_count"] += 1
        self.fails("callback_trace_count_mismatch")
        self.rows = copy.deepcopy(self.original)
        self.rows[0]["baseline"]["callback_count"] = 1
        self.fails("disabled_observer_received_callbacks")

    def test_changed_trace_bytes_reject_order_and_skip(self):
        trace = self.directory / self.rows[0]["pop_trace"]
        raw = trace.read_bytes()
        try:
            trace.write_bytes(raw[:4] + raw[:4] + raw[8:])
            self.fails("nonincreasing_popped_indices")
            trace.write_bytes(raw[4:])
            self.fails("skipped_sample_count_mismatch")
        finally:
            trace.write_bytes(raw)

    def test_unaligned_trace_rejected(self):
        trace = self.directory / self.rows[0]["pop_trace"]
        raw = trace.read_bytes()
        try:
            trace.write_bytes(raw[:-1])
            self.fails("unaligned_pop_trace")
        finally:
            trace.write_bytes(raw)

    def test_individual_valid_chunk_difference_is_reported_separately(self):
        row = self.rows[2]
        for branch in ("baseline", "observed"):
            for frame in row[branch]["frames"]:
                frame["cache_pos"] += 1
        for frame in row["observed"]["frames"]:
            frame["consumed_end"] += 1
            frame["pop_count"] += 1
        result = self.result()
        self.assertTrue(result["contract_pass"], result["errors"])
        self.assertFalse(result["chunk_invariance_pass"])
        self.assertFalse(result["gate_pass"])
        self.assertEqual(result["invariant_groups"], 39)

    def test_files_read_once_and_hash_same_bytes(self):
        self.result()
        saved_open = Path.open
        paths = []

        def tracking_open(path, *args, **kwargs):
            if args and args[0] == "rb":
                paths.append(str(path.resolve()))
            return saved_open(path, *args, **kwargs)

        raw = self.log.read_bytes()
        with mock.patch.object(Path, "open", tracking_open):
            result = analyze(self.log, self.directory)
        self.assertEqual(len(paths), 121)
        self.assertEqual(len(set(paths)), 121)
        self.assertEqual(result["log_sha256"], hashlib.sha256(raw).hexdigest())


class NativeAcquisitionTests(unittest.TestCase):
    def test_real_receiver_if_explicitly_available(self):
        path = os.environ.get("XERAX_NXDN_ACQUISITION_EXE")
        if not path:
            self.skipTest("Set XERAX_NXDN_ACQUISITION_EXE for bounded native correctness matrix")
        executable = Path(path).resolve()
        self.assertTrue(executable.is_file(), "Explicit native executable is unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            result = subprocess.run([str(executable), str(directory)], capture_output=True,
                                    timeout=300, check=False)
            log = directory / "cases.jsonl"
            log.write_bytes(result.stdout)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            metrics = analyze(log, directory)
            self.assertTrue(metrics["contract_pass"], metrics["errors"])
            # Cross-chunk invariance is an experimental result, never assumed.
            self.assertIsInstance(metrics["chunk_invariance_pass"], bool)
            self.assertEqual(metrics["case_count"], 120)


if __name__ == "__main__":
    unittest.main()
