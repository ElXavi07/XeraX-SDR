"""Independent sidecar controls; native runs are bounded correctness tests only."""
import copy
import csv
import hashlib
import importlib.util
import io
import json
import os
import platform
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from inspect_notify import COLUMNS, analyze

# Reuse the frozen independent source fixture, never an observer-produced oracle.
_source_dir = Path(__file__).resolve().parents[1] / 'iq_screen'
sys.path.insert(0, str(_source_dir))
_spec = importlib.util.spec_from_file_location('_schema4_fixture', _source_dir / 'test_inspect_screen.py')
old = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(old)
sys.path.pop(0)


def encoded(rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def refresh(side, summary):
    for role in ('producer', 'consumer'):
        events = [row for row in side if row['role'] == role]
        for index, row in enumerate(events, 1):
            row['id'] = index
        summary['notification_accounting'][role + '_rows'] = len(events)
    summary.update(mapping_published_count=sum(row['kind'] == 'map_publish' for row in side),
                   owner_binding_count=sum(row['kind'] == 'bind' for row in side),
                   notification_count=sum(row['kind'] == 'notify' for row in side))
    counts = dict(normal_stage_loads=0, normal_yield_calls=0, cleanup_stage_loads=0, cleanup_yield_calls=0)
    for row in side:
        if row['kind'] == 'wait':
            prefix = 'cleanup' if row['phase'] == 'cleanup_poll' else 'normal'
            counts[prefix + '_stage_loads'] += row['stage_loads']
            counts[prefix + '_yield_calls'] += row['yield_calls']
    summary['wait_counts'] = counts


def fixture(mode='notify', fmt='cu8', duration=100):
    rows, summary = old.fixture('coordinator', fmt, duration)
    count = summary['expected_requests']
    summary.update(schema_version=5, base_projection_schema_version=4, wait_mode=mode,
                   safety_wait_timeout_ns=2000000000, sidecar_written=True, sidecar_error=None)
    summary['notification_accounting'] = dict(
        object_storage_bytes=144, active_object_bytes=136 if mode == 'notify' else 0,
        shared_domain_counter_bytes=8, token_value_bytes=16, mapping_entry_bytes=32,
        mapping_capacity=count + 1, mapping_reserved_bytes=(count + 1) * 32,
        mapping_publication_atomic_bytes=8, owner_binding_bytes=32, consumer_binding_bytes=32,
        mapping_vector_object_bytes=24, sidecar_trace_object_bytes=96, sidecar_row_bytes=232,
        producer_trace_capacity=count * 3 + 32, consumer_trace_capacity=count * 7 + 32,
        producer_reserved_capacity=count * 3 + 32, consumer_reserved_capacity=count * 7 + 32,
        sidecar_reserved_bytes=(count * 10 + 64) * 232,
        producer_rows=0, consumer_rows=0, dropped_event_count=0, opaque_runtime_allocation=True)
    summary['notification_state_after'] = (dict(domain=71, last_generation=count, predicate_checks=count,
                                                armed=False, ready=False, waiting=False, closed=True)
                                             if mode == 'notify' else None)
    side = []

    def add(kind, phase, role, before, after, **fields):
        row = dict.fromkeys(COLUMNS, '')
        row.update(kind=kind, phase=phase, role=role, before_ns=before, after_ns=after, status='ok')
        row.update(fields)
        side.append(row)
        return row

    transition = [row for row in rows if row['kind'] == 'service' and row['status'] == 'ok']
    for index in range(count):
        call = old.row_of(rows, 'request', request_id=index + 1)
        take = old.row_of(rows, 'take', request_id=index + 1)
        identity = dict(request_id=index + 1, event_id=call['event_id'], token_domain=71, token_generation=index + 1)
        acquired, _, ready = transition[index * 3:index * 3 + 3]
        if mode == 'notify':
            for kind, service in (('bind', acquired), ('notify', ready)):
                add(kind, service['field'], 'producer', service['after_ns'] + 100, service['after_ns'] + 200,
                    **identity, parent_owner_id=service['parent_id'], parent_service_id=service['id'])
            add('arm', 'request', 'consumer', call['before_ns'] - 900, call['before_ns'] - 800, **identity)
            add('map_publish', 'request', 'consumer', call['before_ns'] - 700, call['before_ns'] - 600, **identity)
        wait_identity = identity if mode == 'notify' else dict(request_id=index + 1, event_id=call['event_id'])
        before = call['after_ns'] + 100
        add('wait', mode, 'consumer', before, take['before_ns'] - 100, **wait_identity,
            base_row_id=call['id'], deadline_ns=before + 2000000000 if mode == 'notify' else '', status='ready',
            stage_loads=0 if mode == 'notify' else 5, yield_calls=0 if mode == 'notify' else 3)
    if mode == 'notify':
        add('close', 'shutdown', 'producer', duration * 1000000 + 11000, duration * 1000000 + 12000, status='closed')
        add('close', 'shutdown', 'consumer', duration * 1000000 - 2000, duration * 1000000 - 1000, status='closed')
    side.sort(key=lambda row: (row['role'] != 'producer', row['before_ns']))
    refresh(side, summary)
    return rows, side, summary


def event(side, kind, request=1):
    return next(row for row in side if row['kind'] == kind and row['request_id'] == request)


def closed_wait_fixture():
    """Independent causal closed-reply example, not a native timing oracle."""
    rows, side, summary = fixture()
    rows[:] = [row for row in rows if row['kind'] not in {'verification', 'release'}]
    old.row_of(rows, 'take')['status'] = 'closed'
    old.row_of(rows, 'outcome')['status'] = 'closed'
    old.renumber(rows)
    summary.update(accepted=0, verified=0, eligible=0, csv_rows=len(rows), complete=False,
                   failures=[dict(role='consumer', message='Controlled sticky-close failure')])
    wait, notify = event(side, 'wait'), event(side, 'notify')
    wait.update(status='closed', after_ns=5007000)
    notify['status'] = 'closed'
    close = dict.fromkeys(COLUMNS, '')
    close.update(kind='close', phase='failure', role='producer', before_ns=5006000, after_ns=5006500, status='closed')
    cleanup = dict(wait, phase='cleanup_poll', before_ns=5008000,
                   after_ns=old.row_of(rows, 'take')['before_ns'] - 100,
                   status='ready', deadline_ns='', stage_loads=7, yield_calls=5)
    side.extend((close, cleanup))
    side.sort(key=lambda row: (row['role'] != 'producer', row['before_ns']))
    refresh(side, summary)
    return rows, side, summary


class SidecarTests(unittest.TestCase):
    def check(self, rows, side, summary, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            source_path, side_path = Path(directory) / 'source.csv', Path(directory) / 'side.csv'
            source_path.write_bytes(old.encoded(rows))
            side_path.write_bytes(encoded(side))
            return analyze(source_path, summary, sidecar=side_path, **kwargs)

    def rejected(self, rows, side, summary, **kwargs):
        with self.assertRaises(ValueError):
            self.check(rows, side, summary, **kwargs)

    def test_modes_formats_and_charged_waits(self):
        for mode in ('poll', 'notify'):
            for fmt in ('cu8', 'cf32'):
                with self.subTest(mode=mode, fmt=fmt):
                    rows, side, summary = fixture(mode, fmt, 200)
                    result = self.check(rows, side, summary)
                    self.assertTrue(result['structural_valid'])
                    self.assertTrue(result['notification_structural_valid'])
                    self.assertTrue(result['measurement_eligible'])
                    self.assertFalse(result['performance_eligible'])
                    self.assertEqual(result['eligible_verified_requests'], 2)
                    self.assertEqual(result['notification_wait_ns']['n'], 2)
                    self.assertEqual(result['sidecar_sha256'], hashlib.sha256(encoded(side)).hexdigest())
                    self.assertEqual(result['trace_sha256'], hashlib.sha256(old.encoded(rows)).hexdigest())

    def test_source_and_sidecar_inputs_read_once_even_if_path_changes(self):
        rows, side, summary = fixture()
        with tempfile.TemporaryDirectory() as directory:
            source_path, side_path = Path(directory) / 'source', Path(directory) / 'side'
            original = {source_path: old.encoded(rows), side_path: encoded(side)}
            counts = {source_path: 0, side_path: 0}
            read = Path.read_bytes
            def swap(path):
                if path in original:
                    counts[path] += 1
                    path.write_bytes(b'replaced and malformed')
                    return original[path]
                return read(path)
            with patch.object(Path, 'read_bytes', swap):
                result = analyze(source_path, summary, sidecar=side_path)
            self.assertEqual(list(counts.values()), [1, 1])
            self.assertEqual(result['trace_sha256'], hashlib.sha256(original[source_path]).hexdigest())
            self.assertEqual(result['sidecar_sha256'], hashlib.sha256(original[side_path]).hexdigest())

    def test_wait_may_return_before_notify_poststamp(self):
        rows, side, summary = fixture()
        notify, wait = event(side, 'notify'), event(side, 'wait')
        notify['after_ns'] = wait['after_ns'] + 500
        self.assertGreater(notify['after_ns'], wait['after_ns'])
        self.check(rows, side, summary)

    def test_signal_before_wait_is_valid(self):
        rows, side, summary = fixture()
        notify, wait = event(side, 'notify'), event(side, 'wait')
        wait['before_ns'] = notify['after_ns'] + 100
        wait['deadline_ns'] = wait['before_ns'] + summary['safety_wait_timeout_ns']
        self.check(rows, side, summary)

    def test_impossible_notify_wait_order_rejected_with_declared_tolerance(self):
        rows, side, summary = fixture()
        wait = event(side, 'wait')
        wait['after_ns'] = event(side, 'notify')['before_ns'] - summary['cross_thread_tolerance_ns'] - 1
        self.rejected(rows, side, summary)

    def test_token_source_request_identity_mutations(self):
        for kind in ('arm', 'map_publish', 'bind', 'notify', 'wait'):
            for field in ('request_id', 'event_id', 'token_domain', 'token_generation'):
                with self.subTest(kind=kind, field=field):
                    rows, side, summary = fixture()
                    event(side, kind)[field] += 1
                    self.rejected(rows, side, summary)

    def test_missing_duplicate_and_detached_operations(self):
        for kind in ('arm', 'map_publish', 'bind', 'notify', 'wait'):
            for operation in ('remove', 'duplicate'):
                with self.subTest(kind=kind, operation=operation):
                    rows, side, summary = fixture()
                    row = event(side, kind)
                    if operation == 'remove':
                        side.remove(row)
                    else:
                        side.append(dict(row))
                    refresh(side, summary)
                    self.rejected(rows, side, summary)

    def test_bind_and_notify_require_actual_matching_owner_transition(self):
        for kind in ('bind', 'notify'):
            for field, value in (('parent_owner_id', 1), ('parent_service_id', 1), ('base_row_id', 3), ('role', 'consumer')):
                with self.subTest(kind=kind, field=field):
                    rows, side, summary = fixture()
                    event(side, kind)[field] = value
                    refresh(side, summary)
                    self.rejected(rows, side, summary)

    def test_owner_interval_includes_all_new_costs(self):
        rows, side, summary = fixture()
        notify = event(side, 'notify')
        owner = next(row for row in rows if row['kind'] == 'owner' and row['id'] == notify['parent_owner_id'])
        notify['after_ns'] = owner['after_ns'] + 1
        self.rejected(rows, side, summary)

    def test_same_role_sidecar_and_source_calls_cannot_overlap(self):
        for kind, field in (('arm', 'after_ns'), ('bind', 'before_ns')):
            with self.subTest(kind=kind):
                rows, side, summary = fixture()
                row = event(side, kind)
                if kind == 'arm':
                    row[field] = old.row_of(rows, 'request')['after_ns']
                else:
                    service = next(row2 for row2 in rows if row2['role'] == 'producer' and row2['id'] == row['parent_service_id'])
                    row[field] = service['before_ns']
                self.rejected(rows, side, summary)

    def test_counter_truth_and_no_hidden_notification_polling(self):
        for mode in ('poll', 'notify'):
            rows, side, summary = fixture(mode)
            event(side, 'wait')['stage_loads'] += 1
            refresh(side, summary)
            self.rejected(rows, side, summary)
        rows, side, summary = fixture()
        summary['wait_counts']['normal_stage_loads'] = 1
        self.rejected(rows, side, summary)

    def test_clean_notify_forbids_polling_fallback(self):
        rows, side, summary = fixture()
        wait = event(side, 'wait')
        wait.update(phase='cleanup_poll', stage_loads=5, yield_calls=3)
        refresh(side, summary)
        self.rejected(rows, side, summary)

    def test_lifecycle_summary_and_final_state_mutations(self):
        for field in ('mapping_published_count', 'owner_binding_count', 'notification_count'):
            rows, side, summary = fixture()
            summary[field] += 1
            self.rejected(rows, side, summary)
        for field, value in (('domain', 0), ('last_generation', 0), ('armed', True), ('ready', True), ('waiting', True), ('closed', False)):
            rows, side, summary = fixture()
            summary['notification_state_after'][field] = value
            self.rejected(rows, side, summary)

    def test_memory_accounting_equations_and_missing_metrics(self):
        for field in ('mapping_reserved_bytes', 'sidecar_reserved_bytes', 'consumer_binding_bytes', 'producer_rows',
                      'dropped_event_count', 'token_value_bytes', 'producer_trace_capacity'):
            rows, side, summary = fixture()
            summary['notification_accounting'][field] += 1
            self.rejected(rows, side, summary)
        for field in ('mapping_vector_object_bytes', 'sidecar_row_bytes', 'object_storage_bytes'):
            rows, side, summary = fixture()
            del summary['notification_accounting'][field]
            self.rejected(rows, side, summary)

    def test_projection_never_repairs_broken_source_status_or_counts(self):
        for field in ('accepted', 'verified', 'csv_rows', 'prefill_iterations'):
            rows, side, summary = fixture()
            summary[field] += 1
            self.rejected(rows, side, summary)
        rows, side, summary = fixture()
        old.row_of(rows, 'verification')['status'] = 'mismatch'
        self.rejected(rows, side, summary)

    def test_bad_versions_safety_deadlines_persistence_and_nonfinite_values(self):
        for field, value in (('schema_version', 4), ('base_projection_schema_version', 3), ('safety_wait_timeout_ns', 50000000),
                             ('sidecar_written', False), ('sidecar_error', 'disk failed')):
            rows, side, summary = fixture()
            summary[field] = value
            self.rejected(rows, side, summary)
        for field, value in (('deadline_ns', 55001000), ('before_ns', 'nan'), ('token_domain', -1), ('yield_calls', float('inf'))):
            rows, side, summary = fixture()
            event(side, 'wait')[field] = value
            self.rejected(rows, side, summary)

    def test_cpu_window_must_include_standalone_notifier_shutdown(self):
        rows, side, summary = fixture()
        close = next(row for row in side if row['kind'] == 'close' and row['role'] == 'producer')
        close['before_ns'] = summary['process_cpu']['end_before_ns'] + 1
        close['after_ns'] = close['before_ns'] + 100
        self.rejected(rows, side, summary)

    def test_retired_generation_cannot_be_rebound_to_later_request(self):
        rows, side, summary = fixture(duration=200)
        for row in side:
            if row['request_id'] == 2:
                row['token_generation'] = 1
        self.rejected(rows, side, summary)

    def test_failed_notifier_preserves_source_ticket_and_explicit_cleanup(self):
        rows, side, summary = closed_wait_fixture()
        result = self.check(rows, side, summary, allow_failure=True)
        self.assertTrue(result['structural_valid'])
        self.assertFalse(result['measurement_eligible'])
        self.assertEqual(result['cleanup_poll_count'], 1)
        self.assertEqual(result['accepted_grants'], 0)
        self.assertIn('notification_cleanup_poll', result['measurement_ineligible_reasons'])
        self.rejected(rows, side, summary)
        for field in ('event_id', 'token_domain', 'base_row_id'):
            changed = copy.deepcopy(side)
            cleanup = next(row for row in changed if row['phase'] == 'cleanup_poll')
            cleanup[field] += 1
            self.rejected(rows, changed, summary, allow_failure=True)

    def test_sticky_close_cannot_be_relabelled_successful_ready(self):
        rows, side, summary = closed_wait_fixture()
        event(side, 'wait').update(status='ready', before_ns=5006800)
        event(side, 'wait')['deadline_ns'] = event(side, 'wait')['before_ns'] + 2000000000
        event(side, 'notify')['status'] = 'ok'
        self.rejected(rows, side, summary, allow_failure=True)

    def test_failed_wait_cannot_invent_timeout_or_counter_exhaustion(self):
        for status in ('timed_out', 'counter_exhausted'):
            rows, side, summary = closed_wait_fixture()
            event(side, 'wait')['status'] = status
            self.rejected(rows, side, summary, allow_failure=True)

    def test_closed_before_arm_records_actual_rejected_source_submission(self):
        rows, side, summary = fixture()
        rows[:] = [row for row in rows if row['kind'] not in {'take', 'verification', 'release'}]
        old.row_of(rows, 'request')['status'] = 'closed'
        old.row_of(rows, 'outcome')['status'] = 'closed'
        for row in rows:
            if row['kind'] == 'service' and row['status'] == 'ok':
                row.update(status='closed', field='closed')
        old.renumber(rows)
        summary.update(accepted=0, verified=0, eligible=0, csv_rows=len(rows), complete=False,
                       failures=[dict(role='consumer', message='Controlled close-before-arm failure')])
        side[:] = [row for row in side if row['kind'] in {'arm', 'close'}]
        arm = event(side, 'arm')
        arm.update(status='closed', token_domain='', token_generation='')
        close = dict.fromkeys(COLUMNS, '')
        close.update(kind='close', phase='failure', role='producer', before_ns=5001500, after_ns=5002000, status='closed')
        side.append(close)
        side.sort(key=lambda row: (row['role'] != 'producer', row['before_ns']))
        summary['notification_state_after'].update(last_generation=0, predicate_checks=0)
        refresh(side, summary)
        result = self.check(rows, side, summary, allow_failure=True)
        self.assertFalse(result['measurement_eligible'])
        self.assertIn('notification_arm_closed', result['measurement_ineligible_reasons'])
        self.assertEqual(result['accepted_grants'], 0)
        arm['token_generation'] = 1
        self.rejected(rows, side, summary, allow_failure=True)

    def test_notify_cannot_be_swapped_between_actual_service_cycles(self):
        rows, side, summary = fixture(duration=200)
        first, second = event(side, 'notify', 1), event(side, 'notify', 2)
        for field in ('request_id', 'event_id', 'token_domain', 'token_generation'):
            first[field], second[field] = second[field], first[field]
        self.rejected(rows, side, summary)


@unittest.skipUnless(os.environ.get('XERAX_NOTIFY_SCREEN_EXE'),
                     'Native correctness controls explicitly unavailable: set XERAX_NOTIFY_SCREEN_EXE')
class NativeTests(unittest.TestCase):
    def execute(self, mode, fmt='cu8', fault='none'):
        control_root = os.environ.get('XERAX_NOTIFY_CONTROL_DIR')
        if control_root:
            Path(control_root).mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix=f'{mode}-{fmt}-{fault}-', dir=control_root))
        trace, side = directory / 'source.csv', directory / 'sidecar.csv'
        command = [os.environ['XERAX_NOTIFY_SCREEN_EXE'], '--wait-mode', mode, '--format', fmt,
                   '--duration-ms', '200', '--fault', fault, '--csv', str(trace), '--sidecar', str(side)]
        process = dict(command=command, timeout_seconds=30, python=sys.version, optimized=sys.flags.optimize,
                       platform=platform.platform(), parent_pid=os.getpid(), cwd=str(Path.cwd()), returncode=None)
        try:
            completed = subprocess.run(command, capture_output=True, timeout=30)
        except subprocess.TimeoutExpired as error:
            process['error'] = 'timeout'
            (directory / 'stdout.json').write_bytes(error.stdout or b'')
            (directory / 'stderr.txt').write_bytes(error.stderr or b'')
            (directory / 'process.json').write_text(json.dumps(process, indent=2))
            print('Preserved timed-out native notification control:', directory)
            raise
        except OSError as error:
            process['error'] = str(error)
            (directory / 'process.json').write_text(json.dumps(process, indent=2))
            raise
        process['returncode'] = completed.returncode
        (directory / 'process.json').write_text(json.dumps(process, indent=2))
        (directory / 'stdout.json').write_bytes(completed.stdout)
        (directory / 'stderr.txt').write_bytes(completed.stderr)
        try:
            self.assertIn(completed.returncode, (0, 2))
            summary = json.loads(completed.stdout)
            result = analyze(trace, summary, sidecar=side, allow_failure=True)
            self.assertEqual(completed.returncode == 0, summary['complete'])
            self.assertTrue(result['structural_valid'])
            if fault == 'none':
                self.assertTrue(result['measurement_eligible'])
                self.assertEqual(summary['verified'], summary['accepted'])
            else:
                self.assertFalse(result['measurement_eligible'])
                source_rows = list(csv.DictReader(io.StringIO(trace.read_text())))
                if fault == 'append':
                    self.assertTrue(any(row['kind'] == 'append' and row['status'] == 'rejected' for row in source_rows))
                elif fault == 'byte':
                    self.assertTrue(any(row['kind'] == 'verification' and row['status'] == 'mismatch' and row['field'] == 'byte' for row in source_rows))
                elif fault == 'consumer-exception':
                    self.assertTrue(any(row['kind'] == 'verification' and row['status'] == 'aborted' for row in source_rows))
                elif fault == 'producer-exception':
                    self.assertTrue(any(row['kind'] == 'owner' and row['status'] == 'failed' for row in source_rows))
                elif fault == 'pending-shutdown':
                    self.assertTrue(any(row['kind'] == 'take' and row['status'] == 'closed' for row in source_rows))
                elif fault == 'held-shutdown':
                    self.assertTrue(any(row['kind'] == 'release' and row['phase'] == 'shutdown' for row in source_rows))
            return result, summary, trace.read_bytes(), side.read_bytes()
        except Exception:
            print('Preserved failed native notification control:', directory)
            raise
        finally:
            # Bounded raw evidence remains available for independent review.
            # This correctness helper never adaptively reruns a failed control.
            pass

    def test_clean_modes_and_formats(self):
        for mode in ('poll', 'notify'):
            for fmt in ('cu8', 'cf32'):
                with self.subTest(mode=mode, fmt=fmt):
                    result, _, _, _ = self.execute(mode, fmt)
                    if mode == 'notify':
                        self.assertEqual(result['wait_counts']['normal_stage_loads'], 0)

    def test_inherited_failure_controls(self):
        for mode in ('poll', 'notify'):
            for fault in ('append', 'byte', 'producer-exception', 'consumer-exception', 'pending-shutdown', 'held-shutdown'):
                with self.subTest(mode=mode, fault=fault):
                    self.execute(mode, fault=fault)

    def test_delayed_publication_poststamp_remains_valid(self):
        for mode in ('poll', 'notify'):
            with self.subTest(mode=mode):
                _, summary, raw, _ = self.execute(mode, fault='publication-pause')
                rows = list(csv.DictReader(io.StringIO(raw.decode())))
                publication = next(row for row in rows if row['kind'] == 'publication' and row['event_id'] == '141')
                selection = next(row for row in rows if row['kind'] == 'selection')
                self.assertEqual(selection['event_id'], '141')
                tolerance = summary['cross_thread_tolerance_ns']
                self.assertLessEqual(int(publication['before_ns']), int(selection['before_ns']) + tolerance)
                self.assertGreaterEqual(int(publication['after_ns']) + tolerance, int(selection['after_ns']))


if __name__ == '__main__':
    unittest.main()
