"""Independent classification controls for the fixed three-run TSan gate.

Mocked process results test the checker, not ThreadSanitizer itself. Real probe
executions remain a separate required CI negative control. All assertions stay
active under optimized Python through unittest's explicit check methods.
"""
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import check_tsan_probe as checker


DIAGNOSTIC = b'WARNING: ThreadSanitizer: data race\n  Write of size 4 at a controlled address\n'


def completed(index, *, code=66, diagnostic=True):
    stdout = b'probe stdout ' + str(index).encode('ascii') + b'\x00\xff\n'
    stderr = (DIAGNOSTIC if diagnostic else b'FATAL: ThreadSanitizer: unsupported runtime\n')
    stderr += b'probe stderr ' + str(index).encode('ascii') + b'\x00\xfe\n'
    return subprocess.CompletedProcess(['instrumented-probe'], code, stdout, stderr)


class ProbeClassificationTests(unittest.TestCase):
    def invoke(self, outcomes, *, succeeds):
        """Run once with exactly three predetermined outcomes, no retry oracle."""
        self.assertEqual(len(outcomes), 3)
        executable = Path('independent-instrumented-probe')
        captured_out = io.BytesIO()
        captured_err = io.BytesIO()
        stdout = io.TextIOWrapper(captured_out, encoding='utf-8')
        stderr = io.TextIOWrapper(captured_err, encoding='utf-8')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'nested' / 'evidence'
            with patch.object(checker.subprocess, 'run', side_effect=outcomes) as run, \
                    patch('sys.stdout', stdout), patch('sys.stderr', stderr):
                if succeeds:
                    self.assertIsNone(checker.check_probes(executable, output_directory=output))
                else:
                    with self.assertRaises(RuntimeError) as failure:
                        checker.check_probes(executable, output_directory=output)
                    self.assertTrue(str(failure.exception))
            # Check before examining files: a failure must not short-circuit or
            # adaptively add attempts to replace a bad predetermined invocation.
            self.assertEqual(run.call_count, 3)
            for call in run.call_args_list:
                self.assertEqual(call.args, ([str(executable)],))
                self.assertIs(call.kwargs.get('capture_output'), True)
                self.assertGreater(call.kwargs.get('timeout', 0), 0)
                self.assertLessEqual(call.kwargs['timeout'], 30)
            expected_report = []
            for index, outcome in enumerate(outcomes, 1):
                if isinstance(outcome, subprocess.CompletedProcess):
                    expected_stdout, expected_stderr = outcome.stdout, outcome.stderr
                    returncode, error = outcome.returncode, None
                elif isinstance(outcome, subprocess.TimeoutExpired):
                    expected_stdout, expected_stderr = outcome.output, outcome.stderr
                    returncode, error = None, 'timeout'
                else:
                    self.assertIsInstance(outcome, OSError)
                    expected_stdout, expected_stderr = b'', str(outcome).encode('utf-8')
                    returncode, error = None, type(outcome).__name__
                self.assertEqual((output / f'tsan-probe-{index}.stdout').read_bytes(), expected_stdout or b'')
                self.assertEqual((output / f'tsan-probe-{index}.stderr').read_bytes(), expected_stderr or b'')
                diagnosed = b'WARNING: ThreadSanitizer: data race' in (expected_stderr or b'')
                passed = error is None and returncode == 66 and diagnosed
                expected_report.append(dict(invocation=index, returncode=returncode, error=error,
                                            race_diagnostic=diagnosed, passed=passed))
            self.assertEqual(json.loads((output / 'tsan-probe-results.json').read_bytes()), expected_report)
            stdout.flush()
            stderr.flush()
            transcript = captured_out.getvalue() + captured_err.getvalue()
            for result in expected_report:
                label = 'EXPECTED' if result['passed'] else 'FAILED'
                marker = f"{label} CONTROL {result['invocation']}/3".encode('ascii')
                self.assertIn(b'BEGIN ' + marker, transcript)
                self.assertIn(b'END ' + marker, transcript)
        stdout.close()
        stderr.close()
        return transcript

    def test_run_count_is_fixed_three(self):
        self.assertEqual(checker.PROBE_RUNS, 3)
        self.invoke([completed(1), completed(2), completed(3)], succeeds=True)

    def test_missing_race_at_each_position_fails_and_preserves_all_attempts(self):
        for bad_index in range(3):
            with self.subTest(bad_index=bad_index):
                outputs = [completed(1), completed(2), completed(3)]
                outputs[bad_index] = completed(bad_index + 1, code=0, diagnostic=False)
                self.invoke(outputs, succeeds=False)

    def test_last_failed_probe_cannot_be_hidden_by_two_successes(self):
        self.invoke([completed(1), completed(2), completed(3, code=0, diagnostic=False)], succeeds=False)

    def test_exit_66_without_real_diagnostic_is_not_an_instrumentation_pass(self):
        for noise in (b'', b'FATAL: ThreadSanitizer: unexpected memory mapping\n',
                      b'ERROR: test deliberately returned 66\n',
                      b'WARNING: ThreadSanitizer: lock-order-inversion\n',
                      b'ThreadSanitizer: data race\n'):
            with self.subTest(noise=noise):
                bad = completed(2)
                bad.stderr = noise
                self.invoke([completed(1), bad, completed(3)], succeeds=False)

    def test_race_diagnostic_with_wrong_exit_code_is_not_a_pass(self):
        for code in (0, 1, -11, 67):
            with self.subTest(code=code):
                self.invoke([completed(1), completed(2, code=code), completed(3)], succeeds=False)

    def test_diagnostic_on_stdout_does_not_replace_stderr_runtime_report(self):
        bad = completed(2, diagnostic=False)
        bad.stdout += DIAGNOSTIC
        self.invoke([completed(1), bad, completed(3)], succeeds=False)

    def test_all_three_failures_are_attempted_and_preserved(self):
        self.invoke([completed(1, code=0, diagnostic=False), completed(2, code=1, diagnostic=False),
                     completed(3, diagnostic=False)], succeeds=False)

    def test_timeout_preserves_partial_binary_outputs_and_does_not_short_circuit(self):
        for index in range(3):
            with self.subTest(index=index):
                timeout = subprocess.TimeoutExpired(['instrumented-probe'], 30,
                                                    output=b'partial stdout\x00\xff\n',
                                                    stderr=DIAGNOSTIC + b'partial stderr\x00\xfe\n')
                outputs = [completed(1), completed(2), completed(3)]
                outputs[index] = timeout
                self.invoke(outputs, succeeds=False)

    def test_timeout_without_captured_bytes_still_writes_explicit_empty_files(self):
        timeout = subprocess.TimeoutExpired(['instrumented-probe'], 30)
        self.invoke([timeout, completed(2), completed(3)], succeeds=False)

    def test_launch_errors_are_reported_without_hiding_remaining_invocations(self):
        self.invoke([FileNotFoundError('missing instrumented executable'), completed(2),
                     OSError('controlled process launch failure')], succeeds=False)


if __name__ == '__main__':
    unittest.main()
