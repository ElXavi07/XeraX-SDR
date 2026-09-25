"""Black-box executable and corrupted-evidence tests; not performance trials."""
import copy
import csv
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from observe_latency import analyze, COLUMNS


def timeline_fixture():
    """Deterministic one-credit timeline; no executable or clock is consulted."""
    rows = []
    for index in range(100):
        due = index * 10000
        rows.append({'kind': 'append', 'index': index, 'first_sample': (30 + index) * 30720,
                     'end_sample': (31 + index) * 30720, 'due_us': due, 'wake_us': due + 1,
                     'begin_us': due + 2, 'end_us': due + 3, 'verified_us': '', 'released_us': '',
                     'status': 0, 'verification': 'not_applicable', 'release_kind': 'not_applicable'})
    for index in range(4):
        due = index * 250000
        end = (31 + index * 25) * 30720
        rows.append({'kind': 'snapshot', 'index': index, 'first_sample': end - 768000,
                     'end_sample': end, 'due_us': due, 'wake_us': due + 5,
                     'begin_us': due + 10, 'end_us': due + 100, 'verified_us': due + 150,
                     'released_us': due + 250007 if index < 3 else due + 151,
                     'status': 0, 'verification': 'ok', 'release_kind': 'tick' if index < 3 else 'shutdown'})
    summary = {'schema': 2, 'complete': True, 'trace_written': True, 'trace_error': None,
               'variant': 'whole', 'format': 'cf32', 'injection': 'none', 'seconds': 1,
               'snapshot_hz': 4, 'hold_ms': 100, 'sample_rate_hz': 3072000, 'block_samples': 30720,
               'snapshot_samples': 768000, 'payload_bytes': 15 * 1024 * 1024,
               'input_vector_bytes': 30720 * 8, 'outstanding_credits': 0, 'failures': [],
               'appends': 100, 'snapshot_attempts': 4}
    return rows, summary


class ObservationContractTests(unittest.TestCase):
    """Fast negative controls using synthetic evidence, including under python -O."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='xerax-observation-contract-')
        self.addCleanup(self.temp.cleanup)
        self.trace = Path(self.temp.name) / 'observations.csv'

    def inspect(self, rows, summary, **kwargs):
        with self.trace.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        return analyze(self.trace, summary, **kwargs)

    def test_deterministic_hold_and_shutdown_semantics(self):
        rows, summary = timeline_fixture()
        result = self.inspect(rows, summary)
        self.assertTrue(result['performance_eligible'])
        self.assertEqual(result['accepted_verified_snapshots'], 4)
        self.assertEqual(result['shutdown_censored_holds'], 1)
        self.assertEqual(result['observed_post_verification_hold_us'],
                         {'n': 3, 'p50': 249857, 'p95': 249857, 'p99': 249857, 'max': 249857})
        rows[100]['released_us'] = rows[100]['verified_us'] + 99999
        with self.assertRaisesRegex(ValueError, 'minimum hold'):
            self.inspect(rows, summary)

    def test_overlapping_accepted_leases_are_rejected(self):
        rows, summary = timeline_fixture()
        rows[100]['released_us'] = rows[101]['begin_us'] + 1
        with self.assertRaisesRegex(ValueError, 'single ownership credit'):
            self.inspect(rows, summary)

    def test_multiple_or_nonfinal_shutdown_releases_are_rejected(self):
        rows, summary = timeline_fixture()
        rows[100]['release_kind'] = 'shutdown'
        with self.assertRaisesRegex(ValueError, 'Multiple shutdown'):
            self.inspect(rows, summary)
        rows[103]['release_kind'] = 'failure'
        summary.update(complete=False, failures=[{'message': 'synthetic final failure'}])
        with self.assertRaisesRegex(ValueError, 'not the final owned lease'):
            self.inspect(rows, summary, allow_failure=True)

    def test_shutdown_cannot_precede_later_busy_observations(self):
        rows, summary = timeline_fixture()
        summary['hold_ms'] = 10000
        rows[100].update(release_kind='shutdown', released_us=200)
        for row in rows[101:]:
            row.update(status=11, verification='not_applicable', verified_us='', released_us='',
                       release_kind='not_applicable')
        with self.assertRaisesRegex(ValueError, 'predates the final consumer observation'):
            self.inspect(rows, summary)
        rows[100]['released_us'] = rows[-1]['end_us'] + 1
        result = self.inspect(rows, summary)
        self.assertEqual(result['accepted_verified_snapshots'], 1)
        self.assertEqual(result['snapshot_status_counts'], {'0': 1, '11': 3})
        self.assertEqual(result['shutdown_censored_holds'], 1)

    def test_impossible_source_intervals_are_rejected(self):
        for mutation in ('misaligned', 'before_prefill', 'future', 'regression'):
            with self.subTest(mutation=mutation):
                rows, summary = timeline_fixture()
                index = 101 if mutation == 'regression' else 100
                row = rows[index]
                if mutation == 'misaligned': row['end_sample'] += 1
                elif mutation == 'before_prefill': row['end_sample'] = 29 * 30720
                elif mutation == 'future': row['end_sample'] = 32 * 30720
                else: row['end_sample'] = 30 * 30720
                row['first_sample'] = row['end_sample'] - 768000
                with self.assertRaisesRegex(ValueError, 'source frontier'):
                    self.inspect(rows, summary)

    def test_rejected_append_does_not_publish_a_frontier(self):
        rows, summary = timeline_fixture()
        appends = rows[:1]
        appends[0]['status'] = 8
        snapshots = rows[100:101]
        snapshots[0].update(verification='aborted', release_kind='failure', released_us=151)
        summary.update(complete=False, injection='verify-exception', appends=1, snapshot_attempts=1,
                       failures=[{'message': 'synthetic rejected input'}])
        with self.assertRaisesRegex(ValueError, 'exceeds completed input'):
            self.inspect(appends + snapshots, summary, allow_failure=True)

    def test_aborted_verification_preserves_failed_diagnostics(self):
        rows, summary = timeline_fixture()
        rows = rows[:101]
        rows[-1].update(verification='aborted', released_us=151, release_kind='failure')
        summary.update(complete=False, injection='verify-exception', snapshot_attempts=1,
                       failures=[{'message': 'synthetic verifier exception'}])
        result = self.inspect(rows, summary, allow_failure=True)
        self.assertFalse(result['performance_eligible'])
        self.assertEqual(result['accepted_verified_snapshots'], 0)
        self.assertEqual(result['snapshot_status_counts'], {'0': 1})
        with self.assertRaisesRegex(ValueError, 'not a performance result'):
            self.inspect(rows, summary)
        rows[-1]['release_kind'] = 'tick'
        with self.assertRaisesRegex(ValueError, 'failure release'):
            self.inspect(rows, summary, allow_failure=True)
        rows[-1]['release_kind'] = 'failure'
        rows[-1]['verified_us'] = ''
        with self.assertRaisesRegex(ValueError, 'verification timing'):
            self.inspect(rows, summary, allow_failure=True)

    def test_invariant_failure_after_verification_is_not_performance_evidence(self):
        rows, summary = timeline_fixture()
        rows = rows[:101]
        rows[-1].update(released_us=151, release_kind='failure')
        summary.update(complete=False, injection='overcommit', snapshot_attempts=1,
                       failures=[{'message': 'synthetic single-slot invariant failure'}])
        result = self.inspect(rows, summary, allow_failure=True)
        self.assertFalse(result['performance_eligible'])
        self.assertEqual(result['accepted_verified_snapshots'], 1)

    def test_signed_offsets_and_frontier_rounding_tolerance(self):
        rows, summary = timeline_fixture()
        rows[0]['end_us'] = rows[100]['begin_us'] + .001
        for row in rows:
            for field in ('wake_us', 'begin_us', 'end_us', 'verified_us', 'released_us'):
                if row[field] != '': row[field] -= 1000000
        result = self.inspect(rows, summary)
        self.assertTrue(result['performance_eligible'])
        self.assertGreater(result['producer_early_wakes'], 0)
        rows[0]['end_us'] += .1
        with self.assertRaisesRegex(ValueError, 'exceeds completed input'):
            self.inspect(rows, summary)


class ObservedHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        value = os.environ.get('XERAX_OBSERVED_EXE')
        if not value:
            raise RuntimeError('Set XERAX_OBSERVED_EXE to the built schema-2 harness; never silently skip it')
        cls.exe = Path(value).resolve()
        if not cls.exe.is_file():
            raise RuntimeError('Observed harness executable does not exist')

    def setUp(self):
        evidence = os.environ.get('XERAX_OBSERVED_EVIDENCE_DIR')
        if evidence:
            self.directory = Path(evidence) / self._testMethodName
            self.directory.mkdir(parents=True, exist_ok=False)
        else:
            self.temp = tempfile.TemporaryDirectory(prefix='xerax-observed-test-')
            self.addCleanup(self.temp.cleanup)
            self.directory = Path(self.temp.name)
        self.serial = 0

    def run_case(self, *arguments, expected_exit=0):
        self.serial += 1
        trace = self.directory / f'{self.serial}.csv'
        command = [str(self.exe), '--csv', str(trace), '--seconds', '1', '--snapshot-hz', '4', *arguments]
        run = subprocess.run(command, capture_output=True, timeout=15)
        trace.with_suffix('.stdout.json').write_bytes(run.stdout)
        trace.with_suffix('.stderr').write_bytes(run.stderr)
        self.assertEqual(run.returncode, expected_exit, run.stderr.decode(errors='replace'))
        summary = json.loads(run.stdout)
        self.assertEqual(summary['trace_written'], True)
        self.assertTrue(trace.is_file())
        result = analyze(trace, summary, allow_failure=expected_exit != 0)
        return trace, summary, result

    def test_success_measures_real_wake_and_release_observations(self):
        trace, summary, result = self.run_case('--variant', 'whole', '--hold-ms', '100')
        self.assertTrue(summary['complete'])
        self.assertTrue(result['performance_eligible'])
        self.assertEqual(result['snapshot_attempts'], 4)
        with trace.open(newline='') as handle:
            snapshots = [row for row in csv.DictReader(handle) if row['kind'] == 'snapshot']
        owned = [row for row in snapshots if row['status'] == '0']
        self.assertGreater(len(owned), 0)
        self.assertEqual(result['accepted_verified_snapshots'], len(owned))
        self.assertTrue(all(row['wake_us'] and row['verified_us'] and row['released_us'] for row in owned))
        self.assertEqual(result['copy_return_us']['n'], len(owned))
        self.assertEqual(result['verification_us']['n'], len(owned))
        uncensored = sum(row['release_kind'] in ('immediate', 'tick') for row in owned)
        self.assertEqual(result['shutdown_censored_holds'], sum(row['release_kind'] == 'shutdown' for row in owned))
        holds = result['observed_post_verification_hold_us']
        if uncensored:
            self.assertEqual(holds['n'], uncensored)
            self.assertGreaterEqual(holds['p50'] + .002, 100000)
        else:
            self.assertIsNone(holds)
        self.assertEqual(result['consumer_wake_lateness_us']['n'], 4)

    def test_no_snapshot_control_has_null_consumer_metrics(self):
        _, summary, result = self.run_case('--variant', 'none', '--format', 'cu8')
        self.assertEqual(summary['appends'], 100)
        self.assertEqual(result['accepted_verified_snapshots'], 0)
        self.assertIsNone(result['consumer_wake_lateness_us'])
        self.assertIsNone(result['observed_copy_return_to_release_us'])

    def test_each_metadata_field_and_byte_mismatch_preserves_failure_context(self):
        fields = {'byte': 'byte', 'stream': 'stream_id', 'epoch': 'epoch', 'rate': 'sample_rate_hz',
                  'frequency': 'center_frequency_hz', 'width': 'bytes_per_complex_sample',
                  'first': 'first_sample', 'end': 'end_sample', 'size': 'byte_count'}
        for injection, field in fields.items():
            with self.subTest(injection=injection):
                trace, summary, result = self.run_case('--variant', 'whole', '--inject', injection, expected_exit=1)
                self.assertFalse(summary['complete'])
                self.assertFalse(result['performance_eligible'])
                self.assertEqual(summary['outstanding_credits'], 0)
                failure = next(f for f in summary['failures'] if f['worker'] == 'consumer')
                self.assertEqual(failure['field'], field)
                self.assertEqual(failure['end_sample'] - failure['first_sample'], 768000)
                self.assertNotEqual(failure['expected'], failure['actual'])
                self.assertEqual(failure['byte_offset'], 17 if injection == 'byte' else None)
                with trace.open(newline='') as handle:
                    failed = [r for r in csv.DictReader(handle) if r['verification'] == 'failed']
                self.assertEqual(len(failed), 1)
                self.assertEqual(failed[0]['release_kind'], 'failure')
                with self.assertRaisesRegex(ValueError, 'not a performance result'):
                    analyze(trace, summary)

    def test_actual_append_rejection_retains_rejected_interval(self):
        trace, summary, result = self.run_case('--variant', 'none', '--inject', 'append', expected_exit=1)
        self.assertEqual(summary['appends'], 4)
        self.assertEqual(summary['failures'][0]['worker'], 'producer')
        self.assertNotEqual(summary['failures'][0]['actual'], 0)
        self.assertFalse(result['performance_eligible'])
        with trace.open(newline='') as handle:
            last = list(csv.DictReader(handle))[-1]
        self.assertEqual(int(last['index']), 3)
        self.assertEqual(int(last['first_sample']), 33 * 30720 + 1)
        self.assertNotEqual(int(last['status']), 0)

    def test_exception_after_verification_releases_payload_and_stays_failed(self):
        _, summary, result = self.run_case('--variant', 'whole', '--inject', 'consumer-exception', expected_exit=1)
        self.assertEqual(summary['outstanding_credits'], 0)
        self.assertEqual(result['accepted_verified_snapshots'], 1)
        self.assertFalse(result['performance_eligible'])
        self.assertIn('Injected consumer exception', summary['failures'][0]['message'])

    def test_exception_inside_verifier_and_invariant_failure_keep_complete_rows(self):
        for injection, verification in (('verify-exception', 'aborted'), ('overcommit', 'ok')):
            with self.subTest(injection=injection):
                trace, summary, result = self.run_case('--variant', 'whole', '--inject', injection, expected_exit=1)
                self.assertFalse(summary['complete'])
                self.assertFalse(result['performance_eligible'])
                self.assertEqual(summary['outstanding_credits'], 0)
                self.assertTrue(summary['failures'])
                with trace.open(newline='') as handle:
                    accepted = [row for row in csv.DictReader(handle) if row['status'] == '0' and row['kind'] == 'snapshot']
                self.assertEqual(len(accepted), 1)
                self.assertEqual(accepted[0]['verification'], verification)
                self.assertEqual(accepted[0]['release_kind'], 'failure')
                self.assertTrue(accepted[0]['verified_us'] and accepted[0]['released_us'])

    def test_stalled_reader_rejections_do_not_invent_lease_times(self):
        _, summary, result = self.run_case('--variant', 'whole', '--hold-ms', '10000')
        self.assertEqual(result['accepted_verified_snapshots'], 1)
        self.assertEqual(result['snapshot_status_counts'], {'0': 1, '11': 3})
        self.assertEqual(result['shutdown_censored_holds'], 1)
        self.assertIsNone(result['observed_post_verification_hold_us'])
        self.assertEqual(summary['outstanding_credits'], 0)

    def test_trace_write_failure_is_not_success(self):
        target = self.directory / 'missing' / 'trace.csv'
        run = subprocess.run([str(self.exe), '--csv', str(target), '--variant', 'none', '--seconds', '1'],
                             capture_output=True, timeout=15)
        self.assertEqual(run.returncode, 1)
        (self.directory / 'write-failure.stdout.json').write_bytes(run.stdout)
        (self.directory / 'write-failure.stderr').write_bytes(run.stderr)
        summary = json.loads(run.stdout)
        self.assertFalse(summary['complete'])
        self.assertFalse(summary['trace_written'])
        self.assertTrue(summary['trace_error'])
        with self.assertRaisesRegex(ValueError, 'not confirmed written'):
            analyze(target, summary, allow_failure=True)

    def test_corrupted_observations_are_rejected(self):
        trace, summary, _ = self.run_case('--variant', 'whole')
        with trace.open(newline='') as handle:
            rows = list(csv.DictReader(handle))
        snapshot_index = next(i for i, row in enumerate(rows) if row['kind'] == 'snapshot')
        for fault in ('missing', 'extra', 'nan', 'reversed', 'no_release', 'fake_failure', 'wrong_count', 'false_complete'):
            with self.subTest(fault=fault):
                mutated, meta = copy.deepcopy(rows), copy.deepcopy(summary)
                if fault == 'missing': mutated.pop()
                elif fault == 'extra': mutated.append(copy.deepcopy(mutated[-1]))
                elif fault == 'nan': mutated[0]['wake_us'] = 'nan'
                elif fault == 'reversed': mutated[0]['end_us'] = str(float(mutated[0]['begin_us']) - 100)
                elif fault == 'no_release': mutated[snapshot_index]['released_us'] = ''
                elif fault == 'fake_failure': mutated[snapshot_index]['verification'] = 'failed'
                elif fault == 'wrong_count': meta['snapshot_attempts'] += 1
                elif fault == 'false_complete': meta['failures'] = [{'message': 'unhandled failure'}]
                bad = self.directory / (fault + '.csv')
                with bad.open('w', newline='') as handle:
                    writer = csv.DictWriter(handle, fieldnames=COLUMNS); writer.writeheader(); writer.writerows(mutated)
                with self.assertRaises(ValueError): analyze(bad, meta)

    def test_signed_clock_offsets_remain_observable(self):
        trace, summary, original = self.run_case('--variant', 'whole')
        with trace.open(newline='') as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            for field in ('wake_us', 'begin_us', 'end_us', 'verified_us', 'released_us'):
                if row[field]: row[field] = str(float(row[field]) - 1000000)
        shifted = self.directory / 'signed-offsets.csv'
        with shifted.open('w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS); writer.writeheader(); writer.writerows(rows)
        result = analyze(shifted, summary)
        self.assertGreater(result['producer_early_wakes'], 0)
        self.assertLess(result['producer_signed_wake_offset_us']['p50'], 0)
        self.assertEqual(result['accepted_verified_snapshots'], original['accepted_verified_snapshots'])


if __name__ == '__main__':
    unittest.main()
