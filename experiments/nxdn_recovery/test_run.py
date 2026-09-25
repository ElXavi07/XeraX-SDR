"""Failure-path tests use a mocked process, never the native receiver."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import run


class FailureRetentionTests(unittest.TestCase):
    def invoke(self, process_effect, inspect_effect=None):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = root / "attempt"
            manifest = {"waveforms": {"w": {"file": "input.f32le"}}}
            with patch.object(run.subprocess, "run", side_effect=process_effect), \
                    patch.object(run.analyze, "inspect", side_effect=inspect_effect, return_value={}):
                rows, result = run.launch(root / "unused.exe", directory,
                    {"waveform": "w", "fast": 0, "chunk": 37}, root, manifest, 1)
            self.assertFalse(result["measurement_pass"])
            self.assertEqual(result, json.loads((directory / "audit.json").read_text()))
            self.assertTrue((directory / "invocation.json").is_file())
            self.assertTrue((directory / "failure.txt").is_file())
            return rows, result

    def test_timeout_keeps_failure_record(self):
        _, result = self.invoke(subprocess.TimeoutExpired("mock", 60))
        self.assertEqual(result["exception"], "TimeoutExpired")
        self.assertIsNone(result["exit_code"])

    def test_nonzero_exit_cannot_be_measurement_success(self):
        _, result = self.invoke(lambda *a, **kw: subprocess.CompletedProcess(a, 17))
        self.assertEqual(result["exit_code"], 17)
        self.assertIn("native exit 17", result["detail"])

    def test_invalid_trace_cannot_be_measurement_success(self):
        _, result = self.invoke(lambda *a, **kw: subprocess.CompletedProcess(a, 0),
                                ValueError("nonmonotonic sample trace"))
        self.assertIn("nonmonotonic", result["detail"])

    def test_malformed_events_are_retained_as_failure(self):
        def malformed(*args, **kwargs):
            kwargs["stdout"].write(b"not valid json\n")
            return subprocess.CompletedProcess(args, 0)
        _, result = self.invoke(malformed)
        self.assertEqual(result["exception"], "JSONDecodeError")

    def test_missing_or_mutated_execution_source_fails_preservation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.py"
            path.write_bytes(b"original")
            identities = {str(path): run.prepare.sha(path)}
            self.assertTrue(run.unchanged(identities))
            path.write_bytes(b"changed")
            self.assertFalse(run.unchanged(identities))
            path.unlink()
            self.assertFalse(run.unchanged(identities))


if __name__ == "__main__":
    unittest.main()
