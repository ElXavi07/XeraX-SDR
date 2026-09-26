"""Exercise unchanged failure-retention controls against the new runner."""
import hashlib
import importlib.util
from pathlib import Path
import unittest
import run

path = Path(__file__).resolve().parents[1] / 'nxdn_clear_routing_v1/test_run.py'
if hashlib.sha256(path.read_bytes()).hexdigest() != '3367010532804e875ab854477b05740df57095d82992fb7799c64234966752ac':
    raise ValueError('Frozen failure-retention tests changed')
spec = importlib.util.spec_from_file_location('boundary_runner_contract', path)
contract = importlib.util.module_from_spec(spec); spec.loader.exec_module(contract)
contract.run = run
RetainedFailureControls = contract.RunTests

class IdentityTests(unittest.TestCase):
    def test_conflicting_history_hash_cannot_be_overwritten(self):
        target = {'unchanged': 'first'}
        with self.assertRaises(ValueError): run.merge_identity(target, {'unchanged': 'second'})
        self.assertEqual(target, {'unchanged': 'first'})

if __name__ == '__main__': unittest.main()
