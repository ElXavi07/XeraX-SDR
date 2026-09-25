"""Independent policy controls; no wall-time performance trial is launched."""
import copy
import json
import subprocess
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from run_screen import ORDER, captured, decide, failed_decision, normalized_compilation


def passing():
    return [{"round": r, "variant": v, "returncode": 0, "error": None,
             "summary": {"variant": v, "format": "cf32", "duration_ms": 30000, "fault": "none",
                         "expected_requests": 0 if v == "none" else 300},
             "metrics": {"measurement_eligible": True, "complete_clean_workload": True,
                         "accepted_grants": 0 if v == "none" else 300,
                         "verified_grants": 0 if v == "none" else 300,
                         "eligible_verified_requests": 0 if v == "none" else 300,
                         "completed_requests": 0 if v == "none" else 300,
                         "timed_owner_work_ns": {"p99": 75 if v == "coordinator" else 100, "n": 3000},
                         "owner_work_over_10ms": 0}}
            for r, variants in enumerate(ORDER, 1) for v in variants]


class DecisionTests(unittest.TestCase):
    def test_exact_25_percent_boundary_passes(self):
        self.assertTrue(decide(passing())["passes_screen"])

    def test_missing_and_reordered_trials_fail(self):
        trials = passing()
        self.assertFalse(decide(trials[:-1])["passes_screen"])
        trials[0], trials[1] = trials[1], trials[0]
        self.assertFalse(decide(trials)["passes_screen"])

    def test_invalid_metrics_and_processes_fail_closed(self):
        for key, value in (("measurement_eligible", False), ("verified_grants", 299),
                           ("eligible_verified_requests", True), ("completed_requests", 299),
                           ("owner_work_over_10ms", -1)):
            with self.subTest(key=key):
                trials = passing(); trials[1]["metrics"][key] = value
                self.assertFalse(decide(trials)["passes_screen"])
        for key, value in (("returncode", 1), ("error", "timeout")):
            trials = passing(); trials[0][key] = value
            self.assertFalse(decide(trials)["passes_screen"])

    def test_late_grants_do_not_count_as_completion(self):
        trials = passing(); trials[2]["metrics"]["eligible_verified_requests"] = 284
        self.assertFalse(decide(trials)["passes_screen"])
        trials[2]["metrics"]["eligible_verified_requests"] = 285
        self.assertTrue(decide(trials)["passes_screen"])

    def test_eligible_work_cannot_exceed_verified_work(self):
        trials = passing()
        trials[1]["metrics"].update(accepted_grants=0, verified_grants=0)
        self.assertFalse(decide(trials)["passes_screen"])

    def test_comparison_requires_both_absolute_and_paired_completion(self):
        trials = passing()
        trials[1]["metrics"]["eligible_verified_requests"] = 284
        self.assertFalse(decide(trials)["passes_screen"])
        trials[1]["metrics"]["eligible_verified_requests"] = 285
        self.assertTrue(decide(trials)["passes_screen"])

    def test_any_additional_over_budget_owner_work_fails(self):
        trials = passing(); trials[2]["metrics"]["owner_work_over_10ms"] = 1
        self.assertFalse(decide(trials)["passes_screen"])
        trials[1]["metrics"]["owner_work_over_10ms"] = 1
        self.assertTrue(decide(trials)["passes_screen"])

    def test_no_reader_outlier_is_reported_not_substituted_as_baseline(self):
        trials = passing(); trials[0]["metrics"]["timed_owner_work_ns"]["p99"] = 50000000
        self.assertTrue(decide(trials)["passes_screen"])

    def test_median_reduction_is_contemporaneous(self):
        trials = passing()
        for trial in trials:
            if trial["variant"] == "coordinator": trial["metrics"]["timed_owner_work_ns"]["p99"] = 76
        self.assertFalse(decide(trials)["passes_screen"])

    def test_two_paired_wins_required_even_with_low_median(self):
        trials = passing()
        for trial in trials:
            r, v = trial["round"], trial["variant"]
            if v == "whole": trial["metrics"]["timed_owner_work_ns"]["p99"] = [200, 100, 200][r-1]
            if v == "coordinator": trial["metrics"]["timed_owner_work_ns"]["p99"] = [50, 110, 220][r-1]
        result = decide(trials)
        self.assertEqual(result["median_ratio"], .55)
        self.assertIn("fewer_than_two_paired_p99_wins", result["reasons"])

    def test_wrong_duration_format_and_sample_count_fail(self):
        for key, value in (("duration_ms", 100), ("format", "cu8"), ("expected_requests", 299)):
            trials = passing(); trials[1]["summary"][key] = value
            self.assertFalse(decide(trials)["passes_screen"])
        for value in (None, float("nan"), True, 0):
            trials = passing(); trials[1]["metrics"]["timed_owner_work_ns"]["p99"] = value
            self.assertFalse(decide(trials)["passes_screen"])

    def test_input_is_not_mutated(self):
        trials = passing(); original = copy.deepcopy(trials)
        decide(trials)
        self.assertEqual(trials, original)

    def test_final_provenance_failure_overrides_passing_metrics(self):
        result = failed_decision(passing(), "Frozen input changed during final trial")
        self.assertFalse(result["passes_screen"])
        self.assertTrue(any("integrity_failure" in r for r in result["reasons"]))

    def test_effective_compilation_flags_must_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline, candidate = root / "baseline", root / "candidate"
            baseline.mkdir(); candidate.mkdir()
            for build, source in ((baseline, root/"frozen"), (candidate, root/"current")):
                object_name = 'CMakeFiles/abc123/source.obj' if build == baseline else 'CMakeFiles/def456/source.obj'
                entries = [{"file": str(source/"iq_history.cpp"),
                            "command": f'g++ -I{source} -O3 -o {object_name} {source}/iq_history.cpp'}]
                (build/"compile_commands.json").write_text(json.dumps(entries))
            expected = normalized_compilation(baseline, root/"frozen", root)
            self.assertEqual(expected, normalized_compilation(candidate, root/"current", root))
            path = candidate/"compile_commands.json"
            path.write_text(path.read_text().replace("-O3", "-O0"))
            self.assertNotEqual(expected, normalized_compilation(candidate, root/"current", root))

    def test_missing_compiler_object_output_is_not_silently_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/"compile_commands.json").write_text(json.dumps([{"file":"file.cpp","command":"g++ -O3 file.cpp"}]))
            with self.assertRaises(ValueError):
                normalized_compilation(root, root/"source", root)

    def test_timeout_and_oserror_preserve_failure_without_retry(self):
        for exc in (subprocess.TimeoutExpired(["example"], 1, output=b"partial", stderr=b"details"), OSError("failed")):
            with self.subTest(error=type(exc).__name__), tempfile.TemporaryDirectory() as directory:
                with patch("run_screen.subprocess.run", side_effect=exc) as invoke:
                    record, _ = captured(["example"], directory, Path(directory)/"run")
                self.assertEqual(invoke.call_count, 1)
                self.assertIsNone(record["returncode"])
                self.assertIn(type(exc).__name__, record["error"])
                self.assertTrue((Path(directory)/"run.process.json").exists())
                if isinstance(exc, subprocess.TimeoutExpired):
                    self.assertEqual((Path(directory)/"run.stdout").read_bytes(), b"partial")


if __name__ == "__main__":
    unittest.main()
