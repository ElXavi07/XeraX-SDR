"""Small orchestrator negative controls; every executable invocation is mocked."""
import copy
import csv
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).with_name("run_latency.py")
SPEC = importlib.util.spec_from_file_location("xerax_run_latency_under_test", MODULE_PATH)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def constant_stats(count, value):
    if count == 0:
        return None
    return {"n": count, "p50": value, "p95": value, "p99": value, "max": value}


def fixture(variant="chunk64", statuses=None, hz=4):
    if statuses is None:
        statuses = [] if variant == "none" else [0, 9, 11, 13]
    rows = [{"kind": "append", "index": i, "call_us": 20, "wake_late_us": 5,
             "missed_deadline": 0, "status": 0, "verify_us": 0} for i in range(100)]
    rows += [{"kind": "snapshot", "index": i, "call_us": 30 if status == 0 else 1,
              "wake_late_us": 0, "missed_deadline": 0, "status": status,
              "verify_us": 4 if status == 0 else 0} for i, status in enumerate(statuses)]
    ok = statuses.count(0)
    result = {"schema": 1, "variant": variant, "format": "cf32", "seconds": 1,
              "snapshot_hz": hz, "hold_ms": 0, "appends": 100,
              "snapshot_attempts": len(statuses), "snapshot_ok": ok,
              "snapshot_busy": statuses.count(11), "snapshot_deadline": statuses.count(13),
              "snapshot_not_retained": statuses.count(9), "finish_after_next_scheduled_block": 0,
              "append_call_over_10ms": 0, "append_us": constant_stats(100, 20),
              "wake_lateness_us": constant_stats(100, 5),
              "snapshot_success_us": constant_stats(ok, 30), "verification_us": constant_stats(ok, 4),
              "snapshot_rejected_us": constant_stats(len(statuses) - ok, 1)}
    return rows, result


def write_trace(path, rows, columns=None):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns or runner.TRACE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


class TraceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="xerax-trace-unit-")
        self.addCleanup(self.temporary.cleanup)
        self.trace = Path(self.temporary.name) / "trace.csv"

    def test_valid_statuses_and_no_snapshot_control(self):
        for variant in ("chunk64", "none"):
            with self.subTest(variant=variant):
                rows, result = fixture(variant)
                write_trace(self.trace, rows)
                runner.checked_trace(self.trace, result)

    def test_missing_snapshot_attempts_rejected_even_if_counts_agree(self):
        rows, result = fixture()
        rows.pop()
        result.update(snapshot_attempts=3, snapshot_deadline=0, snapshot_rejected_us=constant_stats(2, 1))
        write_trace(self.trace, rows)
        with self.assertRaisesRegex(runner.TraceValidationError, "Incomplete snapshot-attempt"):
            runner.checked_trace(self.trace, result)

    def test_rejection_categories_cannot_be_swapped(self):
        rows, result = fixture()
        result.update(snapshot_busy=0, snapshot_not_retained=2)
        write_trace(self.trace, rows)
        with self.assertRaisesRegex(runner.TraceValidationError, "snapshot_not_retained"):
            runner.checked_trace(self.trace, result)

    def test_unknown_status_is_not_a_generic_rejection(self):
        rows, result = fixture()
        rows[-1]["status"] = 12  # Cancelled is not emitted by this harness workload.
        write_trace(self.trace, rows)
        with self.assertRaisesRegex(runner.TraceValidationError, "Unknown snapshot status"):
            runner.checked_trace(self.trace, result)

    def test_requested_workload_is_checked(self):
        rows, result = fixture()
        write_trace(self.trace, rows)
        with self.assertRaisesRegex(runner.TraceValidationError, "requested workload"):
            runner.checked_trace(self.trace, result, {"variant": "whole", "seconds": 1})

    def test_unknown_rows_missing_rows_and_bad_indices(self):
        for corruption, message in (("kind", "Unknown trace row kind"),
                                    ("missing", "Trace snapshot count"),
                                    ("index", "Append indices"),
                                    ("extra", "excess rows")):
            with self.subTest(corruption=corruption):
                rows, result = fixture()
                if corruption == "kind":
                    rows[0]["kind"] = "discarded"
                elif corruption == "missing":
                    rows.pop()
                elif corruption == "index":
                    rows[0]["index"] = 1
                else:
                    rows.append(copy.deepcopy(rows[-1]))
                write_trace(self.trace, rows)
                with self.assertRaisesRegex(runner.TraceValidationError, message):
                    runner.checked_trace(self.trace, result)

    def test_nonfinite_negative_and_missing_measurements(self):
        for corruption in ("nan_trace", "negative_trace", "nan_summary", "bad_flag",
                           "bool_count", "negative_count", "missing", "bad_percentile"):
            with self.subTest(corruption=corruption):
                rows, result = fixture()
                if corruption == "nan_trace": rows[0]["call_us"] = float("nan")
                elif corruption == "negative_trace": rows[0]["wake_late_us"] = -1
                elif corruption == "nan_summary": result["append_us"]["p99"] = float("inf")
                elif corruption == "bad_flag": rows[0]["missed_deadline"] = 2
                elif corruption == "bool_count": result["appends"] = True
                elif corruption == "negative_count": result["snapshot_busy"] = -1
                elif corruption == "missing": del result["seconds"]
                else: result["append_us"]["p95"] = 21
                write_trace(self.trace, rows)
                with self.assertRaises(runner.TraceValidationError):
                    runner.checked_trace(self.trace, result)

    def test_empty_metrics_must_be_null_and_columns_exact(self):
        rows, result = fixture("none")
        result["snapshot_success_us"] = constant_stats(1, 0)
        write_trace(self.trace, rows)
        with self.assertRaisesRegex(runner.TraceValidationError, "must be null"):
            runner.checked_trace(self.trace, result)
        rows, result = fixture()
        columns = runner.TRACE_COLUMNS + ["unrecognized"]
        write_trace(self.trace, rows, columns)
        with self.assertRaisesRegex(runner.TraceValidationError, "trace columns"):
            runner.checked_trace(self.trace, result)

    def test_validation_survives_optimized_compilation(self):
        # No child process: compile the same module as python -O would, then
        # exercise a negative case that the former assert implementation skipped.
        namespace = {"__name__": "optimized_latency_test", "__file__": str(MODULE_PATH)}
        exec(compile(MODULE_PATH.read_text(encoding="utf-8"), str(MODULE_PATH), "exec", optimize=2), namespace)
        rows, result = fixture()
        result.update(snapshot_busy=0, snapshot_not_retained=2)
        write_trace(self.trace, rows)
        with self.assertRaisesRegex(ValueError, "snapshot_not_retained"):
            namespace["checked_trace"](self.trace, result)


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="xerax-orchestrator-unit-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        frozen = self.root / "frozen"
        frozen.mkdir()
        self.baseline = frozen / "baseline.exe"
        self.candidate = self.root / "candidate.exe"
        self.baseline.write_bytes(b"not executable: subprocess is mocked")
        self.candidate.write_bytes(b"not executable: subprocess is mocked")
        for name in ("iq_history.h", "iq_history.cpp", "credit_history.h", "credit_history.cpp"):
            (frozen / name).write_bytes(b"unit fixture library identity")
        self.output = self.root / "out"
        self.argv = [str(MODULE_PATH), "--baseline", str(self.baseline), "--candidate", str(self.candidate),
                     "--out", str(self.output), "--seconds", "1", "--rounds", "1",
                     "--formats", "cf32", "--holds", "0"]

    def report(self):
        return json.loads((self.output / "report.json").read_text(encoding="utf-8"))

    def fake_complete(self, command, **kwargs):
        self.assertEqual(kwargs["timeout"], 31)
        variant = command[command.index("--variant") + 1]
        statuses = [] if variant == "none" else [0] * 10
        rows, result = fixture(variant, statuses=statuses, hz=10)
        trace = Path(command[command.index("--csv") + 1])
        write_trace(trace, rows)
        return subprocess.CompletedProcess(command, 0, json.dumps(result).encode("utf-8"), b"")

    def run_with_mock(self, side_effect):
        with mock.patch.object(sys, "argv", self.argv), \
                mock.patch.object(runner.platform, "platform", return_value="unit-test-platform"), \
                mock.patch.object(runner.platform, "processor", return_value="unit-test-processor"), \
                mock.patch.object(runner.subprocess, "run", side_effect=side_effect) as process, \
                mock.patch.object(sys, "stdout", new_callable=io.StringIO):
            runner.main()
        return process

    def test_launch_failure_preserves_report_and_diagnostic(self):
        error = OSError(193, "Synthetic executable format failure")
        with self.assertRaises(OSError):
            self.run_with_mock(error)
        report = self.report()
        self.assertFalse(report["complete"])
        self.assertEqual(len(report["trials"]), 1)
        trial = report["trials"][0]
        self.assertEqual(trial["status"], "launch_failed")
        self.assertEqual(trial["stage"], "launch")
        self.assertEqual(trial["errno"], 193)
        self.assertGreaterEqual(trial["wall_seconds_including_startup"], 0)
        self.assertEqual((self.output / trial["stdout_file"]).read_bytes(), b"")
        self.assertIn("Synthetic executable format failure",
                      (self.output / trial["stderr_file"]).read_text(encoding="utf-8"))
        self.assertEqual(report["orchestrator_sha256"], runner.digest(MODULE_PATH))

    def test_later_launch_failure_keeps_earlier_passed_evidence(self):
        calls = 0

        def execute(command, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return self.fake_complete(command, **kwargs)
            raise PermissionError(13, "Synthetic launch denied")

        with self.assertRaises(PermissionError):
            self.run_with_mock(execute)
        report = self.report()
        self.assertEqual([trial["status"] for trial in report["trials"]], ["passed", "launch_failed"])
        first = report["trials"][0]
        trace = Path(first["command"][first["command"].index("--csv") + 1])
        self.assertEqual(first["trace_sha256"], runner.digest(trace))
        self.assertFalse(report["complete"])

    def test_timeout_keeps_partial_output_and_one_trial(self):
        error = subprocess.TimeoutExpired(["mock-executable"], 31, output=b"partial output", stderr=b"partial error")
        with self.assertRaises(subprocess.TimeoutExpired):
            self.run_with_mock(error)
        report = self.report()
        self.assertEqual(len(report["trials"]), 1)
        trial = report["trials"][0]
        self.assertEqual(trial["status"], "timeout")
        self.assertEqual(trial["timeout_seconds"], 31)
        self.assertEqual((self.output / trial["stdout_file"]).read_bytes(), b"partial output")
        self.assertEqual((self.output / trial["stderr_file"]).read_bytes(), b"partial error")
        self.assertFalse(report["complete"])

    def test_nonzero_exit_and_invalid_measurement_are_preserved(self):
        def failed(command, **_kwargs):
            return subprocess.CompletedProcess(command, 3, b"failed output", b"failed diagnostic")

        with self.assertRaisesRegex(RuntimeError, "Trial failed"):
            self.run_with_mock(failed)
        report = self.report()
        self.assertEqual(report["trials"][0]["status"], "failed")
        self.assertEqual(report["trials"][0]["exit_code"], 3)

        # A distinct output directory is required; the orchestrator never overwrites a run.
        self.output = self.root / "invalid-out"
        self.argv[self.argv.index("--out") + 1] = str(self.output)

        def invalid(command, **kwargs):
            completed = self.fake_complete(command, **kwargs)
            result = json.loads(completed.stdout)
            result["append_us"]["p99"] = 900
            completed.stdout = json.dumps(result).encode("utf-8")
            return completed

        with self.assertRaises(runner.TraceValidationError):
            self.run_with_mock(invalid)
        report = self.report()
        self.assertEqual(report["trials"][0]["status"], "invalid_measurement")
        self.assertIn("append_us.p99", report["trials"][0]["error"])
        self.assertFalse(report["complete"])

    def test_success_is_mocked_but_all_artifacts_are_validated(self):
        process = self.run_with_mock(self.fake_complete)
        self.assertEqual(process.call_count, 5)
        report = self.report()
        self.assertTrue(report["complete"])
        self.assertEqual(len(report["summary"]), 5)
        self.assertEqual(report["orchestrator_sha256"], runner.digest(MODULE_PATH))
        self.assertEqual([trial["status"] for trial in report["trials"]], ["passed"] * 5)


if __name__ == "__main__":
    unittest.main()
