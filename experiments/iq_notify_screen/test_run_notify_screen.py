"""Negative controls for the preregistered policy, without performance trials."""
import copy
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from run_notify_screen import ORDER, captured, decide, digest, failed_decision, take_p99, validated_output_guards, verify_inputs


def passing():
    return [{"round": r, "wait_mode": mode, "returncode": 0, "error": None,
             "summary": {"schema_version": 5, "variant": "coordinator", "wait_mode": mode, "format": "cf32",
                         "fault": "none", "duration_ms": 30000, "expected_requests": 300},
             "metrics": {"measurement_eligible": True, "complete_clean_workload": True,
                         "completed_requests": 300, "eligible_verified_requests": 300,
                         "accepted_grants": 300, "verified_grants": 300, "owner_work_over_10ms": 0,
                         "timed_owner_work_ns": {"n": 3000, "p99": 1000000},
                         "process_cpu": {"valid": True, "scope": "before_thread_launch_through_join",
                                         "elapsed_ns": 1000000000 if mode == "poll" else 900000000},
                         "request_timing_bounds": [{"request_id": i,
                             "grant_observation_bracket_ns": {"before_ns": 1, "after_ns": 2},
                             "request_to_verified_ns_bounds": {"lower_ns": 1, "upper_ns": 1000001},
                             "request_to_take_ns_bounds": {
                             "lower_ns": 100, "upper_ns": 1000000}} for i in range(1, 301)]}}
            for r, modes in enumerate(ORDER, 1) for mode in modes]


class Policy(unittest.TestCase):
    def test_exact_cpu_boundary_passes_and_next_integer_fails(self):
        trials = passing()
        self.assertTrue(decide(trials)["passes_screen"])
        for run in trials:
            if run["wait_mode"] == "notify": run["metrics"]["process_cpu"]["elapsed_ns"] += 1
        self.assertIn("median_cpu_reduction_below_10_percent", decide(trials)["reasons"])

    def test_order_missing_extra_and_duplicate_trials_fail(self):
        trials = passing()
        for broken in (trials[:-1], trials + [trials[0]], list(reversed(trials)), [trials[0]] * 6):
            self.assertFalse(decide(broken)["passes_screen"])

    def test_each_pair_has_latency_gate_even_when_median_looks_good(self):
        trials = passing()
        trials[1]["metrics"]["timed_owner_work_ns"]["p99"] = 1050000
        self.assertTrue(decide(trials)["passes_screen"])
        trials[1]["metrics"]["timed_owner_work_ns"]["p99"] += 1
        self.assertIn("round_1_producer_p99_regression_above_5_percent", decide(trials)["reasons"])

    def test_take_upper_bound_gate_exact_boundary(self):
        trials = passing()
        for row in trials[1]["metrics"]["request_timing_bounds"]:
            row["request_to_take_ns_bounds"]["upper_ns"] = 2000000
        self.assertTrue(decide(trials)["passes_screen"])
        for row in trials[1]["metrics"]["request_timing_bounds"]:
            row["request_to_take_ns_bounds"]["upper_ns"] += 1
        self.assertIn("round_1_take_p99_regression_above_1ms", decide(trials)["reasons"])

    def test_all_successful_takes_include_late_replies(self):
        trials = passing()
        trials[1]["metrics"]["eligible_verified_requests"] = 285
        for row in trials[1]["metrics"]["request_timing_bounds"][-15:]:
            row["request_to_take_ns_bounds"]["upper_ns"] = 50000001
        self.assertFalse(decide(trials)["passes_screen"])

    def test_nearest_rank_p99_is_not_average_or_max(self):
        metrics = passing()[0]["metrics"]
        for i, row in enumerate(metrics["request_timing_bounds"], 1):
            row["request_to_take_ns_bounds"].update(lower_ns=0, upper_ns=i)
        self.assertEqual(take_p99(metrics), 297)

    def test_rejected_request_keeps_ledger_but_is_not_a_successful_take(self):
        trials = passing(); metrics = trials[1]["metrics"]
        metrics.update(accepted_grants=299, verified_grants=299, eligible_verified_requests=299)
        metrics["request_timing_bounds"][-1].update(grant_observation_bracket_ns=None,
                                                    request_to_verified_ns_bounds=None,
                                                    request_to_take_ns_bounds=None)
        self.assertTrue(decide(trials)["passes_screen"])
        metrics["verified_grants"] = 300
        self.assertFalse(decide(trials)["passes_screen"])

    def test_incomplete_verified_timing_identity_fails(self):
        trials = passing()
        trials[0]["metrics"]["request_timing_bounds"][0]["grant_observation_bracket_ns"] = None
        self.assertFalse(decide(trials)["passes_screen"])

    def test_absolute_and_paired_eligible_boundaries(self):
        trials = passing()
        trials[1]["metrics"]["eligible_verified_requests"] = 285
        self.assertTrue(decide(trials)["passes_screen"])
        trials[1]["metrics"]["eligible_verified_requests"] = 284
        result = decide(trials)
        self.assertIn("round_1_absolute_completion_below_95_percent", result["reasons"])
        self.assertIn("round_1_paired_completion_below_95_percent", result["reasons"])

    def test_no_unverified_or_impossible_completions(self):
        for key, value in (("eligible_verified_requests", 301), ("eligible_verified_requests", True),
                           ("verified_grants", 299), ("accepted_grants", 299), ("completed_requests", 299)):
            with self.subTest(key=key, value=value):
                trials = passing(); trials[1]["metrics"][key] = value
                self.assertFalse(decide(trials)["passes_screen"])

    def test_no_new_over_budget_work(self):
        trials = passing(); trials[1]["metrics"]["owner_work_over_10ms"] = 1
        self.assertFalse(decide(trials)["passes_screen"])
        trials[0]["metrics"]["owner_work_over_10ms"] = 1
        self.assertTrue(decide(trials)["passes_screen"])

    def test_median_cpu_requires_two_actual_pair_wins(self):
        trials = passing()
        for run in trials:
            by_mode = {"poll": [200, 100, 200], "notify": [50, 110, 220]}
            run["metrics"]["process_cpu"]["elapsed_ns"] = by_mode[run["wait_mode"]][run["round"] - 1]
        result = decide(trials)
        self.assertEqual(result["median_cpu_ratio"], .55)
        self.assertIn("fewer_than_two_paired_cpu_wins", result["reasons"])

    def test_wrong_mode_duration_format_and_schema(self):
        for key, value in (("wait_mode", "notify"), ("duration_ms", 100), ("format", "cu8"),
                           ("schema_version", 4), ("expected_requests", 299), ("fault", "append")):
            trials = passing(); trials[0]["summary"][key] = value
            self.assertFalse(decide(trials)["passes_screen"])

    def test_malformed_costs_are_not_zero_or_success(self):
        for value in (None, True, float("nan"), float("inf"), 0, -1):
            for field in ("elapsed_ns", "p99"):
                with self.subTest(value=value, field=field):
                    trials = passing()
                    key = "process_cpu" if field == "elapsed_ns" else "timed_owner_work_ns"
                    trials[0]["metrics"][key][field] = value
                    self.assertFalse(decide(trials)["passes_screen"])
        trials = passing(); trials[0]["metrics"]["process_cpu"]["valid"] = False
        self.assertFalse(decide(trials)["passes_screen"])

    def test_bad_timing_identity_bounds_or_cardinality_rejected(self):
        for alteration in ("duplicate", "missing", "reversed", "boolean"):
            trials = passing(); rows = trials[0]["metrics"]["request_timing_bounds"]
            if alteration == "duplicate": rows[1]["request_id"] = 1
            if alteration == "missing": rows.pop()
            if alteration == "reversed": rows[0]["request_to_take_ns_bounds"]["lower_ns"] = 2000000
            if alteration == "boolean": rows[0]["request_to_take_ns_bounds"]["upper_ns"] = True
            self.assertFalse(decide(trials)["passes_screen"])

    def test_failure_or_cleanup_cannot_pass(self):
        for field, value in (("measurement_eligible", False), ("complete_clean_workload", False)):
            trials = passing(); trials[0]["metrics"][field] = value
            self.assertFalse(decide(trials)["passes_screen"])
        for field, value in (("returncode", 1), ("error", "Timeout")):
            trials = passing(); trials[0][field] = value
            self.assertFalse(decide(trials)["passes_screen"])

    def test_decision_does_not_mutate_and_integrity_overrides_pass(self):
        trials = passing(); before = copy.deepcopy(trials)
        decide(trials)
        self.assertEqual(trials, before)
        self.assertFalse(failed_decision(trials, "final input mutation")["passes_screen"])

    def test_manifest_guard_rejects_changed_or_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source"; path.write_bytes(b"frozen")
            hashes = {str(path): digest(path)}
            verify_inputs(hashes)
            path.write_bytes(b"modified")
            with self.assertRaises(ValueError): verify_inputs(hashes)
            path.unlink()
            with self.assertRaises(OSError): verify_inputs(hashes)

    def test_timeout_preserves_partial_output_and_never_retries(self):
        with tempfile.TemporaryDirectory() as directory:
            exc = subprocess.TimeoutExpired(["example"], 1, output=b"partial", stderr=b"failure")
            with patch("subprocess.run", side_effect=exc) as invoke:
                result, output = captured(["example"], directory, Path(directory) / "run")
            self.assertEqual(invoke.call_count, 1)
            self.assertIsNone(result["returncode"])
            self.assertEqual(output, b"partial")
            self.assertEqual((Path(directory) / "run.stderr").read_bytes(), b"failure")
            self.assertTrue((Path(directory) / "run.process.json").exists())

    def test_retained_trace_matches_analyzed_bytes_before_and_after_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory) / "run"
            trial, run = {}, {"metrics": {}}
            for field in ("trace", "sidecar"):
                path = Path(directory) / field; path.write_bytes(field.encode())
                trial[field] = str(path)
                run[field + "_sha256"] = run["metrics"][field + "_sha256"] = digest(path)
            for suffix in (".stdout", ".stderr", ".process.json", ".summary.json", ".metrics.json"):
                Path(str(prefix) + suffix).write_bytes(b"record")
            guards = validated_output_guards(run, trial, prefix)
            verify_inputs(guards)
            run["metrics"]["trace_sha256"] = "different_analyzed_bytes"
            with self.assertRaises(ValueError): validated_output_guards(run, trial, prefix)
            run["metrics"]["trace_sha256"] = run["trace_sha256"]
            Path(trial["sidecar"]).write_bytes(b"changed_after_validation")
            with self.assertRaises(ValueError): validated_output_guards(run, trial, prefix)
            with self.assertRaises(ValueError): verify_inputs(guards)


if __name__ == "__main__":
    unittest.main()
