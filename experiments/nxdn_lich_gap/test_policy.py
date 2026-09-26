import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess

import prepare
import run_pair


class GateTests(unittest.TestCase):
    def test_consecutive_evidence_contract(self):
        self.assertEqual([r["result"] for r in run_pair.oracle("WPWW")], [0, 0, 0, 2])
        self.assertEqual([r["result"] for r in run_pair.oracle("WPWW", True)], [0, 0, 2, 2])
        self.assertEqual([r["result"] for r in run_pair.oracle("SPW")], [2, 1, 2])
        self.assertEqual([r["result"] for r in run_pair.oracle("WCWW")], [0, 0, 0, 2])
        self.assertEqual([r["result"] for r in run_pair.oracle("SRWW")], [2, -1, 0, 2])

    def test_candidate_patch_is_bounded_and_rejects_drift(self):
        source = prepare.FRAME.read_text()
        result = prepare.candidate(source)
        self.assertEqual(result.count("nxdn_confirm_begin_frame(state);"), 1)
        self.assertEqual(result.count("nxdn_confirm_end_frame(state);"), 1)
        with self.assertRaises(ValueError):
            prepare.candidate(source.replace("nxdn_frame_ctx_init(&ctx);", "changed();"))
        self.assertEqual(prepare.FRAME.read_text(), source)

    def test_independent_polynomial_crc(self):
        # Long division of the augmented information integer, separately from
        # the frozen shift-register encoder. Both channel widths/init states.
        encoder = prepare.load_encoder()
        for payload in range(2):
            for kind in "WSCPUD":
                data, meta = prepare.vector(encoder, payload, kind)
                self.assertEqual(len(data), 192)
                for channel, width, poly in (("sacch", 6, 0x27), ("facch", 12, 0x80F)):
                    info = meta[channel]["information_bits"]
                    value = (int(info, 2) << width) ^ (((1 << width) - 1) << len(info))
                    divisor = (1 << width) | poly
                    while value.bit_length() > width:
                        value ^= divisor << (value.bit_length() - width - 1)
                    self.assertEqual(value, meta[channel]["computed_crc"])

    def test_measurement_rejects_tampering(self):
        # Build an explicit ideal observation solely to test negative mutations
        # of the measurement policy; never used as experimental receiver data.
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            manifest = prepare.prepare(directory)
            rows = []
            for payload in range(2):
                for enabled in range(2):
                    for name, sequence in prepare.SEQUENCES.items():
                        truth = run_pair.oracle(sequence)
                        for step, kind in enumerate(sequence):
                            count = 0 if kind == "R" else 8 if kind in "PUD" else 182
                            events = []
                            if enabled and kind in "WSC":
                                meta = manifest["vectors"][f"{payload}-{kind}.dibits"]
                                for channel, part, label in ((1, 0, "sacch"), (2, 1, "facch"), (2, 2, "facch")):
                                    c = meta[label]
                                    events.append({"channel": channel, "part": part, "computed": c["computed_crc"],
                                                   "received": c["transmitted_crc"], "bits": c["information_bits"],
                                                   "soft_pass": int(c["crc_expected_pass"]), "fallback": int(not c["crc_expected_pass"])})
                            hold = int(kind in "WSC" and truth[step]["confirmed"] != 0)
                            row = {"payload": payload, "observed": enabled, "sequence": name, "step": step,
                                   "kind": kind, "consumed": count, "events": events, "errors": 0,
                                   "voice": 0, "carrier": int(kind not in "PUD"), "clock_changed": hold,
                                   "mono_changed": hold, "content": 0, **truth[step]}
                            row["read_dibits"] = "" if kind == "R" else "".join(map(str, (directory / f"{payload}-{kind}.dibits").read_bytes()[10:10 + count]))
                            rows.append(row)
            self.assertTrue(run_pair.check_rows(rows, manifest, directory, "candidate")["measurement_pass"])
            # A real baseline preventing the proposed bridge is valid H0 data.
            hypothetical_h0 = run_pair.check_rows(rows, manifest, directory, "baseline")
            self.assertTrue(hypothetical_h0["measurement_pass"])
            self.assertTrue(hypothetical_h0["predicted_transition_deviations"])
            # A poor candidate that follows the old policy is valid negative data.
            poor = copy.deepcopy(rows)
            for row in poor:
                predicted = run_pair.oracle(prepare.SEQUENCES[row["sequence"]], True)[row["step"]]
                row.update(predicted)
                hold = int(row["kind"] in "WSC" and row["confirmed"] != 0)
                row["clock_changed"] = row["mono_changed"] = hold
            poor_report = run_pair.check_rows(poor, manifest, directory, "candidate")
            self.assertTrue(poor_report["measurement_pass"])
            self.assertTrue(poor_report["contract_deviations"])
            # Full runner: keep six proposed baseline bridges, break an unrelated
            # strong-control verdict. Valid data must still fail progression.
            broken_control = copy.deepcopy(poor)
            for row in broken_control:
                if row["sequence"] == "adjacent_strong" and row["step"] == 1:
                    row["result"] = 1
            baseline_report = run_pair.check_rows(broken_control, manifest, directory, "baseline")
            candidate_report = run_pair.check_rows(rows, manifest, directory, "candidate")
            self.assertTrue(baseline_report["measurement_pass"])
            first = directory / "dummy-baseline.exe"
            second = directory / "dummy-candidate.exe"
            first.write_bytes(b"framework dummy; never executed")
            second.write_bytes(b"framework dummy; never executed")
            with patch.object(run_pair, "execute_role", side_effect=[(broken_control, baseline_report), (rows, candidate_report)]):
                full = run_pair.run(first, second, directory, directory / "negative-pair")
            self.assertTrue(full["measurement_pass"])
            self.assertEqual(full["baseline_bridges"], 6)
            self.assertFalse(full["progression_pass"])
            self.assertNotIn("report.json", full["files"])
            for name, digest in full["files"].items():
                self.assertEqual(prepare.sha(directory / "negative-pair" / name), digest)
            for field, value in (("voice", 1), ("errors", 1), ("consumed", 8), ("confirmed", 1),
                                 ("read_dibits", ""), ("clock_changed", 1)):
                bad = copy.deepcopy(rows)
                bad[0][field] = value
                with self.subTest(field=field):
                    self.assertFalse(run_pair.check_rows(bad, manifest, directory, "candidate")["measurement_pass"])
            bad = copy.deepcopy(rows)
            next(r for r in bad if r["events"])["events"][0]["bits"] = "0" * 26
            self.assertFalse(run_pair.check_rows(bad, manifest, directory, "candidate")["measurement_pass"])
            self.assertFalse(run_pair.check_rows(rows[1:], manifest, directory, "candidate")["measurement_pass"])
            self.assertFalse(run_pair.check_rows(rows + [rows[0]], manifest, directory, "candidate")["measurement_pass"])

    def test_failed_execution_is_classified(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            binary = directory / "not-executed"
            def fail(*args, **kwargs):
                kwargs["stdout"].write(b"partial output")
                kwargs["stderr"].write(b"retained diagnostic")
                raise subprocess.TimeoutExpired("controlled test", 60)
            with patch.object(run_pair.subprocess, "run", side_effect=fail):
                rows, report = run_pair.execute_role(binary, directory, "baseline", {})
            self.assertFalse(report["measurement_pass"])
            self.assertEqual(report["exception"], "TimeoutExpired")
            self.assertEqual(report["phase"], "launch")
            self.assertEqual((directory / "baseline.jsonl").read_bytes(), b"partial output")
            self.assertEqual((directory / "baseline.stderr").read_bytes(), b"retained diagnostic")

    def test_malformed_output_and_missing_fields_are_classified(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            for payload, phase in ((b"broken\n", "parse"), (b"{}\n", "inspect")):
                def emit(*args, **kwargs):
                    kwargs["stdout"].write(payload)
                    return subprocess.CompletedProcess([], 0)
                with patch.object(run_pair.subprocess, "run", side_effect=emit):
                    rows, report = run_pair.execute_role(directory / "not-executed", directory, "baseline", {})
                self.assertEqual(report["exit_code"], 0)
                self.assertEqual(report["phase"], phase)
                self.assertFalse(report["measurement_pass"])


if __name__ == "__main__":
    unittest.main()
