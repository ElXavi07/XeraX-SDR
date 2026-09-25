"""Runner-policy controls with mock modules/processes, never a decoder run."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import run_frames as runner


FAKE_GENERATOR = b'''import hashlib,json
from pathlib import Path
def generate(directory):
    directory.mkdir(exist_ok=False)
    manifest={"generator_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    for index,name in enumerate(("valid","wrong_all_crc","wrong_lich")):
        (directory/(name+".dibits")).write_bytes(bytes([index])*192)
    (directory/"vectors.json").write_text(json.dumps(manifest))
    return manifest
'''

FAKE_VALIDATOR = b'''import hashlib,json
def analyze(log_path,artifact_dir,vectors_path):
    raw=log_path.read_bytes()
    value=json.loads(raw)
    hashes={str(vectors_path):hashlib.sha256(vectors_path.read_bytes()).hexdigest()}
    for name in ("valid","wrong_all_crc","wrong_lich"):
        path=vectors_path.parent/(name+".dibits")
        hashes[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
    return {"measurement_contract_pass":value["measurement"],"direct_block_gate_pass":value["direct"],
            "receiver_gate_pass":value["receiver"],"gate_pass":all(value.values()),
            "log_sha256":hashlib.sha256(raw).hexdigest(),"vector_sha256":hashes,"artifact_sha256":{}}
'''


class FrameRunnerPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        for name in runner.SOURCE_FILES:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(FAKE_GENERATOR if name == runner.GENERATOR else
                             FAKE_VALIDATOR if name == runner.VALIDATOR else b"declared research source\n")
        self.exe = self.root / "observer.exe"
        self.exe.write_bytes(b"mock observer never executed")
        self.out = self.root / "build" / "new-evidence"
        self.git = {"head": "a" * 40, "tracked_repository_dirty": True,
                    "relevant_status_porcelain": [], "scope": "mock bounded source state"}
        for patch in (mock.patch.object(runner, "git_state", return_value=self.git),
                      mock.patch.object(runner.platform, "platform", return_value="test-platform")):
            patch.start()
            self.addCleanup(patch.stop)

    def native(self, command, **kwargs):
        self.assertEqual(command, [str(self.exe), str(self.out / "vectors"), str(self.out)])
        self.assertEqual(kwargs["timeout"], 300)
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
        self.assertFalse(kwargs["check"])
        self.assertTrue((self.out / "manifest-before.json").is_file())
        self.assertTrue(all((self.out / "vectors" / name).is_file() for name in runner.VECTOR_NAMES))
        kwargs["stdout"].write(b'{"measurement":true,"direct":true,"receiver":true}')
        kwargs["stderr"].write(b"retained native diagnostics\n")
        return SimpleNamespace(returncode=0)

    def execute(self, behavior=None):
        with mock.patch.object(runner.subprocess, "run", side_effect=behavior or self.native) as call:
            result = runner.run(self.exe, self.out, repo_root=self.root)
        return result, call

    def phases(self, result):
        return {item["phase"] for item in result["errors"]}

    def test_success_hashes_explicit_sources_vectors_and_same_output(self):
        result, call = self.execute()
        self.assertTrue(result["measurement_pass"], result["errors"])
        self.assertTrue(result["receiver_gate_pass"])
        self.assertEqual(result["status"], "measurement_passed_receiver_passed")
        self.assertEqual(call.call_count, 1)
        self.assertEqual(len(result["inputs_before"]), len(runner.SOURCE_FILES) + 5)
        self.assertEqual(result["inputs_before"], result["inputs_after"])
        self.assertEqual(result["outputs_before_validation"], result["outputs_after_validation"])
        self.assertEqual(json.loads((self.out / "report.json").read_text()), result)
        manifest = json.loads((self.out / "manifest-before.json").read_text())
        self.assertEqual(manifest["inputs"], result["inputs_before"])
        self.assertEqual(result["validated_outputs"]["cases.jsonl"], result["output_sha256"]["cases.jsonl"])
        self.assertEqual(result["manifest_sha256"]["manifest-before.json"],
                         hashlib.sha256((self.out / "manifest-before.json").read_bytes()).hexdigest())
        self.assertFalse(result["speed_measurement"])

    def test_receiver_failure_is_explicit_successful_measurement(self):
        def failed_receiver(command, **kwargs):
            kwargs["stdout"].write(b'{"measurement":true,"direct":true,"receiver":false}')
            return SimpleNamespace(returncode=0)
        result, _ = self.execute(failed_receiver)
        self.assertTrue(result["measurement_pass"])
        self.assertFalse(result["receiver_gate_pass"])
        self.assertFalse(result["analysis"]["gate_pass"])
        self.assertEqual(result["status"], "measurement_passed_receiver_failed")
        with mock.patch.object(runner, "run", return_value=result), mock.patch("builtins.print"):
            self.assertEqual(runner.main([str(self.exe), str(self.out)]), 0)

    def test_measurement_failure_cannot_be_overridden_by_receiver_pass(self):
        def bad_measurement(command, **kwargs):
            kwargs["stdout"].write(b'{"measurement":false,"direct":true,"receiver":true}')
            return SimpleNamespace(returncode=0)
        result, _ = self.execute(bad_measurement)
        self.assertFalse(result["measurement_pass"])
        self.assertTrue(result["receiver_gate_pass"])
        self.assertIn("analysis", self.phases(result))

    def test_direct_failure_independently_blocks_measurement_success(self):
        def bad_direct(command, **kwargs):
            kwargs["stdout"].write(b'{"measurement":true,"direct":false,"receiver":true}')
            return SimpleNamespace(returncode=0)
        result, _ = self.execute(bad_direct)
        self.assertFalse(result["measurement_pass"])

    def test_existing_directory_and_contents_untouched(self):
        self.out.mkdir(parents=True)
        sentinel = self.out / "old.txt"
        sentinel.write_text("preserve")
        with mock.patch.object(runner.subprocess, "run") as call:
            with self.assertRaises(FileExistsError):
                runner.run(self.exe, self.out, repo_root=self.root)
        call.assert_not_called()
        self.assertEqual(sentinel.read_text(), "preserve")
        self.assertEqual(list(self.out.iterdir()), [sentinel])

    def test_missing_executable_preserves_failure_report(self):
        self.exe.unlink()
        result, call = self.execute()
        call.assert_not_called()
        self.assertFalse(result["measurement_pass"])
        self.assertEqual(result["native"]["status"], "not_started")
        self.assertTrue((self.out / "report.json").is_file())

    def test_platform_error_preserved_before_launch(self):
        with mock.patch.object(runner.platform, "platform", side_effect=OSError("OS helper failed")):
            result, call = self.execute()
        call.assert_not_called()
        self.assertFalse(result["measurement_pass"])
        self.assertIn("OS helper failed", json.dumps(result["errors"]))

    def test_native_failure_preserves_valid_analysis_without_success(self):
        def bad_exit(command, **kwargs):
            self.native(command, **kwargs)
            return SimpleNamespace(returncode=9)
        result, _ = self.execute(bad_exit)
        self.assertFalse(result["measurement_pass"])
        self.assertTrue(result["analysis"]["measurement_contract_pass"])
        self.assertEqual(result["native"]["returncode"], 9)

    def test_malformed_output_and_stderr_remain_available(self):
        def malformed(command, **kwargs):
            kwargs["stdout"].write(b"partial invalid output")
            kwargs["stderr"].write(b"diagnostic details")
            return SimpleNamespace(returncode=0)
        result, _ = self.execute(malformed)
        self.assertFalse(result["measurement_pass"])
        self.assertEqual((self.out / "cases.jsonl").read_bytes(), b"partial invalid output")
        self.assertEqual((self.out / "stderr.log").read_bytes(), b"diagnostic details")

    def test_timeout_keeps_partial_evidence_and_original_failure(self):
        def timeout(command, **kwargs):
            kwargs["stdout"].write(b"partial before timeout")
            kwargs["stderr"].write(b"waiting")
            raise subprocess.TimeoutExpired(command, 300)
        result, _ = self.execute(timeout)
        self.assertFalse(result["measurement_pass"])
        self.assertEqual(result["native"]["status"], "timeout")
        self.assertEqual(result["errors"][0]["phase"], "native")
        self.assertEqual((self.out / "cases.jsonl").read_bytes(), b"partial before timeout")

    def test_launch_error_has_a_retained_report(self):
        result, _ = self.execute(mock.Mock(side_effect=OSError("cannot execute")))
        self.assertFalse(result["measurement_pass"])
        self.assertEqual(result["native"]["status"], "launch_failed")
        self.assertIn("cannot execute", json.dumps(result["errors"]))

    def test_dsd_environment_removed_without_leaking_values(self):
        def check(command, **kwargs):
            self.assertFalse(any(key.upper().startswith("DSD_") for key in kwargs["env"]))
            return self.native(command, **kwargs)
        with mock.patch.dict(os.environ, {"DSD_TEST_PRIVATE": "secret-value", "dsd_lower": "other-value"}):
            result, _ = self.execute(check)
        self.assertTrue(result["measurement_pass"])
        self.assertNotIn("secret-value", json.dumps(result))

    def test_binary_drift_fails_after_otherwise_valid_analysis(self):
        def change(command, **kwargs):
            result = self.native(command, **kwargs)
            self.exe.write_bytes(b"different observer")
            return result
        result, _ = self.execute(change)
        self.assertFalse(result["measurement_pass"])
        self.assertIn("input_integrity", self.phases(result))

    def test_vector_drift_cannot_be_relabelled_by_new_inspector_hash(self):
        def change(command, **kwargs):
            result = self.native(command, **kwargs)
            (self.out / "vectors" / "valid.dibits").write_bytes(b"different vector")
            return result
        result, _ = self.execute(change)
        self.assertFalse(result["measurement_pass"])
        self.assertIn("input_integrity", self.phases(result))
        self.assertIn("vector_changed_after_launch", {item["reason"] for item in result["errors"]})

    def test_inspector_source_drift_uses_old_frozen_bytes_but_fails_integrity(self):
        def change(command, **kwargs):
            result = self.native(command, **kwargs)
            (self.root / runner.VALIDATOR).write_text("raise RuntimeError('wrong validator executed')")
            return result
        result, _ = self.execute(change)
        self.assertTrue(result["analysis"]["measurement_contract_pass"])
        self.assertFalse(result["measurement_pass"])

    def test_generator_manifest_mismatch_prevents_observer_launch(self):
        original = runner.load_entry
        def load(source, path, entry):
            function = original(source, path, entry)
            if entry != "generate":
                return function
            def wrong(directory):
                value = function(directory)
                value["generator_sha256"] = "0" * 64
                return value
            return wrong
        with mock.patch.object(runner, "load_entry", side_effect=load):
            result, call = self.execute()
        call.assert_not_called()
        self.assertFalse(result["measurement_pass"])
        self.assertTrue((self.out / "source-inputs-before.json").is_file())

    def test_source_change_during_generation_blocks_native_launch(self):
        original = runner.load_entry
        def load(source, path, entry):
            function = original(source, path, entry)
            if entry != "generate":
                return function
            def change(directory):
                value = function(directory)
                (self.root / runner.VALIDATOR).write_text("changed source")
                return value
            return change
        with mock.patch.object(runner, "load_entry", side_effect=load):
            result, call = self.execute()
        call.assert_not_called()
        self.assertFalse(result["measurement_pass"])

    def test_output_mutation_during_analysis_fails(self):
        original = runner.load_entry
        def load(source, path, entry):
            function = original(source, path, entry)
            if entry != "analyze":
                return function
            def change(log, artifacts, vectors):
                value = function(log, artifacts, vectors)
                log.write_bytes(b"changed after captured validation")
                return value
            return change
        with mock.patch.object(runner, "load_entry", side_effect=load):
            result, _ = self.execute()
        self.assertFalse(result["measurement_pass"])
        self.assertIn("output_integrity", self.phases(result))

    def test_fabricated_validator_hash_cannot_pass_integrity(self):
        original = runner.load_entry
        def load(source, path, entry):
            function = original(source, path, entry)
            if entry != "analyze":
                return function
            def fabricate(log, artifacts, vectors):
                value = function(log, artifacts, vectors)
                value["log_sha256"] = "0" * 64
                return value
            return fabricate
        with mock.patch.object(runner, "load_entry", side_effect=load):
            result, _ = self.execute()
        self.assertFalse(result["measurement_pass"])
        self.assertIn("validator_hash_mismatch", {item["reason"] for item in result["errors"]})

    def test_inspector_must_bind_all_frozen_vector_files(self):
        original = runner.load_entry
        def load(source, path, entry):
            function = original(source, path, entry)
            if entry != "analyze":
                return function
            def omit(log, artifacts, vectors):
                value = function(log, artifacts, vectors)
                value["vector_sha256"] = {}
                return value
            return omit
        with mock.patch.object(runner, "load_entry", side_effect=load):
            result, _ = self.execute()
        self.assertFalse(result["measurement_pass"])
        self.assertIn("Inspector did not bind every frozen vector file", json.dumps(result["errors"]))

    def test_manifest_change_preserved_and_rejected(self):
        def change(command, **kwargs):
            result = self.native(command, **kwargs)
            (self.out / "manifest-before.json").write_text("{}")
            return result
        result, _ = self.execute(change)
        self.assertFalse(result["measurement_pass"])
        self.assertIn("frozen_manifest_changed: manifest-before.json", {item["reason"] for item in result["errors"]})

    def test_source_revision_change_not_relabelled(self):
        with mock.patch.object(runner, "git_state", side_effect=[self.git, dict(self.git, head="b" * 40)]):
            result, _ = self.execute()
        self.assertFalse(result["measurement_pass"])
        self.assertEqual(result["source_git"]["head"], "a" * 40)

    def test_unrelated_private_files_never_hashed(self):
        private = self.root / "private.txt"
        private.write_text("not part of the experiment")
        def add(command, **kwargs):
            result = self.native(command, **kwargs)
            (self.out / "unrelated.txt").write_text("unrelated artifact")
            return result
        result, _ = self.execute(add)
        self.assertTrue(result["measurement_pass"])
        self.assertNotIn(str(private), result["inputs_before"])
        self.assertNotIn("unrelated.txt", result["output_sha256"])

    def test_cli_failed_measurement_returns_nonzero(self):
        result = {"measurement_pass": False, "receiver_gate_pass": False, "status": "failed"}
        with mock.patch.object(runner, "run", return_value=result), mock.patch("builtins.print"):
            self.assertEqual(runner.main([str(self.exe), str(self.out)]), 1)


if __name__ == "__main__":
    unittest.main()
