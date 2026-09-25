import copy
import json
import math
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from xerax_bench import corpus, runner
from xerax_bench.model import contained, digest, load_corpus, percentile, write_json


class CorpusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.meta = {"format": "dsd-neo-iq", "version": 1, "sample_format": "cu8",
                     "sample_rate_hz": 48000, "capture_center_frequency_hz": 450000000}
        self.case = corpus.add_iq(self.root, "case", bytes([150, 128] * 48), self.meta,
            "nxdn48", {"kind": "known_fields", "required": ["Src=901"], "release_gate": True},
            {"kind": "synthetic", "hardware": None}, {})
        self.manifest = self.root / "manifest.json"
        self.doc = {"schema": 1, "cases": [self.case]}
        write_json(self.manifest, self.doc)

    def tearDown(self):
        self.temp.cleanup()

    def test_valid_corpus(self):
        self.assertEqual(load_corpus(self.manifest)["cases"][0]["id"], "case")

    def test_tampering_is_rejected(self):
        (self.root / "case.iq").write_bytes(bytes(96))
        with self.assertRaisesRegex(ValueError, "hash"):
            load_corpus(self.manifest)

    def test_metadata_tampering_is_rejected(self):
        (self.root / "case.iq.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "Metadata hash"):
            load_corpus(self.manifest)

    def test_sidecar_and_manifest_must_agree(self):
        self.case["input"]["sample_rate_hz"] = 96000
        write_json(self.manifest, self.doc)
        with self.assertRaisesRegex(ValueError, "Sidecar"):
            load_corpus(self.manifest)

    def test_duplicate_ids(self):
        self.doc["cases"].append(copy.deepcopy(self.case))
        write_json(self.manifest, self.doc)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            load_corpus(self.manifest)

    def test_path_escape(self):
        with self.assertRaises(ValueError):
            contained(self.root, "../outside.iq")
        with self.assertRaises(ValueError):
            contained(self.root, str(self.root.resolve()))

    def test_no_empty_known_truth(self):
        self.case["truth"]["required"] = []
        write_json(self.manifest, self.doc)
        with self.assertRaises(ValueError):
            load_corpus(self.manifest)

    def test_invalid_sample_count(self):
        self.case["input"]["samples"] = -1
        write_json(self.manifest, self.doc)
        with self.assertRaises(ValueError):
            load_corpus(self.manifest)

    def test_discriminator_has_same_duration(self):
        doc = corpus.discriminator_suite(self.manifest, self.root / "disc")
        self.assertEqual(doc["cases"][0]["input"]["samples"], 48)
        self.assertEqual(doc["cases"][0]["input"]["stage"], "discriminator")
        self.assertEqual(doc["cases"][0]["provenance"]["derived_from_iq_sha256"],
                         self.case["input"]["sha256"])

    def test_missing_adapter_recorded_not_passed(self):
        profile = self.root / "missing.json"
        write_json(profile, {"schema": 1, "name": "missing", "engine": "xerax-cli",
                             "executable": None})
        result = runner.run(self.manifest, [profile], self.root / "run", repeats=1, warmups=0)
        self.assertEqual(result["runs"][0]["status"], "unavailable")
        self.assertIsNone(result["runs"][0]["metrics"])
        self.assertIsNone(result["summary"][0]["median_wall_seconds"])

    def test_adapter_does_not_reinterpret_iq_as_audio(self):
        profile = {"engine": "dsd-fme", "executable": sys.executable}
        self.assertIsNone(runner.command(profile, self.case, self.root, self.root, "speed"))

    def test_no_shell_or_key_search_arguments(self):
        profile = {"engine": "xerax-lab", "executable": "receiver with spaces.exe",
                   "prefix": ["0", "0", "0"]}
        argv = runner.command(profile, self.case, self.root, self.root, "diagnostics")
        self.assertEqual(argv[0], "receiver with spaces.exe")
        self.assertIn("--no-config", argv)
        self.assertNotIn("--xerax-nxdn-search", argv)

    def test_output_is_not_overwritten(self):
        profile = self.root / "missing.json"
        write_json(profile, {"schema": 1, "name": "missing", "engine": "xerax-cli",
                             "executable": None})
        with self.assertRaises(FileExistsError):
            runner.run(self.manifest, [profile], self.root, repeats=1)

    def test_import_is_byte_exact_and_truth_is_not_invented(self):
        result = corpus.register_capture(self.root / "case.iq.json", self.root / "import",
            "nxdn48", "synthetic_protocol", "test only; not an off-air signal")
        case = result["cases"][0]
        self.assertEqual(case["input"]["sha256"], self.case["input"]["sha256"])
        self.assertEqual(case["truth"]["kind"], "unknown")
        self.assertFalse(case["hardware_acceptance"])

    def test_import_rejects_escaping_sidecar(self):
        meta = json.loads((self.root / "case.iq.json").read_text())
        meta["data_file"] = "../outside.iq"
        write_json(self.root / "escape.json", meta)
        with self.assertRaisesRegex(ValueError, "escapes"):
            corpus.register_capture(self.root / "escape.json", self.root / "import",
                "nxdn48", "off_air_iq", "operator declaration")

    def test_mix_identity_and_provenance(self):
        result = corpus.mix(self.manifest, "case", "case", self.root / "mix", 0, 0)
        case = result["cases"][0]
        self.assertEqual(case["input"]["sha256"], self.case["input"]["sha256"])
        self.assertEqual(len(case["provenance"]["components"]), 2)
        self.assertFalse(case["truth"]["release_gate"])
        self.assertFalse(case["hardware_acceptance"])

    def test_mix_rejects_unrepresentable_frequency(self):
        with self.assertRaisesRegex(ValueError, "Invalid mixing"):
            corpus.mix(self.manifest, "case", "case", self.root / "mix", 24000, 0)

    def test_adapter_rejects_wrong_discriminator_rate(self):
        doc = corpus.discriminator_suite(self.manifest, self.root / "disc")
        doc["cases"][0]["input"]["sample_rate_hz"] = 96000
        self.assertIsNone(runner.command({"engine": "dsd-fme", "executable": sys.executable},
            doc["cases"][0], self.root / "disc", self.root, "speed"))

    def test_negative_requires_assertion(self):
        self.case["truth"] = {"kind": "no_protocol"}
        write_json(self.manifest, self.doc)
        with self.assertRaisesRegex(ValueError, "false-positive"):
            load_corpus(self.manifest)

    def test_string_cannot_replace_boolean_gate(self):
        self.case["truth"]["release_gate"] = "false"
        write_json(self.manifest, self.doc)
        with self.assertRaisesRegex(ValueError, "boolean"):
            load_corpus(self.manifest)

    def test_arbitrary_adapter_options_rejected(self):
        profile = self.root / "bad-profile.json"
        write_json(profile, {"schema": 1, "name": "bad", "engine": "xerax-cli",
            "executable": None, "prefix": ["--invented-unreviewed-option"]})
        with self.assertRaisesRegex(ValueError, "reviewed preset"):
            runner.load_profile(profile)

    def test_stress_failures_are_not_counted_as_throughput(self):
        profile = self.root / "profile.json"
        write_json(profile, {"schema": 1, "name": "test", "engine": "xerax-cli", "executable": None})
        rows = [{"status": "completed", "duration_seconds": 2, "truth": {"release_gate": True},
                 "metrics": {"assertions_passed": False}},
                {"status": "timeout", "duration_seconds": 10, "truth": {"release_gate": True}, "metrics": None}]
        with patch.object(runner, "run", return_value={"runs": rows}):
            result = runner.stress(self.manifest, profile, self.root / "stress", workers=2, iterations=1)
        self.assertEqual((result["attempts"], result["completed"]), (4, 2))
        self.assertEqual(result["failed_release_assertions"], 2)
        self.assertAlmostEqual(result["aggregate_recording_seconds_per_wall_second"] * result["wall_seconds"], 4)
        self.assertIsNone(result["shared_channelizer_capacity"])

    def test_inspect_cli_exports_frames_without_fabricating_sample_time(self):
        source, dest = self.root / "frames.txt", self.root / "frames.jsonl"
        source.write_text("2026-09-24 FRAME AMBE slot=2 data=AA55 err=[1] [3]\n")
        result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / "bench.py"),
            "inspect", str(source), "--out", str(dest)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        frame = json.loads(dest.read_text())
        self.assertEqual(frame["slot"], 2)
        self.assertEqual(frame["payload_hex"], "AA55")
        self.assertIsNone(frame["sample_index"])


class SignalTests(unittest.TestCase):
    def test_identity_is_byte_exact(self):
        data = bytes(range(256)) * 4
        self.assertEqual(corpus.impair(data, 48000, {}, 1)[0], data)

    def test_noise_is_reproducible_and_seeded(self):
        data = bytes([170, 150, 80, 120] * 100)
        a = corpus.impair(data, 48000, {"snr_db": 10}, 4)[0]
        b = corpus.impair(data, 48000, {"snr_db": 10}, 4)[0]
        c = corpus.impair(data, 48000, {"snr_db": 10}, 5)[0]
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_dropout_preserves_timeline(self):
        data = bytes([170, 140] * 1000)
        modified, _ = corpus.impair(data, 48000, {"gap_start_fraction": .4, "gap_duration_s": .001}, 0)
        self.assertEqual(len(data), len(modified))
        self.assertEqual(modified[800:896], bytes([128, 128] * 48))

    def test_repeat_load_does_not_claim_new_calls(self):
        data = bytes([170, 140] * 100)
        modified, details = corpus.impair(data, 48000, {"repeat": 4}, 0)
        self.assertEqual(modified, data * 4)
        self.assertEqual(details["repeat"], 4)

    def test_noise_power_matches_requested_reference(self):
        data = bytes([177, 127] * 40000)
        modified, _ = corpus.impair(data, 48000, {"snr_db": 20}, 55)
        observed = sum((modified[i] - data[i]) ** 2 for i in range(len(data))) / (len(data) / 2)
        expected = ((177 - 127.5) ** 2 + .5 ** 2) / 100
        self.assertAlmostEqual(observed / expected, 1, delta=.04)

    def test_synthetic_random_signal_is_not_labeled_protocol(self):
        self.assertEqual(corpus.synthetic(48000, .01, 1, "random4fsk"),
                         corpus.synthetic(48000, .01, 1, "random4fsk"))


class EvidenceTests(unittest.TestCase):
    def test_empty_frame_log_is_observed_zero_not_missing_measurement(self):
        result = runner.score("", "", {"kind": "unknown"})
        self.assertEqual(result["decoded_vocoder_frames"], 0)
        self.assertIsNone(result["frame_payload_sha256"])

    def test_partial_payload_presence_is_not_reported_consistent(self):
        row = {"case": "case", "variant": "base", "warmup": False, "status": "completed",
               "wall_seconds": 1, "truth": {}, "metrics": {"frame_payload_sha256": "abc", "assertions_passed": True}}
        missing = copy.deepcopy(row)
        missing["metrics"]["frame_payload_sha256"] = None
        self.assertFalse(runner.summarize([row, missing])[0]["payload_consistent"])

    def test_missing_positive_is_failure(self):
        result = runner.score("", None, {"kind": "known_fields", "required": ["Src=901"]})
        self.assertFalse(result["assertions_passed"])
        self.assertIsNone(result["decoded_vocoder_frames"])

    def test_negative_detects_false_voice(self):
        result = runner.score("", "FRAME AMBE slot=1 data=A0 err=[0] [0]",
            {"kind": "no_protocol", "forbidden": [corpus.TRANSMISSION]})
        self.assertFalse(result["assertions_passed"])

    def test_payload_hash_ignores_wall_timestamp(self):
        frame = "FRAME AMBE slot=1 data=AA55 err=[0] [0]"
        a = runner.score("", "2026-01-01 01:02:03 " + frame, {"kind": "unknown"})
        b = runner.score("", "2026-02-04 11:12:13 " + frame, {"kind": "unknown"})
        self.assertEqual(a["frame_payload_sha256"], b["frame_payload_sha256"])
        self.assertIsNone(a["assertions_passed"])
        self.assertIsNone(a["bit_error_rate"])
        self.assertIsNone(a["first_pcm_sample"])

    def test_payload_hash_tracks_slot(self):
        a = runner.score("", "FRAME AMBE slot=1 data=AA err=[0] [0]", {"kind": "unknown"})
        b = runner.score("", "FRAME AMBE slot=2 data=AA err=[0] [0]", {"kind": "unknown"})
        self.assertNotEqual(a["frame_payload_sha256"], b["frame_payload_sha256"])

    def test_ansi_and_missing_statistics(self):
        result = runner.score("\x1b[32mSrc=901\x1b[0m", None,
                              {"kind": "known_fields", "required": ["Src=901"]})
        self.assertTrue(result["assertions_passed"])
        self.assertIsNone(result["audio_errors_reported"])

    def test_bad_exit_is_not_success(self):
        with tempfile.TemporaryDirectory() as temp:
            result = runner.invoke([sys.executable, "-c", "raise SystemExit(3)"],
                                   temp, Path(temp) / "log", 5)
            self.assertEqual(result["status"], "process_error")
            self.assertEqual(result["exit_code"], 3)

    def test_timeout_is_recorded(self):
        with tempfile.TemporaryDirectory() as temp:
            result = runner.invoke([sys.executable, "-c", "import time; time.sleep(5)"],
                                   temp, Path(temp) / "log", .05)
            self.assertEqual(result["status"], "timeout")

    def test_percentiles(self):
        self.assertIsNone(percentile([], .95))
        self.assertEqual(percentile([1, 3, 2], .5), 2)

    def test_failed_candidate_is_not_silently_dropped(self):
        a = {"case": "case", "repeat": 0, "variant": "base", "warmup": False,
             "status": "completed", "wall_seconds": 1, "metrics": {}, "truth": {}}
        b = dict(a, variant="trial", status="timeout")
        result = runner.compare({"profiles": [{"name": "base"}, {"name": "trial"}],
            "runs": [a, b], "measurement": "speed"}, "base", "trial")
        self.assertEqual(result["results"][0]["missing_or_failed_pairs"], 1)
        self.assertIsNone(result["results"][0]["median_process_speed_ratio"])
        self.assertEqual(result["promotion_decision"], "not_established")

    def test_gate_failure_remains_visible_when_candidate_crashes(self):
        a = {"case": "case", "repeat": 0, "variant": "base", "warmup": False,
             "status": "completed", "wall_seconds": 1, "metrics": {}, "truth": {"release_gate": True}}
        b = dict(a, variant="trial", status="process_error")
        result = runner.compare({"profiles": [{"name": "base"}, {"name": "trial"}],
            "runs": [a, b], "measurement": "speed"}, "base", "trial")
        self.assertTrue(result["results"][0]["candidate_gate_failure"])
        self.assertEqual(result["results"][0]["comparable_payload_pairs"], 0)


if __name__ == "__main__":
    unittest.main()
