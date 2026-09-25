"""Counterexamples for the progression gate; these do not execute a native decoder."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import analyze
import prepare
import run_pair


def frame(ordinal, kind, begin_confirmed, begin_streak, result, confirmed, streak):
    return {"source": {"ordinal": ordinal, "kind": kind}, "channel_truth": True,
            "begin": {"seq": ordinal * 10, "confirmed": begin_confirmed, "streak": begin_streak},
            "end": {"seq": ordinal * 10 + 5, "value": result, "confirmed": confirmed, "streak": streak},
            "dispatch": {"end": {"verdict": int(result == 0)}}}


def pair():
    before = [frame(2, "W", 0, 0, 0, 0, 1), frame(3, "P", 0, 1, 0, 0, 1),
              frame(4, "W", 0, 1, 2, 1, 2), frame(5, "W", 1, 2, 2, 1, 3)]
    after = [frame(2, "W", 0, 0, 0, 0, 1), frame(3, "P", 0, 1, 0, 0, 0),
             frame(4, "W", 0, 0, 0, 0, 1), frame(5, "W", 0, 1, 2, 1, 2)]
    return {"p0-parity_gap-f1-c37": {"baseline": {"frames": before, "resets": [], "reset_completed": True},
                                     "candidate": {"frames": after, "resets": [], "reset_completed": True}}}


class Policy(unittest.TestCase):
    def test_actual_correction_and_nonexposure(self):
        self.assertTrue(analyze.quality(pair())["progression_pass"])
        data = pair()
        data[next(iter(data))]["baseline"]["frames"].pop(1)
        self.assertFalse(analyze.quality(data)["progression_pass"])

    def test_skipped_candidate_or_late_reset_not_correction(self):
        for mutation in ("skip", "reset", "incidental", "no_final"):
            data = pair()
            candidate = data[next(iter(data))]["candidate"]
            if mutation == "skip":
                candidate["frames"].pop(2)
            elif mutation == "reset":
                candidate["resets"].append({"begin": {"seq": 47}})
            elif mutation == "incidental":
                other = copy.deepcopy(candidate["frames"][2]); other["source"] = None
                candidate["frames"].insert(3, other)
            else:
                candidate["frames"].pop()
            self.assertFalse(analyze.quality(data)["progression_pass"], mutation)

    def test_empty_controls_do_not_pass(self):
        data = pair()
        data["p0-clean_weak-f1-c37"] = {r: {"frames": [], "resets": [], "reset_completed": True} for r in ("baseline", "candidate")}
        self.assertFalse(analyze.quality(data)["progression_pass"])

    def test_baseline_false_proof_blocks_progression(self):
        data = pair()
        data["p0-bad_crc-f1-c37"] = {r: {"frames": [frame(0, "C", 0, 0, 2, 1, 0)], "resets": [], "reset_completed": True}
                                     for r in ("baseline", "candidate")}
        self.assertFalse(analyze.quality(data)["progression_pass"])

    def test_neutrality_keeps_outcomes(self):
        a = [{"kind": "frame_end", "seq": 2, "pops": 12, "frontier": 12, "body": "0123", "value": 2}]
        b = copy.deepcopy(a); b[0].update(seq=0, pops=0, frontier=0)
        self.assertEqual(analyze.semantic(a), analyze.semantic(b))
        b[0]["value"] = 0
        self.assertNotEqual(analyze.semantic(a), analyze.semantic(b))

    def test_false_ordinal_or_truncated_body_cannot_match(self):
        waveform = {"frames": [{"ordinal": 0, "kind": "P", "vector": "p", "start": 640}]}
        body = "0" * 8
        begin = {"eof": 0, "sync": 28, "frontier": 840}
        end = {"eof": 0, "frontier": 1000, "body_count": 8, "body": body, "body_positions": list(range(860, 1001, 20))}
        self.assertEqual(analyze.source_identity(begin, end, waveform, {"p": bytes(192)})["ordinal"], 0)
        begin["frontier"] = 2000
        self.assertIsNone(analyze.source_identity(begin, end, waveform, {"p": bytes(192)}))
        begin["frontier"] = 840; end["eof"] = 1
        self.assertIsNone(analyze.source_identity(begin, end, waveform, {"p": bytes(192)}))

    def test_timeout_is_retained(self):
        import subprocess
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = {"waveforms": {"w": {"file": "wave.f32le"}}}
            case = {"waveform": "w", "fast": 0, "chunk": 37}
            with patch("run_pair.subprocess.run", side_effect=subprocess.TimeoutExpired("decoder", 60)):
                _, result = run_pair.execute(root / "absent", root / "attempt", case, root, manifest, 1)
            self.assertFalse(result["measurement_pass"])
            self.assertTrue((root / "attempt/failure.txt").is_file())
            self.assertEqual(json.loads((root / "attempt/audit.json").read_text())["exception"], "TimeoutExpired")

    def test_registered_matrix_and_independent_crc(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest = prepare.prepare(Path(temp))
            self.assertEqual(len(manifest["cases"]), 64)
            self.assertEqual(len(manifest["waveforms"]), 16)
            for vector in manifest["vectors"]["vectors"].values():
                for channel in ("sacch", "facch"):
                    v = vector[channel]
                    self.assertEqual(analyze.crc(v["information_bits"], v["crc_width"]), v["computed_crc"])


if __name__ == "__main__":
    unittest.main()
