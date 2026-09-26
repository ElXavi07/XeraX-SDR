"""Mocked execution-failure retention tests; never invokes a native decoder."""
import json
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest import mock

import run as runner


class InvocationTests(unittest.TestCase):
    def invoke(self, directory, behavior, inspect_error=None, policy_error=None):
        root = Path(directory)
        case = {"id": "wave-c37", "waveform": "wave", "chunk": 37, "fast": 0}
        manifest = {"waveforms": {"wave": {"file": "wave.f32le"}}}
        with mock.patch.object(runner.subprocess, "run", side_effect=behavior) as launch, \
             mock.patch.object(runner.analyze, "inspect", side_effect=inspect_error,
                               return_value={"measurement_pass": True}) as inspector, \
             mock.patch.object(runner.analyze, "inspect_policy", side_effect=policy_error,
                               return_value={"measurement_pass": True, "enabled": 1}) as policy:
            result = runner.invoke(root / "candidate.exe", root / "result", case, root, manifest, 1, 1)
        saved = json.loads((root / "result/audit.json").read_text())
        self.assertEqual(result, saved)
        self.assertEqual(launch.call_count, 1)
        self.assertTrue((root / "result/invocation.json").is_file())
        self.assertTrue((root / "result/events.jsonl").is_file())
        self.assertTrue((root / "result/stderr.txt").is_file())
        return result, root / "result", inspector, policy

    @staticmethod
    def output(returncode=0, malformed=False, timeout=False):
        def fake(args, **kwargs):
            kwargs["stdout"].write(b'{"kind":"configuration"}\n' if not malformed else b'{unparseable\n')
            kwargs["stdout"].flush()
            kwargs["stderr"].write(b"retained native diagnostic\n")
            kwargs["stderr"].flush()
            Path(args[-1]).write_bytes(b"recorded-pop-bytes")
            (Path(kwargs["cwd"]) / "phase.jsonl").write_text('{"kind":"configuration"}\n')
            if timeout:
                raise subprocess.TimeoutExpired(args, kwargs["timeout"])
            return types.SimpleNamespace(returncode=returncode)
        return fake

    def test_success_attaches_policy_and_fixed_invocation(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(runner.os.environ, {"DSD_FAKE_TEST": "remove-me"}):
            def launch(args, **kwargs):
                self.assertEqual(args[2:5], ["0", "37", "1"])
                self.assertFalse(any(k.upper().startswith("DSD_") for k in kwargs["env"]))
                return self.output()(args, **kwargs)
            result, folder, inspector, policy = self.invoke(d, launch)
            self.assertTrue(result["measurement_pass"])
            self.assertTrue(result["audit"]["policy"]["measurement_pass"])
            self.assertEqual(inspector.call_count, 1)
            self.assertEqual(policy.call_args.args[0], folder / "phase.jsonl")
            self.assertEqual(policy.call_args.args[2], 1)
            self.assertFalse((folder / "failure.txt").exists())

    def test_nonzero_exit_keeps_raw_and_rejects_passing_checkers(self):
        with tempfile.TemporaryDirectory() as d:
            result, folder, _, _ = self.invoke(d, self.output(returncode=9))
            self.assertFalse(result["measurement_pass"])
            self.assertEqual(result["exit_code"], 9)
            self.assertTrue((folder / "pops.u32le").is_file())
            self.assertIn("Native or measurement", (folder / "failure.txt").read_text())

    def test_timeout_keeps_partial_stdout_stderr_trace_and_failure(self):
        with tempfile.TemporaryDirectory() as d:
            result, folder, inspector, policy = self.invoke(d, self.output(timeout=True))
            self.assertFalse(result["measurement_pass"])
            self.assertEqual(result["exception"], "TimeoutExpired")
            self.assertIsNone(result["exit_code"])
            self.assertIn("configuration", (folder / "events.jsonl").read_text())
            self.assertIn("retained native", (folder / "stderr.txt").read_text())
            self.assertEqual((folder / "pops.u32le").read_bytes(), b"recorded-pop-bytes")
            self.assertEqual((inspector.call_count, policy.call_count), (0, 0))

    def test_malformed_output_retained_without_inspector_call(self):
        with tempfile.TemporaryDirectory() as d:
            result, folder, inspector, _ = self.invoke(d, self.output(malformed=True))
            self.assertFalse(result["measurement_pass"])
            self.assertEqual(result["exception"], "JSONDecodeError")
            self.assertEqual((folder / "events.jsonl").read_bytes(), b"{unparseable\n")
            self.assertEqual(inspector.call_count, 0)

    def test_inspector_or_policy_exception_is_not_native_success(self):
        for inspector_fails in (False, True):
            with self.subTest(inspector=inspector_fails), tempfile.TemporaryDirectory() as d:
                result, folder, _, _ = self.invoke(d, self.output(),
                    inspect_error=ValueError("bad actual trace") if inspector_fails else None,
                    policy_error=None if inspector_fails else FileNotFoundError("phase.jsonl"))
                self.assertFalse(result["measurement_pass"])
                self.assertEqual(result["exit_code"], 0)
                self.assertTrue((folder / "failure.txt").is_file())

    def test_existing_attempt_directory_cannot_be_retried(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "result").mkdir()
            with mock.patch.object(runner.subprocess, "run") as launch, self.assertRaises(FileExistsError):
                runner.invoke(Path(d) / "binary", Path(d) / "result", {}, Path(d), {}, 0, 0)
            launch.assert_not_called()

    def test_preservation_detects_changed_missing_and_unmodified_files(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "frozen"; p.write_bytes(b"frozen")
            group = {str(p): runner.prepare.sha(p)}
            self.assertTrue(runner.preserved(group))
            p.write_bytes(b"changed")
            self.assertFalse(runner.preserved(group))
            p.unlink()
            self.assertFalse(runner.preserved(group))


if __name__ == "__main__":
    unittest.main()
