"""Check one-attempt retention and declared option forwarding without a receiver."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import run

CASE = {'id': 'cold_fast-c37', 'configuration': 'cold_fast', 'waveform': 'cold', 'chunk': 37, 'fast': 1}
MANIFEST = {'waveforms': {'cold': {'file': 'wave.f32le'}}}

class RunTests(unittest.TestCase):
    def test_existing_identity_is_not_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); attempt = root / 'attempt'; attempt.mkdir()
            with patch.object(run.subprocess, 'run') as process:
                with self.assertRaises(FileExistsError):
                    run.invoke(root / 'unused.exe', attempt, CASE, root, MANIFEST, 1)
                process.assert_not_called()

    def test_fast_option_is_forwarded_and_environment_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); attempt = root / 'attempt'
            def native(args, **kw):
                self.assertEqual(args[2:5], ['1', '37', '1'])
                self.assertFalse(kw.get('shell', False))
                self.assertFalse(any(k.upper().startswith('DSD_') for k in kw['env']))
                self.assertEqual(kw['timeout'], 60)
                return subprocess.CompletedProcess(args, 0)
            with patch.dict(run.os.environ, {'DSD_OVERRIDE': 'bad', 'dsd_lower': 'bad'}), \
                 patch.object(run.subprocess, 'run', side_effect=native) as process, \
                 patch.object(run.analyze, 'inspect', return_value={'measurement_pass': True}):
                result = run.invoke(root / 'unused.exe', attempt, CASE, root, MANIFEST, 1)
                self.assertEqual(process.call_count, 1)
                self.assertTrue(result['measurement_pass'])

    def test_timeout_preserves_partial_bytes_and_never_retries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); attempt = root / 'attempt'
            def timeout(args, **kw):
                kw['stdout'].write(b'{"partial":'); kw['stderr'].write(b'diagnostic')
                raise subprocess.TimeoutExpired(args, 60)
            with patch.object(run.subprocess, 'run', side_effect=timeout) as process:
                result = run.invoke(root / 'unused.exe', attempt, CASE, root, MANIFEST, 0)
                self.assertEqual(process.call_count, 1)
            self.assertEqual(result['exception'], 'TimeoutExpired')
            self.assertEqual((attempt / 'events.jsonl').read_bytes(), b'{"partial":')
            self.assertEqual((attempt / 'stderr.txt').read_bytes(), b'diagnostic')

    def test_checker_exception_cannot_erase_native_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); attempt = root / 'attempt'
            with patch.object(run.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as process, \
                 patch.object(run.analyze, 'inspect', side_effect=ValueError('bad evidence')):
                result = run.invoke(root / 'unused.exe', attempt, CASE, root, MANIFEST, 0)
                self.assertEqual(process.call_count, 1)
            self.assertFalse(result['measurement_pass'])
            self.assertEqual(json.loads((attempt / 'process.json').read_bytes()), {'exit_code': 0})
            self.assertEqual(result['detail'], 'bad evidence')

    def test_native_failure_cannot_become_measurement_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(run.subprocess, 'run', return_value=subprocess.CompletedProcess([], 5)), \
                 patch.object(run.analyze, 'inspect', return_value={'measurement_pass': True}):
                result = run.invoke(root / 'unused.exe', root / 'attempt', CASE, root, MANIFEST, 0)
            self.assertEqual(result['exit_code'], 5)
            self.assertFalse(result['measurement_pass'])

    def test_changed_source_or_copied_binary_blocks_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / 'source'; source.write_bytes(b'original')
            group = {str(source): run.prepare.sha(source)}; source.write_bytes(b'changed')
            with patch.object(run, 'invoke') as invoke:
                with self.assertRaises(ValueError):
                    run.checked_invoke(root / 'unused.exe', root / 'attempt', CASE, root, MANIFEST, 0, (group,))
                invoke.assert_not_called()

    def test_ambiguous_json_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'events'
            for raw in ('{"id":1,"id":2}\n', '{"value":NaN}\n', '{"value":Infinity}\n', '{"partial":'):
                p.write_text(raw, encoding='utf-8')
                with self.assertRaises(ValueError): run.read_rows(p)

if __name__ == '__main__': unittest.main()
