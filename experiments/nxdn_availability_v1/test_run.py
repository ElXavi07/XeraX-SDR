"""Exercise unchanged failure-retention controls against the new runner."""
import hashlib
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import json
import tempfile
import xml.etree.ElementTree as ET
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

class NativeUnitEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='nxdn-availability-unit-evidence-')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.xml = ET.Element('testsuite', tests='8', failures='0', errors='0', skipped='0', disabled='0')
        for name in run.NATIVE_TEST_NAMES:
            ET.SubElement(self.xml, 'testcase', name=name, status='run')
        self.status = {'all_pass':True, 'test_count':8, 'exit_code':0,
                       'test_names':list(run.NATIVE_TEST_NAMES), 'native_receiver_invocations':0}
        self.write_xml()
        for name in ('native-unit.log', 'native-unit-1.log'):
            self.path(name).write_bytes(b'All eight synthetic unit contracts passed.\n')

    def path(self, name):
        return self.folder / ('nxdn-availability-v1-' + name)

    def write_status(self):
        raw = (json.dumps(self.status) + '\n').encode()
        for name in ('native-unit-status.json', 'native-unit-status-1.json'):
            self.path(name).write_bytes(raw)

    def write_xml(self):
        raw = ET.tostring(self.xml, encoding='utf-8')
        self.path('native-unit-1.xml').write_bytes(raw)
        self.status['xml_sha256'] = hashlib.sha256(raw).hexdigest()
        self.write_status()

    def test_exact_eight_passes_return_all_five_evidence_hashes(self):
        files = run.validate_native_units(self.folder)
        self.assertEqual(set(files), {str(self.path(n).resolve()) for n in run.NATIVE_UNIT_FILES})
        self.assertEqual(len(files), 5)
        for path, digest in files.items():
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), digest)

    def test_xml_bytes_changed_without_new_digest_rejected(self):
        with self.path('native-unit-1.xml').open('ab') as stream: stream.write(b' ')
        with self.assertRaisesRegex(ValueError, 'XML hash'): run.validate_native_units(self.folder)

    def test_validated_xml_tamper_blocks_launch_before_invocation(self):
        identities = run.validate_native_units(self.folder)
        with self.path('native-unit-1.xml').open('ab') as stream: stream.write(b'changed')
        with patch.object(run, 'invoke') as invoke:
            with self.assertRaisesRegex(ValueError, 'Identity changed'):
                run.checked_invoke(Path('never.exe'), self.folder/'never-run', {},
                                   self.folder, {}, 0, (identities,))
            invoke.assert_not_called()
        self.assertFalse((self.folder/'never-run').exists())

    def test_rehashed_xml_failure_is_not_a_pass(self):
        ET.SubElement(self.xml[0], 'failure', message='assertion failed')
        self.write_xml()
        with self.assertRaisesRegex(ValueError, 'did not pass'): run.validate_native_units(self.folder)

    def test_rehashed_xml_error_or_skip_is_not_a_pass(self):
        for tag in ('error', 'skipped'):
            with self.subTest(tag=tag):
                node = ET.SubElement(self.xml[0], tag)
                self.write_xml()
                with self.assertRaises(ValueError): run.validate_native_units(self.folder)
                self.xml[0].remove(node)

    def test_suite_failure_totals_are_checked(self):
        for key in ('failures', 'errors', 'disabled', 'skipped'):
            with self.subTest(key=key):
                self.xml.set(key, '1'); self.write_xml()
                with self.assertRaises(ValueError): run.validate_native_units(self.folder)
                self.xml.set(key, '0')

    def test_case_that_did_not_run_rejected(self):
        self.xml[0].set('status', 'notrun'); self.write_xml()
        with self.assertRaisesRegex(ValueError, 'not executed'): run.validate_native_units(self.folder)

    def test_missing_duplicate_extra_or_wrong_xml_name_rejected(self):
        original = ET.tostring(self.xml)
        for mutation in ('missing', 'duplicate', 'extra', 'nested_extra', 'wrong', 'reordered'):
            with self.subTest(mutation=mutation):
                self.xml = ET.fromstring(original)
                if mutation == 'missing': self.xml.remove(self.xml[0])
                elif mutation == 'duplicate': self.xml[1].set('name', self.xml[0].get('name'))
                elif mutation == 'extra': ET.SubElement(self.xml, 'testcase', name='unregistered', status='run')
                elif mutation == 'nested_extra':
                    nested = ET.SubElement(self.xml, 'testsuite')
                    ET.SubElement(nested, 'testcase', name='hidden-extra', status='run')
                elif mutation == 'wrong': self.xml[0].set('name', 'unregistered')
                else:
                    first = self.xml[0]; self.xml.remove(first); self.xml.append(first)
                self.write_xml()
                with self.assertRaisesRegex(ValueError, 'cases differ'): run.validate_native_units(self.folder)

    def test_json_count_exit_or_receiver_invocation_cannot_claim_pass(self):
        original = dict(self.status)
        for key, bad in (('test_count',9), ('test_count',True), ('exit_code',1),
                         ('native_receiver_invocations',1), ('all_pass',1)):
            with self.subTest(key=key, bad=bad):
                self.status = dict(original); self.status[key] = bad; self.write_status()
                with self.assertRaises(ValueError): run.validate_native_units(self.folder)

    def test_json_names_must_be_exact_eight(self):
        self.status['test_names'][0] = 'unregistered'; self.write_status()
        with self.assertRaisesRegex(ValueError, 'status names'): run.validate_native_units(self.folder)

    def test_final_status_cannot_disagree_with_saved_attempt(self):
        self.path('native-unit-status-1.json').write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError, 'status differs'): run.validate_native_units(self.folder)

    def test_final_log_cannot_disagree_with_saved_attempt(self):
        self.path('native-unit-1.log').write_bytes(b'Failed test')
        with self.assertRaisesRegex(ValueError, 'log differs'): run.validate_native_units(self.folder)

    def test_missing_saved_xml_rejected(self):
        self.path('native-unit-1.xml').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing'): run.validate_native_units(self.folder)

    def test_malformed_xml_with_updated_hash_rejected(self):
        raw = b'<testsuite'
        self.path('native-unit-1.xml').write_bytes(raw)
        self.status['xml_sha256'] = hashlib.sha256(raw).hexdigest(); self.write_status()
        with self.assertRaisesRegex(ValueError, 'Malformed'): run.validate_native_units(self.folder)

    def test_wrong_suite_count_rejected(self):
        self.xml.set('tests', '9'); self.write_xml()
        with self.assertRaisesRegex(ValueError, 'suite differs'): run.validate_native_units(self.folder)

    def test_completed_auditor_failures_are_snapshotted_without_live_run_files(self):
        expected = {'build-audit-first.py', 'build-audit-first.log', 'build-audit-second.py',
                    'build-audit-second.log', 'build-audit-third.py', 'build-audit-third.log',
                    'build-audit-final.log', 'build-audit-pass.log', 'observer-prototype-failure.c',
                    'prepare-build-initial.py', 'configure-1.log', 'build-1.log',
                    'framework-preflight-old.log', 'framework-evidence-normal.log'}
        for name in expected: self.path(name).write_bytes(b'retained preflight evidence')
        self.path('receiver-run.log').write_bytes(b'not a completed preflight')
        self.path('build-audit-directory').mkdir()
        (self.folder / 'nxdn-other-build-audit-first.py').write_bytes(b'other study')
        found = run.completed_preflight_files(self.folder)
        self.assertEqual(set(found), {self.path(n) for n in expected})
        self.assertEqual(len(found), len(expected))

if __name__ == '__main__': unittest.main()
