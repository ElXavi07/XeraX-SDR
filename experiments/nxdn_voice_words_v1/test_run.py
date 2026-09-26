"""Exercise immutable-attempt and failure-retention behavior without native runs."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import run


class AttemptTests(unittest.TestCase):
    def test_existing_attempt_is_never_reexecuted(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "attempt"; folder.mkdir()
            (folder / "marker").write_bytes(b"keep")
            with patch.object(run.subprocess, "run") as process:
                with self.assertRaises(FileExistsError):
                    run.invoke(["unused.exe"], folder, "out.txt")
                process.assert_not_called()
            self.assertEqual((folder / "marker").read_bytes(), b"keep")

    def test_timeout_preserves_partial_output_and_has_no_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "attempt"
            def timed_out(arguments, **kwargs):
                kwargs["stdout"].write(b"partial row\n")
                kwargs["stderr"].write(b"partial diagnostic\n")
                raise subprocess.TimeoutExpired(arguments, 120)
            with patch.object(run.subprocess, "run", side_effect=timed_out) as process:
                result = run.invoke(["unused.exe", "input"], folder, "rows.jsonl")
                self.assertEqual(process.call_count, 1)
            self.assertEqual(result["exception"], "TimeoutExpired")
            self.assertIsNone(result["exit_code"])
            self.assertEqual((folder / "rows.jsonl").read_bytes(), b"partial row\n")
            self.assertEqual((folder / "stderr.txt").read_bytes(), b"partial diagnostic\n")
            self.assertIn("TimeoutExpired", (folder / "failure.txt").read_text())
            self.assertEqual(json.loads((folder / "process.json").read_text()), result)

    def test_native_failure_recorded_once_without_shell_or_dsd_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "attempt"
            with patch.dict(run.os.environ, {"DSD_TEST_OVERRIDE": "1", "dsd_other": "2"}), \
                 patch.object(run.subprocess, "run", return_value=subprocess.CompletedProcess([], 3)) as process:
                result = run.invoke(["space path/executable.exe", "space input/file"], folder, "out")
                self.assertEqual(result, {"exit_code": 3})
                self.assertEqual(process.call_count, 1)
                args, kwargs = process.call_args
                self.assertEqual(args[0], ["space path/executable.exe", "space input/file"])
                self.assertFalse(kwargs.get("shell", False))
                self.assertFalse(any(k.upper().startswith("DSD_") for k in kwargs["env"]))

    def test_preservation_detects_missing_or_modified_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "file"; p.write_bytes(b"original")
            group = {str(p): run.prepare.sha(p)}
            self.assertTrue(run.preserved(group))
            p.write_bytes(b"changed")
            self.assertFalse(run.preserved(group))
            p.unlink()
            self.assertFalse(run.preserved(group))


if __name__ == "__main__":
    unittest.main()
