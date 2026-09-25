"""Falsify legacy projection and failure retention without native execution."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import prepare
import prepare_build
import run


class RunnerTests(unittest.TestCase):
    def projection_fixture(self):
        old = [{"seq": 0, "kind": "frame_end", "body": "01", "body_positions": [20, 17], "value": 1}]
        new = copy.deepcopy(old)
        new[0]["body_positions"] = [20, 0]
        new[0]["body_calls"] = [
            {"eof_after": 0, "symbol_before": 0, "symbol_after": 1},
            {"eof_after": 1, "symbol_before": 1, "symbol_after": 1}]
        return old, new

    def test_only_unavailable_eof_positions_are_projected(self):
        old, new = self.projection_fixture()
        self.assertTrue(run.anchor_projection(old, new))
        for key in ("body", "value"):
            bad = copy.deepcopy(new); bad[0][key] = "changed"
            self.assertFalse(run.anchor_projection(old, bad))
        self.assertEqual(old[0]["body_positions"], [20, 17])

    def test_completed_or_non_eof_calls_cannot_hide_position_drift(self):
        old, new = self.projection_fixture()
        for field, value in (("eof_after", 0), ("symbol_after", 2)):
            bad = copy.deepcopy(new); bad[0]["body_calls"][1][field] = value
            self.assertFalse(run.anchor_projection(old, bad))
        new[0]["body_positions"][0] = 21
        self.assertFalse(run.anchor_projection(old, new))

    def test_unknown_event_cannot_be_silently_dropped(self):
        old, new = self.projection_fixture()
        new.insert(0, {"seq": 0, "kind": "unknown"})
        self.assertFalse(run.anchor_projection(old, new))

    def test_malformed_projection_is_retained_as_failure(self):
        old, new = self.projection_fixture()
        for key in ("kind", "body_calls", "body_positions"):
            bad = copy.deepcopy(new); del bad[0][key]
            self.assertFalse(run.anchor_projection(old, bad))

    def test_missing_or_repeated_source_seam_is_rejected(self):
        for value in ("none", "twice twice"):
            with self.assertRaises(ValueError):
                prepare_build.replace_one(value, "twice", "new")

    def test_independently_pinned_scch_frame_bytes(self):
        enc = prepare.encoder()
        expected = {False: "e49e9872c987d580c76ba274aca18137767ca9db452a8e6f0a508a156411b4c1",
                    True: "fb1afd6934f61d552131f84a635789fbae9d57f8537527cc9edc59cbeed00137"}
        import hashlib
        for wrong, digest in expected.items():
            data, meta = prepare.scch_vector(enc, wrong)
            self.assertEqual(hashlib.sha256(data).hexdigest(), digest)
            self.assertEqual(meta["computed_crc"], 17)
            self.assertEqual(meta["transmitted_crc"], 81 if wrong else 17)

    def test_timeout_or_invalid_trace_is_retained(self):
        for timeout in (True, False):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                process = subprocess.TimeoutExpired("fake", 60) if timeout else lambda *a, **kw: subprocess.CompletedProcess(a, 0)
                with patch.object(run.subprocess, "run", side_effect=process), \
                        patch.object(run.analyze, "inspect", side_effect=ValueError("invalid trace")):
                    _, result = run.invoke(root / "not-executed.exe", root / "attempt", {"waveform": "w", "chunk": 37},
                        root, {"waveforms": {"w": {"file": "unused"}}}, 1)
                self.assertFalse(result["measurement_pass"])
                self.assertEqual(result, json.loads((root / "attempt/audit.json").read_text()))
                self.assertTrue((root / "attempt/failure.txt").is_file())


if __name__ == "__main__":
    unittest.main()
