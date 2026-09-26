"""Short runner-policy controls; no receiver or performance workload is run."""
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import run_acquisition as runner


FAKE_VALIDATOR = b'''import hashlib, json
def analyze(log_path, artifact_dir):
    raw = log_path.read_bytes()
    value = json.loads(raw)
    return {"gate_pass": value["gate_pass"],
            "log_sha256": hashlib.sha256(raw).hexdigest(),
            "artifact_sha256": {}}
'''


class RunnerPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        for name in runner.SOURCE_FILES:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(FAKE_VALIDATOR if name == runner.VALIDATOR else b"declared input\n")
        self.exe = self.root / "observer.exe"
        self.exe.write_bytes(b"mock executable, never run")
        self.out = self.root / "build" / "new-evidence"
        self.git = {"head": "a" * 40, "tracked_repository_dirty": True,
                    "relevant_status_porcelain": [" M experiments/nxdn_acquisition/observer.c"],
                    "scope": "mocked bounded source state"}
        self.git_patch = mock.patch.object(runner, "git_state", return_value=self.git)
        self.git_patch.start()
        self.addCleanup(self.git_patch.stop)
        platform_patch = mock.patch.object(runner.platform, "platform", return_value="test-platform")
        platform_patch.start()
        self.addCleanup(platform_patch.stop)

    def native(self, command, **kwargs):
        self.assertEqual(command, [str(self.exe), str(self.out)])
        self.assertEqual(kwargs["timeout"], 300)
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
        self.assertFalse(kwargs["check"])
        self.assertTrue((self.out / "manifest-before.json").is_file())
        kwargs["stdout"].write(b'{"gate_pass": true}\n')
        kwargs["stderr"].write(b"retained native diagnostic\n")
        return SimpleNamespace(returncode=0)

    def execute(self, behavior=None):
        with mock.patch.object(runner.subprocess, "run", side_effect=behavior or self.native) as call:
            result = runner.run(self.exe, self.out, repo_root=self.root)
        return result, call

    def phases(self, result):
        return {error["phase"] for error in result["errors"]}

    def test_success_freezes_inputs_and_binds_output_hashes(self):
        result, call = self.execute()
        self.assertTrue(result["gate_pass"], result["errors"])
        self.assertEqual(call.call_count, 1)
        self.assertEqual(result["source_git"], self.git)
        self.assertEqual(result["inputs_before"], result["inputs_after"])
        self.assertEqual(len(result["inputs_before"]), len(runner.SOURCE_FILES) + 1)
        self.assertEqual(result["validated_outputs"]["cases.jsonl"], result["output_sha256"]["cases.jsonl"])
        self.assertEqual(json.loads((self.out / "report.json").read_text()), result)
        self.assertIn("retained native diagnostic", (self.out / "stderr.log").read_text())
        self.assertFalse(result["speed_measurement"])

    def test_existing_directory_refused_without_changes(self):
        self.out.mkdir(parents=True)
        sentinel = self.out / "prior.txt"
        sentinel.write_text("unchanged")
        with mock.patch.object(runner.subprocess, "run") as call:
            with self.assertRaises(FileExistsError):
                runner.run(self.exe, self.out, repo_root=self.root)
        call.assert_not_called()
        self.assertEqual(sentinel.read_text(), "unchanged")
        self.assertEqual(list(self.out.iterdir()), [sentinel])

    def test_missing_executable_preserves_failed_report(self):
        self.exe.unlink()
        result, call = self.execute()
        self.assertFalse(result["gate_pass"])
        call.assert_not_called()
        self.assertEqual(result["native"]["status"], "not_started")
        self.assertTrue((self.out / "report.json").is_file())
        self.assertTrue((self.out / "cases.jsonl").is_file())
        self.assertIn("driver", self.phases(result))

    def test_platform_inspection_failure_preserves_failed_report(self):
        with mock.patch.object(runner.platform, "platform", side_effect=OSError("platform unavailable")):
            result, call = self.execute()
        call.assert_not_called()
        self.assertFalse(result["gate_pass"])
        self.assertIsNone(result["platform"])
        self.assertEqual(result["native"]["status"], "not_started")
        self.assertIn("platform unavailable", json.dumps(result["errors"]))
        self.assertTrue((self.out / "report.json").is_file())

    def test_native_failure_cannot_be_overridden_by_valid_output(self):
        def fail(command, **kwargs):
            self.native(command, **kwargs)
            return SimpleNamespace(returncode=7)
        result, _ = self.execute(fail)
        self.assertFalse(result["gate_pass"])
        self.assertTrue(result["analysis"]["gate_pass"])
        self.assertEqual(result["native"]["returncode"], 7)
        self.assertIn("native", self.phases(result))

    def test_independent_gate_failure_cannot_be_overridden_by_exit_zero(self):
        def fail(command, **kwargs):
            kwargs["stdout"].write(b'{"gate_pass": false}')
            return SimpleNamespace(returncode=0)
        result, _ = self.execute(fail)
        self.assertFalse(result["gate_pass"])
        self.assertIn("analysis", self.phases(result))

    def test_malformed_output_is_retained(self):
        def malformed(command, **kwargs):
            kwargs["stdout"].write(b"partial native output\n")
            kwargs["stderr"].write(b"native detail")
            return SimpleNamespace(returncode=0)
        result, _ = self.execute(malformed)
        self.assertFalse(result["gate_pass"])
        self.assertEqual((self.out / "cases.jsonl").read_bytes(), b"partial native output\n")
        self.assertEqual((self.out / "stderr.log").read_bytes(), b"native detail")
        self.assertIn("analysis", self.phases(result))

    def test_timeout_keeps_partial_files_and_first_failure(self):
        def timeout(command, **kwargs):
            kwargs["stdout"].write(b"partial before timeout")
            kwargs["stderr"].write(b"waiting")
            raise subprocess.TimeoutExpired(command, 300)
        result, _ = self.execute(timeout)
        self.assertFalse(result["gate_pass"])
        self.assertEqual(result["native"]["status"], "timeout")
        self.assertEqual(result["errors"][0]["phase"], "native")
        self.assertEqual((self.out / "cases.jsonl").read_bytes(), b"partial before timeout")
        self.assertEqual((self.out / "stderr.log").read_bytes(), b"waiting")

    def test_launch_error_preserved(self):
        result, _ = self.execute(mock.Mock(side_effect=OSError("permission denied")))
        self.assertFalse(result["gate_pass"])
        self.assertEqual(result["native"]["status"], "launch_failed")
        self.assertIn("permission denied", json.dumps(result["errors"]))

    def test_input_change_overrides_otherwise_successful_gate(self):
        def change(command, **kwargs):
            outcome = self.native(command, **kwargs)
            self.exe.write_bytes(b"changed executable")
            return outcome
        result, _ = self.execute(change)
        self.assertFalse(result["gate_pass"])
        self.assertTrue(result["analysis"]["gate_pass"])
        self.assertIn("input_integrity", self.phases(result))

    def test_frozen_validator_bytes_used_despite_source_mutation(self):
        def change(command, **kwargs):
            outcome = self.native(command, **kwargs)
            (self.root / runner.VALIDATOR).write_text("raise RuntimeError('changed validator executed')")
            return outcome
        result, _ = self.execute(change)
        self.assertTrue(result["analysis"]["gate_pass"])
        self.assertFalse(result["gate_pass"])
        self.assertIn("input_integrity", self.phases(result))

    def test_output_mutation_during_analysis_rejected(self):
        def load(source, path):
            real = runner.load_analyzer_original(source, path)
            def mutate(log, artifacts):
                value = real(log, artifacts)
                log.write_bytes(b"changed after validation")
                return value
            return mutate
        # Keep an explicit saved implementation; no mutation of the frozen file.
        saved = runner.load_analyzer
        with mock.patch.object(runner, "load_analyzer_original", saved, create=True):
            with mock.patch.object(runner, "load_analyzer", side_effect=load):
                result, _ = self.execute()
        self.assertFalse(result["gate_pass"])
        self.assertIn("output_integrity", self.phases(result))

    def test_validator_hash_mismatch_rejected(self):
        def analyzer(log, artifacts):
            return {"gate_pass": True, "log_sha256": "0" * 64, "artifact_sha256": {}}
        with mock.patch.object(runner, "load_analyzer", return_value=analyzer):
            result, _ = self.execute()
        self.assertFalse(result["gate_pass"])
        self.assertIn("validator_hash_mismatch", {e["reason"] for e in result["errors"]})

    def test_unrelated_files_not_hashed(self):
        private = self.root / "private-local.txt"
        private.write_text("not an experiment input")
        def add(command, **kwargs):
            result = self.native(command, **kwargs)
            (self.out / "unrelated.txt").write_text("not a named harness output")
            return result
        result, _ = self.execute(add)
        self.assertTrue(result["gate_pass"])
        self.assertNotIn(str(private), result["inputs_before"])
        self.assertNotIn("unrelated.txt", result["output_sha256"])

    def test_source_state_change_is_not_silently_relabelled(self):
        changed = dict(self.git, head="b" * 40)
        with mock.patch.object(runner, "git_state", side_effect=[self.git, changed]):
            result, _ = self.execute()
        self.assertFalse(result["gate_pass"])
        self.assertEqual(result["source_git"]["head"], "a" * 40)
        self.assertIn("source_integrity", self.phases(result))

    def test_cli_returns_nonzero_for_failed_run(self):
        with mock.patch.object(runner, "run", return_value={"gate_pass": False, "status": "failed"}):
            with mock.patch("builtins.print"):
                self.assertEqual(runner.main([str(self.exe), str(self.out)]), 1)


if __name__ == "__main__":
    unittest.main()
