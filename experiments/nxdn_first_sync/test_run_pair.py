from pathlib import Path
import tempfile
import unittest
from unittest import mock
import run_pair

class PairPolicies(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.baseline = self.root/'baseline'; self.baseline.write_bytes(b'baseline')
        self.candidate = self.root/'candidate'; self.candidate.write_bytes(b'candidate')
        self.frozen = self.root/'frozen'; self.frozen.mkdir()
        self.output = self.root/'output'; self.calls = []
    def run_mocked(self, *, baseline_ok=True, promotion=True, drift=False, baseline_changed=False):
        def native(exe, output):
            self.calls.append(exe.name)
            if drift: self.candidate.write_bytes(b'changed')
            return {'status': 'measured', 'measurement_pass': baseline_ok, 'receiver_gate_pass': True}
        def match(*args):
            if baseline_changed: raise ValueError('baseline differs')
        def loader(path):
            ns = ({'SOURCE_FILES': (), 'run': native} if path == run_pair.INNER else
                  {'load_run': lambda path: {}, 'baseline_matches': match,
                   'compare': lambda *a, **kw: {'evidence_valid': True, 'promotion_pass': promotion}})
            return ns, run_pair.digest(path)
        with mock.patch.object(run_pair, 'module', side_effect=loader):
            return run_pair.run(self.baseline, self.candidate, self.output, frozen_baseline_dir=self.frozen)
    def test_pair_order_and_single_runs(self):
        result = self.run_mocked()
        self.assertTrue(result['measurement_pass']); self.assertTrue(result['promotion_pass'])
        self.assertEqual(self.calls, ['baseline', 'candidate'])
    def test_receiver_rejection_is_valid_negative_experiment(self):
        result = self.run_mocked(promotion=False)
        self.assertTrue(result['measurement_pass']); self.assertFalse(result['promotion_pass'])
    def test_baseline_failure_prevents_candidate(self):
        result = self.run_mocked(baseline_ok=False)
        self.assertFalse(result['measurement_pass']); self.assertEqual(self.calls, ['baseline'])
    def test_baseline_reproduction_failure_prevents_candidate(self):
        result = self.run_mocked(baseline_changed=True)
        self.assertFalse(result['measurement_pass']); self.assertEqual(self.calls, ['baseline'])
    def test_input_drift_prevents_candidate(self):
        result = self.run_mocked(drift=True)
        self.assertFalse(result['measurement_pass']); self.assertEqual(self.calls, ['baseline'])
    def test_existing_output_never_overwritten(self):
        self.output.mkdir(); marker=self.output/'keep'; marker.write_text('preserved')
        with self.assertRaises(FileExistsError): self.run_mocked()
        self.assertEqual(marker.read_text(), 'preserved'); self.assertEqual(self.calls, [])
    def test_identical_binary_bytes_rejected(self):
        self.candidate.write_bytes(self.baseline.read_bytes())
        result = self.run_mocked()
        self.assertFalse(result['measurement_pass']); self.assertEqual(self.calls, [])

if __name__ == '__main__': unittest.main()
