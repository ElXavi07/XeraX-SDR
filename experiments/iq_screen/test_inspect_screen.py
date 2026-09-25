"""Independent schema-4 fixtures and bounded executable correctness checks.

Synthetic records are constructed here, without calling the observer or its
serializer. Native tests run only when XERAX_SCREEN_EXE is explicitly set.
These checks do not establish comparative performance or hard deadlines.
"""
import csv
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from inspect_screen import COLUMNS, analyze


def fixture(variant='whole', fmt='cu8', duration=100):
    width = 2 if fmt == 'cu8' else 8
    rows = []
    ids = {'producer': 0, 'consumer': 0}
    base = dict(stream_id=1, epoch=1, rate_hz=3072000, frequency_hz=451100000,
                width=width, pool_id=7 if variant == 'coordinator' else '',
                generation=3 if variant == 'coordinator' else '')

    def add(kind, role, before, after, **fields):
        ids[role] += 1
        row = dict.fromkeys(COLUMNS, '')
        row.update(kind=kind, role=role, id=ids[role], before_ns=before, after_ns=after, status='ok')
        row.update(fields)
        rows.append(row)
        return row

    pubs = []
    for index in range(140 + duration // 10):
        timed = index >= 140
        start = (index - 140) * 10000000
        phase = 'timed' if timed else 'prefill'
        owner = add('owner', 'producer', start, start + 900000, phase=phase,
                    due_ns=(index - 140) * 10000000 if timed else '')
        common = dict(parent_id=owner['id'])
        first, end = index * 30720, (index + 1) * 30720
        add('generate', 'producer', start + 10000, start + 100000, **common,
            phase='input', first_sample=first, end_sample=end, byte_count=30720 * width)
        add('append', 'producer', start + 110000, start + 200000, **common, **base,
            phase='input', first_sample=first, end_sample=end, byte_count=30720 * width, source_status=0)
        retained = max(0, end - 8388608 // width)
        descriptor = dict(**base, event_id=index + 1, first_sample=retained, end_sample=end,
                          byte_count=(end - retained) * width)
        add('state', 'producer', start + 210000, start + 220000, **common, **descriptor, phase='published_frontier')
        pubs.append(add('publication', 'producer', start + 230000, start + 240000,
                        **common, **descriptor, phase='release_store'))
        if variant == 'coordinator' and timed:
            for step in range(3):
                at = start + 250000 + step * 20000
                serving = index >= 141 and (index - 141) % 10 == 0
                add('service', 'producer', at, at + 10000, **common, phase=f'step{step + 1}',
                    check_ns=at, status='ok' if serving else 'empty',
                    field=('acquired', 'granted', 'ready')[step] if serving else 'idle')
            add('reclaim', 'producer', start + 320000, start + 330000, **common, phase='owner')
    add('shutdown', 'producer', duration * 1000000, duration * 1000000 + 10000, phase='owner')
    count = 0 if variant == 'none' else (duration + 94) // 100
    for index in range(count):
        request_id = index + 1
        due = 5000000 + index * 100000000
        selected = pubs[140 + index * 10]
        source = {key: selected[key] for key in (*base, 'event_id', 'first_sample', 'end_sample', 'byte_count')}
        add('selection', 'consumer', due, due + 1000, **source, request_id=request_id,
            phase='acquire_load', due_ns=due)
        source.update(first_sample=source['end_sample'] - 768000, byte_count=768000 * width)
        source['request_id'] = request_id
        deadline = due + 1000 + 50000000
        source['deadline_ns'] = deadline
        add('eligibility', 'consumer', due + 2000, due + 3000, **source,
            phase='pre_call', check_ns=due + 2000)
        add('request', 'consumer', due + 4000, due + 5000, **source,
            phase='submit' if variant == 'coordinator' else 'whole_copy',
            check_ns=due + 4000, source_status='' if variant == 'coordinator' else 0)
        if variant == 'coordinator':
            add('take', 'consumer', due + 5301000, due + 5302000, **source,
                phase='mailbox', check_ns=due + 5301000, source_status=0)
        post = due + (5303000 if variant == 'coordinator' else 8000)
        add('eligibility', 'consumer', post, post + 1000, **source,
            phase='post_call', check_ns=post)
        add('verification', 'consumer', post + 2000, post + 12000, **source,
            phase='exact_bytes', verified_bytes=768000 * width)
        add('release', 'consumer', post + 13000, post + 14000, **source, phase='normal')
        add('outcome', 'consumer', post + 15000, post + 16000, **source,
            phase='request', check_ns=post)
    if count:
        add('shutdown', 'consumer', duration * 1000000, duration * 1000000 + 10000, phase='client')
    summary = dict(schema_version=4, variant=variant, format=fmt, duration_ms=duration,
                   producer_period_ns=10000000, request_period_ns=100000000,
                   snapshot_samples=768000, deadline_ns=50000000, width=width,
                   rate_hz=3072000, stream_id=1, epoch=1, frequency_hz=451100000,
                   prefill_iterations=140, expected_owner_iterations=duration // 10,
                   expected_requests=count, completed_owner_iterations=duration // 10,
                   completed_requests=count, accepted=count, verified=count, eligible=count,
                   complete=True, shutdown_acknowledged=True, fault='none',
                   secondary_failure_count=0, emergency_cleanup=False,
                   cpu_time_ns=None, measured_memory_stats=None,
                   trace_written=True, trace_error=None, csv_rows=len(rows),
                   producer_trace_capacity=10000, consumer_trace_capacity=1000,
                   trace_reserved_bytes=4000000, publication_descriptor_bytes=4096,
                   input_buffer_bytes=30720 * width, dropped_event_count=0,
                   performance_eligible=False, cross_thread_tolerance_ns=1000,
                   clock=dict(is_steady=True, period_num=1, period_den=1000000000,
                              qpc_frequency_hz=10000000, provenance='Independent synthetic clock fixture'),
                   failures=[])
    summary['abi'] = dict(pointer_bytes=8, credit_history_bytes=168, snapshot_lease_bytes=160,
                          slab_history_bytes=16, slab_budget_bytes=16, coordinator_budget_bytes=16,
                          mailbox_bytes=56, reply_bytes=280)
    summary['process_cpu'] = dict(api='CLOCK_PROCESS_CPUTIME_ID', scope='before_thread_launch_through_join',
                                 start_before_ns=-1000000, start_after_ns=-999900,
                                 end_before_ns=duration * 1000000 + 20000000,
                                 end_after_ns=duration * 1000000 + 20000100,
                                 start_value_ns=500000000, end_value_ns=550000000, elapsed_ns=50000000,
                                 wall_elapsed_min_ns=duration * 1000000 + 20999900,
                                 wall_elapsed_max_ns=duration * 1000000 + 21000100,
                                 api_resolution_ns=1, resolution_kind='clock_getres', logical_cpu_count=4,
                                 sanity_allowance_per_logical_cpu_ns=20000000,
                                 start_error=0, end_error=0, valid=True)
    for name, publication, at in (('source_memory_before', pubs[139], -2000000),
                                  ('source_memory_after', pubs[-1], duration * 1000000 + 21000000)):
        endpoint = dict(before_ns=at, after_ns=at + 100, retention_capacity_bytes=8388608,
                        retained_bytes=8388608, first_sample=publication['first_sample'],
                        end_sample=publication['end_sample'], accepted_end_sample=publication['end_sample'],
                        source_active=True, source_metadata_opaque=variant != 'coordinator',
                        unreserved_facade_bytes=48 if variant == 'coordinator' else 168,
                        whole=None, slabs=None, coordinator=None, mailbox_metadata=None)
        if variant != 'coordinator':
            endpoint['whole'] = dict(ring_capacity_bytes=8388608, snapshot_capacity_bytes=7340032,
                                     slot_count=1, outstanding_count=0, outstanding_reserved_bytes=0,
                                     preallocated_snapshot_bytes=7340032, total_payload_bytes=15728640,
                                     payload_budget_bytes=15728640)
        else:
            endpoint['slabs'] = dict(payload_bytes=15728640, metadata_bytes=64000, budget_control_bytes=128,
                                     payload_limit=15728640, metadata_limit=131072, arenas=1,
                                     snapshot_pinned_slabs=0, live_pinned_slabs=0, outstanding_live_leases=0,
                                     filling_bytes=0, history_slabs=137, free_slabs=115)
            endpoint['coordinator'] = dict(reservation_limit=16384, current_reserved_bytes=832,
                                           high_water_reserved_bytes=832, ledger_allocation_bytes=104,
                                           control_allocation_bytes=392, fixed_reservation_bytes=336,
                                           control_reservations=1, high_water_control_reservations=1)
            endpoint['mailbox_metadata'] = dict(control_allocation_bytes=392, coordinator_object_bytes=56,
                                                held_reply_object_bytes=280, reserved_bytes=728, metadata_cap=8192)
        summary[name] = endpoint
    return rows, summary


def calibration(summary):
    return dict(schema_version=1, kind='whole_source_allocation_calibration', available=True, format=summary['format'],
                width=summary['width'], payload_bytes=15728640, allocation_count=7, deallocation_count=7,
                captured_allocation_bytes=15729664, metadata_allocation_bytes_including_facade=1024,
                metadata_reservation_bytes=1184, peak_live_bytes=15729664,
                live_bytes_after_history_destroy=7340400, live_bytes_after_destroy=0, operational_allocations=0,
                verified_bytes=768000 * summary['width'], retained_bytes=8388608,
                credit_history_bytes=168, snapshot_lease_bytes=160, pointer_bytes=8, complete=True)


def encoded(rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode('utf-8')


def row_of(rows, kind, phase=None, request_id=None):
    return next(row for row in rows if row['kind'] == kind and
                (phase is None or row['phase'] == phase) and
                (request_id is None or row['request_id'] == request_id))


def renumber(rows):
    # Used only for consumer semantic reorder attacks; owner links are unchanged.
    counter = 0
    for row in rows:
        if row['role'] == 'consumer':
            counter += 1
            row['id'] = counter


class SyntheticTraceTests(unittest.TestCase):
    def check(self, rows, summary, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trace.csv'
            path.write_bytes(encoded(rows))
            return analyze(path, summary, **kwargs)

    def rejected(self, rows, summary, **kwargs):
        with self.assertRaises(ValueError):
            self.check(rows, summary, **kwargs)

    def test_all_profiles_and_exact_source_intervals(self):
        for variant in ('none', 'whole', 'coordinator'):
            for fmt in ('cu8', 'cf32'):
                with self.subTest(variant=variant, fmt=fmt):
                    rows, summary = fixture(variant, fmt)
                    result = self.check(rows, summary)
                    self.assertTrue(result['structural_valid'])
                    self.assertTrue(result['complete_clean_workload'])
                    self.assertFalse(result['performance_eligible'])
                    self.assertEqual(result['publication_count'], 150)
                    if variant != 'none':
                        self.assertEqual(result['source_intervals'][0]['first_sample'], 3563520)
                        self.assertEqual(result['source_intervals'][0]['end_sample'], 4331520)
                    self.assertIsNone(result['shutdown_censored_requested_holds'])

    def test_overlap_store_before_producer_post_stamp(self):
        rows, summary = fixture()
        pub = next(row for row in rows if row['kind'] == 'publication' and row['event_id'] == 141)
        pub['after_ns'] = 6000000
        next(row for row in rows if row['kind'] == 'owner' and row['id'] == pub['parent_id'])['after_ns'] = 6100000
        result = self.check(rows, summary)
        self.assertEqual(result['publication_to_selection_ns_bounds'][0]['lower_ns'], 0)
        self.assertGreater(pub['after_ns'], row_of(rows, 'selection')['after_ns'])

    def test_cross_role_tolerance_and_impossible_order(self):
        rows, summary = fixture()
        pub = next(row for row in rows if row['kind'] == 'publication' and row['event_id'] == 141)
        selection = row_of(rows, 'selection')
        pub['before_ns'] = selection['after_ns'] + 1000
        pub['after_ns'] = pub['before_ns'] + 1000
        next(row for row in rows if row['kind'] == 'owner' and row['id'] == pub['parent_id'])['after_ns'] = pub['after_ns'] + 1000
        self.check(rows, summary)
        pub['before_ns'] += 1
        self.rejected(rows, summary)

    def test_stale_completed_publication_is_diagnostic_not_invented_happens_before(self):
        rows, summary = fixture(duration=200)
        selection = row_of(rows, 'selection', request_id=2)
        old = next(row for row in rows if row['kind'] == 'publication' and row['event_id'] == 141)
        fields = ('event_id', 'first_sample', 'end_sample', 'byte_count')
        for row in rows:
            if row['request_id'] == 2:
                row.update({key: old[key] for key in fields})
                if row is not selection:
                    row.update(first_sample=old['end_sample'] - 768000, byte_count=1536000)
        result = self.check(rows, summary)
        self.assertGreater(result['publication_to_selection_ns_bounds'][1]['newer_completed_publications'], 0)

    def test_unknown_duplicate_and_regressing_publication_ids(self):
        for field, value in (('event_id', 999), ('epoch', 2), ('width', 8), ('end_sample', 99999999)):
            with self.subTest(field=field):
                rows, summary = fixture()
                row_of(rows, 'selection')[field] = value
                self.rejected(rows, summary)
        rows, summary = fixture()
        row_of(rows, 'publication')['event_id'] = 2
        self.rejected(rows, summary)
        rows, summary = fixture('coordinator')
        row_of(rows, 'selection')['pool_id'] = 8
        self.rejected(rows, summary)
        rows, summary = fixture(duration=200)
        old = next(row for row in rows if row['kind'] == 'publication' and row['event_id'] == 140)
        for row in rows:
            if row['request_id'] == 2:
                row.update({key: old[key] for key in ('event_id', 'first_sample', 'end_sample', 'byte_count')})
                if row['kind'] != 'selection':
                    row.update(first_sample=old['end_sample'] - 768000, byte_count=1536000)
        self.rejected(rows, summary)

    def test_missing_each_required_operation(self):
        for kind in ('generate', 'append', 'state', 'publication', 'service', 'reclaim',
                     'selection', 'request', 'take', 'verification', 'release', 'outcome', 'shutdown'):
            with self.subTest(kind=kind):
                rows, summary = fixture('coordinator')
                rows.remove(row_of(rows, kind))
                summary['csv_rows'] = len(rows)
                self.rejected(rows, summary)

    def test_owner_must_enclose_all_work(self):
        for kind in ('generate', 'append', 'publication', 'service', 'reclaim'):
            rows, summary = fixture('coordinator')
            child = row_of(rows, kind)
            owner = next(row for row in rows if row['kind'] == 'owner' and row['id'] == child['parent_id'])
            owner['after_ns'] = child['after_ns'] - 1
            self.rejected(rows, summary)

    def test_producer_semantic_order_not_only_timestamps(self):
        rows, summary = fixture('coordinator')
        service = row_of(rows, 'service')
        reclaim = row_of(rows, 'reclaim')
        # Swap contents except structural identity/timing. Generic monotonicity remains valid.
        for key in ('kind', 'phase', 'field', 'check_ns'):
            service[key], reclaim[key] = reclaim[key], service[key]
        reclaim['check_ns'] = reclaim['before_ns']
        self.rejected(rows, summary)

    def test_taken_reply_requires_real_unique_owner_transition_cycle(self):
        for mutation in ('missing', 'busy_ready', 'wrong_order', 'reused'):
            with self.subTest(mutation=mutation):
                rows, summary = fixture('coordinator', duration=200 if mutation == 'reused' else 100)
                transitions = [row for row in rows if row['kind'] == 'service' and row['status'] == 'ok']
                if mutation == 'missing':
                    for row in transitions:
                        row.update(status='empty', field='idle')
                elif mutation == 'busy_ready':
                    transitions[2]['status'] = 'busy'
                elif mutation == 'wrong_order':
                    transitions[1]['field'] = 'acquired'
                else:
                    for row in transitions[3:]:
                        row.update(status='empty', field='idle')
                self.rejected(rows, summary)

    def test_pending_service_tick_rejection_is_feasible_but_not_a_transition(self):
        rows, summary = fixture('coordinator')
        services = [row for row in rows if row['kind'] == 'service']
        first_owner = next(row for row in rows if row['kind'] == 'owner' and row['id'] == services[0]['parent_id'])
        first_owner['after_ns'] = 5020000
        services[0].update(before_ns=5003000, after_ns=5004500, check_ns=5003000,
                           status='tick_regression', field='pending')
        services[1].update(before_ns=5005000, after_ns=5006000, check_ns=5005000,
                           status='ok', field='acquired')
        services[2].update(before_ns=5007000, after_ns=5008000, check_ns=5007000,
                           status='ok', field='granted')
        reclaim = next(row for row in rows if row['kind'] == 'reclaim' and row['parent_id'] == first_owner['id'])
        reclaim.update(before_ns=5009000, after_ns=5010000)
        services[3].update(status='ok', field='ready')
        services[4].update(status='busy', field='ready')
        services[5].update(status='busy', field='ready')
        result = self.check(rows, summary)
        self.assertTrue(result['measurement_eligible'])
        self.assertEqual(result['accepted_grants'], 1)
        baseline = copy.deepcopy(rows)
        for changes in (dict(field='granted'),
                        dict(before_ns=5004000, check_ns=5004000),
                        dict(before_ns=5001000, check_ns=5001000, after_ns=5002999)):
            broken = copy.deepcopy(baseline)
            row_of(broken, 'service').update(changes)
            self.rejected(broken, summary)
        # A rejected check is not an acquired transition and cannot replace the
        # subsequent successful cycle even though it observed Pending.
        services[1].update(status='empty', field='idle')
        self.rejected(rows, summary)

    def test_transition_cycle_cannot_precede_submit_or_follow_take(self):
        for before_ns in (250000, 20250000):
            rows, summary = fixture('coordinator')
            transitions = [row for row in rows if row['kind'] == 'service' and row['status'] == 'ok']
            replacement = [row for row in rows if row['kind'] == 'service' and
                           before_ns <= row['before_ns'] < before_ns + 60000]
            for row in transitions:
                row.update(status='empty', field='idle')
            for row, phase in zip(replacement, ('acquired', 'granted', 'ready')):
                row.update(status='ok', field=phase)
            self.rejected(rows, summary)

    def test_owner_transition_brackets_may_overlap_submit_and_take(self):
        rows, summary = fixture('coordinator')
        request = row_of(rows, 'request')
        request['after_ns'] = 10265000  # Acquired release may precede submit's post-stamp.
        ready = next(row for row in rows if row['kind'] == 'service' and row['status'] == 'ok' and row['field'] == 'ready')
        ready['after_ns'] = 10310000  # Consumer may observe Ready before owner resumes.
        result = self.check(rows, summary)
        self.assertEqual(result['accepted_grants'], 1)

    def test_coordinator_take_success_cannot_check_at_deadline(self):
        rows, summary = fixture('coordinator')
        take = row_of(rows, 'take')
        delta = take['deadline_ns'] - take['before_ns']
        for row in rows:
            if row['role'] == 'consumer' and row['id'] >= take['id'] and row['kind'] != 'shutdown':
                row['before_ns'] += delta
                row['after_ns'] += delta
                if row['check_ns'] != '':
                    row['check_ns'] += delta
        row_of(rows, 'eligibility', 'post_call')['status'] = 'deadline_expired'
        row_of(rows, 'outcome')['status'] = 'deadline_expired'
        summary['eligible'] = 0
        with self.assertRaisesRegex(ValueError, 'Successful coordinator grant contradicts supplied deadline checks'):
            self.check(rows, summary)

    def test_coordinator_service_success_cannot_check_at_deadline_inside_long_take(self):
        for step in range(3):
            with self.subTest(step=step):
                rows, summary = fixture('coordinator')
                transitions = [row for row in rows if row['kind'] == 'service' and row['status'] == 'ok']
                take = row_of(rows, 'take')
                deadline = take['deadline_ns']
                delta = deadline - transitions[step]['before_ns']
                for row in rows:
                    if row['role'] == 'producer' and row['before_ns'] >= 10000000:
                        row['before_ns'] += delta
                        row['after_ns'] += delta
                        if row['check_ns'] != '':
                            row['check_ns'] += delta
                # The consumer's actual take check is early, but its long call
                # bracket overlaps the late owner transitions. Timestamp
                # feasibility alone cannot authorize a successful core result.
                new_after = max(row['after_ns'] for row in transitions) + 1000
                shift = new_after - take['after_ns']
                take['after_ns'] = new_after
                for row in rows:
                    if row['role'] == 'consumer' and row['id'] > take['id'] and row['kind'] != 'shutdown':
                        row['before_ns'] += shift
                        row['after_ns'] += shift
                        if row['check_ns'] != '':
                            row['check_ns'] += shift
                row_of(rows, 'eligibility', 'post_call')['status'] = 'deadline_expired'
                row_of(rows, 'outcome')['status'] = 'deadline_expired'
                summary['eligible'] = 0
                with self.assertRaisesRegex(ValueError, 'Successful coordinator grant contradicts supplied deadline checks'):
                    self.check(rows, summary)

    def test_coordinator_admission_success_cannot_check_at_deadline(self):
        rows, summary = fixture('coordinator')
        call = row_of(rows, 'request')
        delta = call['deadline_ns'] - call['before_ns']
        for row in rows:
            if row['role'] == 'consumer' and row['id'] >= call['id'] and row['kind'] != 'shutdown':
                row['before_ns'] += delta
                row['after_ns'] += delta
                if row['check_ns'] != '':
                    row['check_ns'] += delta
        row_of(rows, 'eligibility', 'post_call')['status'] = 'deadline_expired'
        row_of(rows, 'outcome')['status'] = 'deadline_expired'
        summary['eligible'] = 0
        with self.assertRaisesRegex(ValueError, 'Coordinator admitted request at or after its supplied deadline'):
            self.check(rows, summary)

    def test_coordinator_admission_can_expire_after_precheck_before_submit(self):
        rows, summary = fixture('coordinator')
        call = row_of(rows, 'request')
        deadline = call['deadline_ns']
        call.update(before_ns=deadline, after_ns=deadline + 1000, check_ns=deadline,
                    status='deadline_expired')
        post = row_of(rows, 'eligibility', 'post_call')
        post.update(before_ns=deadline + 2000, after_ns=deadline + 3000,
                    check_ns=deadline + 2000, status='deadline_expired')
        row_of(rows, 'outcome').update(before_ns=deadline + 4000, after_ns=deadline + 5000,
                                      check_ns=post['check_ns'], status='deadline_expired')
        rows = [row for row in rows if row['kind'] not in {'take', 'verification', 'release'}]
        for row in rows:
            if row['kind'] == 'service' and row['status'] == 'ok':
                row.update(status='empty', field='idle')
        renumber(rows)
        summary.update(csv_rows=len(rows), accepted=0, verified=0, eligible=0)
        result = self.check(rows, summary)
        self.assertEqual(result['accepted_grants'], 0)
        self.assertEqual(result['request_status_counts'], {'deadline_expired': 1})

    def test_consumer_semantic_order_not_only_timestamps(self):
        for first_kind, first_phase, second_kind, second_phase in (
                ('eligibility', 'pre_call', 'request', None),
                ('eligibility', 'post_call', 'verification', None),
                ('request', None, 'take', None)):
            rows, summary = fixture('coordinator')
            first = row_of(rows, first_kind, first_phase)
            second = row_of(rows, second_kind, second_phase)
            a, b = rows.index(first), rows.index(second)
            # Change CSV order and operation brackets coherently, keep check samples coherent.
            first['before_ns'], second['before_ns'] = second['before_ns'], first['before_ns']
            first['after_ns'], second['after_ns'] = second['after_ns'], first['after_ns']
            for row in (first, second):
                if row['check_ns'] != '':
                    row['check_ns'] = row['before_ns']
            rows[a], rows[b] = rows[b], rows[a]
            renumber(rows)
            self.rejected(rows, summary)

    def test_shutdown_terminal_and_after_full_container(self):
        rows, summary = fixture()
        shutdown = row_of(rows, 'shutdown', 'owner')
        last_owner = [row for row in rows if row['kind'] == 'owner'][-1]
        shutdown['before_ns'] = last_owner['after_ns'] - 1
        self.rejected(rows, summary)
        rows, summary = fixture()
        shutdown = row_of(rows, 'shutdown', 'client')
        rows.remove(shutdown)
        rows.insert(rows.index(row_of(rows, 'selection')), shutdown)
        shutdown.update(before_ns=4000000, after_ns=4000001)
        renumber(rows)
        self.rejected(rows, summary)

    def test_same_role_order_has_no_cross_role_tolerance(self):
        rows, summary = fixture()
        request = row_of(rows, 'request')
        request['before_ns'] = row_of(rows, 'eligibility', 'pre_call')['after_ns'] - 1
        request['check_ns'] = request['before_ns']
        self.rejected(rows, summary)

    def test_nonfinite_missing_out_of_range_and_boolean_numbers(self):
        for value in ('nan', 'Infinity', '1.5', '', str(1 << 63)):
            rows, summary = fixture()
            row_of(rows, 'selection')['after_ns'] = value
            self.rejected(rows, summary)
        for field in ('accepted', 'schema_version', 'completed_requests'):
            rows, summary = fixture()
            summary[field] = True
            self.rejected(rows, summary)

    def test_capacity_drops_cardinality_and_persistence(self):
        for field, value in (('csv_rows', 1), ('dropped_event_count', 1), ('producer_trace_capacity', 1),
                             ('trace_written', False), ('trace_error', 'write failed'),
                             ('performance_eligible', True), ('emergency_cleanup', True),
                             ('shutdown_acknowledged', False)):
            rows, summary = fixture()
            summary[field] = value
            self.rejected(rows, summary)
        rows, summary = fixture()
        summary['cross_thread_tolerance_ns'] = 1000000000
        self.rejected(rows, summary)

    def test_byte_counts_identity_and_full_verification(self):
        for kind, field, value in (('append', 'byte_count', 12), ('state', 'first_sample', 1),
                                   ('verification', 'verified_bytes', 17), ('verification', 'epoch', 2),
                                   ('request', 'source_status', 3), ('release', 'end_sample', 0)):
            rows, summary = fixture()
            row_of(rows, kind)[field] = value
            self.rejected(rows, summary)

    def test_soft_deadline_equality_still_verifies_granted_bytes(self):
        rows, summary = fixture()
        post = row_of(rows, 'eligibility', 'post_call')
        delta = post['deadline_ns'] - post['before_ns']
        started = False
        for row in rows:
            if row is post:
                started = True
            if started and row['role'] == 'consumer' and row['kind'] != 'shutdown':
                row['before_ns'] += delta
                row['after_ns'] += delta
        post.update(check_ns=post['before_ns'], status='deadline_expired')
        row_of(rows, 'request')['after_ns'] = post['deadline_ns']
        row_of(rows, 'outcome').update(check_ns=post['check_ns'], status='deadline_expired')
        summary['eligible'] = 0
        result = self.check(rows, summary)
        self.assertEqual(result['accepted_grants'], 1)
        self.assertEqual(result['verified_grants'], 1)
        self.assertEqual(result['eligible_requests'], 0)
        post['status'] = 'ok'
        self.rejected(rows, summary)

    def test_pre_call_expiry_is_terminal_without_invented_work(self):
        rows, summary = fixture()
        pre = row_of(rows, 'eligibility', 'pre_call')
        pre.update(before_ns=pre['deadline_ns'], after_ns=pre['deadline_ns'] + 1000,
                   check_ns=pre['deadline_ns'], status='deadline_expired')
        outcome = row_of(rows, 'outcome')
        outcome.update(before_ns=pre['after_ns'] + 1000, after_ns=pre['after_ns'] + 2000,
                       check_ns=pre['check_ns'], status='deadline_expired')
        rows = [row for row in rows if row['role'] == 'producer' or
                row['kind'] in {'selection', 'shutdown', 'outcome'} or row is pre]
        renumber(rows)
        summary.update(csv_rows=len(rows), accepted=0, verified=0, eligible=0)
        result = self.check(rows, summary)
        self.assertEqual(result['request_status_counts'], {'deadline_expired': 1})

    def test_failed_coordinator_reply_keeps_provenance_and_has_no_grant(self):
        for status in ('closed', 'cancelled', 'deadline_expired', 'source_error'):
            rows, summary = fixture('coordinator')
            row_of(rows, 'take').update(status=status, source_status=2 if status == 'source_error' else 0)
            row_of(rows, 'outcome')['status'] = status
            rows = [row for row in rows if row['kind'] not in {'verification', 'release'}]
            renumber(rows)
            summary.update(csv_rows=len(rows), accepted=0, verified=0, eligible=0)
            self.check(rows, summary)
            row_of(rows, 'take')['epoch'] = 2
            self.rejected(rows, summary)

    def test_held_shutdown_release_is_not_a_measured_hold_duration(self):
        rows, summary = fixture('coordinator')
        summary['fault'] = 'held-shutdown'
        row_of(rows, 'release')['phase'] = 'shutdown'
        result = self.check(rows, summary)
        self.assertEqual(result['shutdown_release_count'], 1)
        self.assertIsNone(result['shutdown_censored_requested_holds'])
        self.assertFalse(result['complete_clean_workload'])

    def test_recorded_verifier_failures_are_not_clean_workloads(self):
        for fault in ('byte', 'consumer-exception'):
            rows, summary = fixture()
            summary.update(complete=False, fault=fault, verified=0, eligible=0,
                           failures=[dict(role='consumer', message='Controlled verifier failure')])
            verification = row_of(rows, 'verification')
            verification.update(status='mismatch' if fault == 'byte' else 'aborted',
                                verified_bytes=17 if fault == 'byte' else '')
            if fault == 'byte':
                verification.update(field='byte', expected=31, actual=30, offset=17)
            row_of(rows, 'release')['phase'] = 'failure'
            row_of(rows, 'outcome')['status'] = 'failed'
            self.rejected(rows, summary)
            result = self.check(rows, summary, allow_failure=True)
            self.assertTrue(result['structural_valid'])
            self.assertFalse(result['complete_clean_workload'])
            if fault == 'byte':
                verification['actual'] = 'not a byte'
                self.rejected(rows, summary, allow_failure=True)

    def test_recorded_failed_append_has_no_new_publication(self):
        rows, summary = fixture('none')
        failed = row_of(rows, 'owner', 'timed')
        failed['status'] = 'failed'
        keep = []
        for row in rows:
            if row['kind'] == 'shutdown' or row['after_ns'] < 0 or row is failed or (
                    row['parent_id'] == failed['id'] and row['kind'] in {'generate', 'append'}):
                keep.append(row)
        append = [row for row in keep if row['kind'] == 'append'][-1]
        append.update(status='rejected', source_status=3, byte_count=61439)
        for index, row in enumerate(keep, 1):
            row['id'] = index
        summary.update(complete=False, fault='append', completed_owner_iterations=0, csv_rows=len(keep),
                       failures=[dict(role='producer', message='Controlled rejected append')])
        for field in ('first_sample', 'end_sample', 'accepted_end_sample'):
            summary['source_memory_after'][field] = summary['source_memory_before'][field]
        result = self.check(keep, summary, allow_failure=True)
        self.assertEqual(result['publication_count'], 140)
        self.assertEqual(result['timed_owner_work_ns']['n'], 1)

    def test_trace_read_once_digest_matches_validated_bytes_despite_path_swap(self):
        rows, summary = fixture()
        original = encoded(rows)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trace.csv'
            path.write_bytes(original)
            reader = Path.read_bytes
            calls = []
            def replace_after_read(target):
                calls.append(target)
                data = reader(target)
                target.write_bytes(b'changed after read')
                return data
            with patch.object(Path, 'read_bytes', replace_after_read):
                result = analyze(path, summary)
            self.assertEqual(calls, [path])
            self.assertEqual(result['trace_sha256'], hashlib.sha256(original).hexdigest())
            self.assertNotEqual(path.read_bytes(), original)

    def test_bad_header_truncated_csv_and_unknown_kind(self):
        rows, summary = fixture()
        for raw in (encoded(rows).replace(b'kind,role', b'kind,kind', 1),
                    encoded(rows) + b'publication,producer\n',
                    encoded(rows).replace(b'generate,producer', b'invented,producer', 1)):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'trace.csv'
                path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    analyze(path, summary)

    def test_single_run_measurement_eligibility_is_separate_from_paired_improvement(self):
        for variant in ('none', 'whole', 'coordinator'):
            rows, summary = fixture(variant)
            result = self.check(rows, summary, memory_calibration=calibration(summary))
            self.assertTrue(result['measurement_eligible'])
            self.assertEqual(result['measurement_ineligible_reasons'], [])
            self.assertFalse(result['performance_eligible'])
            self.assertFalse(result['paired_improvement_eligible'])
            self.assertEqual(result['prefill_retained_bytes'], 8388608)
            if variant != 'coordinator':
                accounted = result['source_memory_accounting']['before']
                self.assertEqual(accounted['source_reservation_bytes'], 15728640 + 1184)
                self.assertTrue(accounted['calibrated_heap_already_includes_facade'])

    def test_missing_required_measurements_are_unavailable_not_zero(self):
        for key, reason in (('process_cpu', 'process_cpu_missing'), ('abi', 'abi_sizes_missing'),
                            ('source_memory_before', 'source_memory_before_missing'),
                            ('source_memory_after', 'source_memory_after_missing')):
            rows, summary = fixture('coordinator')
            summary[key] = None
            result = self.check(rows, summary)
            self.assertTrue(result['structural_valid'])
            self.assertFalse(result['measurement_eligible'])
            self.assertIn(reason, result['measurement_ineligible_reasons'])
        rows, summary = fixture()
        result = self.check(rows, summary)
        self.assertIn('whole_memory_calibration_missing', result['measurement_ineligible_reasons'])
        self.assertIsNone(result['source_memory_accounting']['before']['source_reservation_bytes'])

    def test_cpu_parallel_time_can_exceed_wall_time(self):
        rows, summary = fixture('coordinator')
        cpu = summary['process_cpu']
        cpu['elapsed_ns'] = 2 * cpu['wall_elapsed_max_ns']
        cpu['end_value_ns'] = cpu['start_value_ns'] + cpu['elapsed_ns']
        result = self.check(rows, summary)
        self.assertTrue(result['measurement_eligible'])
        self.assertGreater(result['process_cpu']['elapsed_ns'], cpu['wall_elapsed_max_ns'])
        cpu['elapsed_ns'] = cpu['logical_cpu_count'] * (cpu['wall_elapsed_max_ns'] + 20000000) + 1
        cpu['end_value_ns'] = cpu['start_value_ns'] + cpu['elapsed_ns']
        self.rejected(rows, summary)

    def test_cpu_numeric_counter_and_scope_contradictions_rejected(self):
        for field, value in (('elapsed_ns', float('nan')), ('elapsed_ns', -1), ('elapsed_ns', True),
                              ('end_value_ns', 499999999), ('wall_elapsed_max_ns', 1),
                              ('start_before_ns', -20000000), ('end_before_ns', 90000000),
                              ('start_after_ns', float('inf')), ('scope', 'timed_body_only'),
                              ('sanity_allowance_per_logical_cpu_ns', 999999999),
                              ('start_error', 5)):
            with self.subTest(field=field, value=value):
                rows, summary = fixture('coordinator')
                summary['process_cpu'][field] = value
                self.rejected(rows, summary)

    def test_cpu_omitted_worker_tail_rejected_even_if_declared_wall_is_consistent(self):
        rows, summary = fixture('coordinator')
        cpu = summary['process_cpu']
        cpu.update(end_before_ns=90000000, end_after_ns=90000100,
                   wall_elapsed_min_ns=90999900, wall_elapsed_max_ns=91000100)
        self.rejected(rows, summary)

    def test_cpu_errors_and_missing_host_count_block_measurement(self):
        rows, summary = fixture('coordinator')
        cpu = summary['process_cpu']
        cpu.update(valid=False, start_error=5, start_value_ns=None, elapsed_ns=None)
        result = self.check(rows, summary)
        self.assertIsNone(result['process_cpu'])
        self.assertIn('process_cpu_unavailable', result['measurement_ineligible_reasons'])
        rows, summary = fixture('coordinator')
        summary['process_cpu']['logical_cpu_count'] = None
        result = self.check(rows, summary)
        self.assertFalse(result['measurement_eligible'])
        self.assertIn('logical_cpu_count_unavailable', result['measurement_ineligible_reasons'])
        summary['process_cpu'].update(valid=False, start_error=5, elapsed_ns=float('inf'))
        self.rejected(rows, summary)

    def test_windows_storage_unit_is_not_falsely_accounting_resolution(self):
        rows, summary = fixture('coordinator')
        summary['process_cpu'].update(api='GetProcessTimes', api_resolution_ns=100,
                                      resolution_kind='storage_unit_not_accounting_resolution')
        self.assertTrue(self.check(rows, summary)['measurement_eligible'])
        original = copy.deepcopy(summary)
        summary['process_cpu']['end_value_ns'] += 1
        summary['process_cpu']['elapsed_ns'] += 1
        self.rejected(rows, summary)
        summary = original
        summary['process_cpu']['resolution_kind'] = 'measured_accuracy'
        self.rejected(rows, summary)

    def test_true_140_prefill_and_full_retention_are_required(self):
        rows, summary = fixture()
        summary['prefill_iterations'] = 30
        self.rejected(rows, summary)
        for fmt in ('cu8', 'cf32'):
            rows, summary = fixture(fmt=fmt)
            before = summary['source_memory_before']
            self.assertEqual(before['end_sample'], 140 * 30720)
            self.assertEqual((before['end_sample'] - before['first_sample']) * summary['width'], 8388608)
            before['retained_bytes'] -= summary['width']
            self.rejected(rows, summary)

    def test_memory_endpoint_cannot_be_inside_cpu_window_or_name_wrong_source(self):
        for field, value in (('first_sample', 0), ('accepted_end_sample', 99999999),
                              ('before_ns', -999000), ('source_active', False)):
            rows, summary = fixture('coordinator')
            summary['source_memory_before'][field] = value
            if field == 'before_ns':
                summary['source_memory_before']['after_ns'] = value + 100
            self.rejected(rows, summary)
        rows, summary = fixture('coordinator')
        summary['source_memory_after']['slabs']['metadata_bytes'] += 8
        self.rejected(rows, summary)

    def test_candidate_ledger_totals_abi_and_retirement_bounds_are_reconciled(self):
        for group, field, value in (('coordinator', 'current_reserved_bytes', 831),
                                    ('coordinator', 'high_water_reserved_bytes', 999),
                                    ('coordinator', 'control_reservations', 2),
                                    ('coordinator', 'fixed_reservation_bytes', 335),
                                    ('coordinator', 'ledger_allocation_bytes', 0),
                                    ('mailbox_metadata', 'held_reply_object_bytes', 279),
                                    ('slabs', 'metadata_bytes', 131072),
                                    ('slabs', 'payload_limit', 999999999),
                                    ('slabs', 'history_slabs', 136), ('slabs', 'free_slabs', 116)):
            with self.subTest(group=group, field=field):
                rows, summary = fixture('coordinator')
                summary['source_memory_after'][group][field] = value
                self.rejected(rows, summary)
        rows, summary = fixture('coordinator')
        result = self.check(rows, summary)
        self.assertEqual(result['source_memory_accounting']['before']['source_reservation_bytes'],
                         15728640 + 64000 + 128 + 832 + 48)
        summary['abi']['mailbox_bytes'] += 8
        self.rejected(rows, summary)

    def test_outstanding_credits_pins_or_filling_tail_reject_quiescent_claim(self):
        for field in ('snapshot_pinned_slabs', 'live_pinned_slabs', 'outstanding_live_leases', 'filling_bytes'):
            rows, summary = fixture('coordinator')
            summary['source_memory_after']['slabs'][field] = 1
            self.rejected(rows, summary)
        rows, summary = fixture()
        summary['source_memory_after']['whole']['outstanding_count'] = 1
        self.rejected(rows, summary, memory_calibration=calibration(summary))

    def test_whole_calibration_profile_allocation_and_abi_contradictions_rejected(self):
        for field, value in (('format', 'cf32'), ('pointer_bytes', 4), ('payload_bytes', 0),
                              ('captured_allocation_bytes', 15728640), ('metadata_reservation_bytes', 1024),
                              ('live_bytes_after_destroy', 1), ('operational_allocations', 1),
                              ('deallocation_count', 6), ('verified_bytes', 17),
                              ('peak_live_bytes', 999999999), ('live_bytes_after_history_destroy', 999999999)):
            with self.subTest(field=field):
                rows, summary = fixture()
                measured = calibration(summary)
                measured[field] = value
                self.rejected(rows, summary, memory_calibration=measured)

    def test_incomplete_calibration_blocks_measurement_without_claiming_zero_cost(self):
        rows, summary = fixture()
        measured = calibration(summary)
        measured.update(complete=False, verified_bytes=17)
        result = self.check(rows, summary, memory_calibration=measured)
        self.assertFalse(result['measurement_eligible'])
        self.assertIn('whole_memory_calibration_incomplete', result['measurement_ineligible_reasons'])
        unavailable = dict(schema_version=1, kind='whole_source_allocation_calibration', available=False,
                           complete=False, reason='TSan replacement allocation operators unavailable')
        result = self.check(rows, summary, memory_calibration=unavailable)
        self.assertIn('whole_memory_calibration_unavailable', result['measurement_ineligible_reasons'])

    def test_conservative_grant_take_and_verification_bounds(self):
        rows, summary = fixture('coordinator')
        timing = self.check(rows, summary)['request_timing_bounds'][0]
        self.assertEqual(timing['request_begin_ns'], 5004000)
        self.assertEqual(timing['grant_observation_bracket_ns'], {'before_ns': 10270000, 'after_ns': 10280000})
        self.assertEqual(timing['request_to_grant_ns_bounds'], {'lower_ns': 5265000, 'upper_ns': 5277000})
        self.assertEqual(timing['request_to_take_ns_bounds'], {'lower_ns': 5297000, 'upper_ns': 5298000})
        self.assertEqual(timing['request_to_verified_ns_bounds'], {'lower_ns': 5301000, 'upper_ns': 5311000})
        rows, summary = fixture()
        timing = self.check(rows, summary)['request_timing_bounds'][0]
        self.assertEqual(timing['request_to_grant_ns_bounds'], {'lower_ns': 0, 'upper_ns': 1000})
        self.assertIsNone(timing['request_to_take_ns_bounds'])


class NativeObserverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configured = os.environ.get('XERAX_SCREEN_EXE')
        if not configured:
            raise unittest.SkipTest('Native observer explicitly unavailable: XERAX_SCREEN_EXE is not set; synthetic tests only')
        cls.exe = Path(configured).resolve()
        if not cls.exe.is_file():
            raise RuntimeError(f'Configured native observer does not exist: {cls.exe}')
        configured_calibration = os.environ.get('XERAX_MEMORY_CALIBRATION_EXE')
        cls.calibrations = {}
        if configured_calibration:
            calibration_exe = Path(configured_calibration).resolve()
            if not calibration_exe.is_file():
                raise RuntimeError(f'Configured memory calibration does not exist: {calibration_exe}')
            for fmt in ('cu8', 'cf32'):
                process = subprocess.run([str(calibration_exe), '--format', fmt], capture_output=True,
                                         text=True, timeout=45, check=False)
                if process.returncode not in (0, 2):
                    raise RuntimeError(process.stdout + process.stderr)
                measured = json.loads(process.stdout)
                if process.returncode == 0 and measured.get('complete') is not True:
                    raise RuntimeError('Calibration exit success lacks complete evidence')
                if measured.get('available') is False:
                    print('Native allocation calibration explicitly unavailable: ' + measured.get('reason', 'missing reason'))
                cls.calibrations[fmt] = measured

    def run_case(self, variant, fmt='cu8', fault='none'):
        with tempfile.TemporaryDirectory(prefix='xerax-comparison-') as directory:
            trace = Path(directory) / 'trace.csv'
            result = subprocess.run([str(self.exe), '--variant', variant, '--format', fmt,
                                     '--duration-ms', '200', '--fault', fault, '--csv', str(trace)],
                                    capture_output=True, text=True, timeout=45, check=False)
            self.assertIn(result.returncode, (0, 2), msg=result.stdout + result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(result.returncode, 0 if summary['complete'] else 2)
            checked = analyze(trace, summary, allow_failure=True, memory_calibration=self.calibrations.get(fmt))
            self.assertTrue(checked['structural_valid'])
            self.assertFalse(checked['performance_eligible'])
            parsed = list(csv.DictReader(io.StringIO(trace.read_text(encoding='utf-8'))))
            return checked, summary, parsed

    def test_clean_all_variants_formats(self):
        for variant in ('none', 'whole', 'coordinator'):
            for fmt in ('cu8', 'cf32'):
                with self.subTest(variant=variant, fmt=fmt):
                    result, summary, _ = self.run_case(variant, fmt)
                    self.assertTrue(summary['complete'])
                    self.assertEqual(result['accepted_grants'], result['verified_grants'])
                    expected = variant == 'coordinator' or bool(self.calibrations.get(fmt, {}).get('complete'))
                    self.assertEqual(result['measurement_eligible'], expected)

    def test_producer_faults_preserve_partial_failure_evidence(self):
        for variant in ('none', 'whole', 'coordinator'):
            for fault in ('append', 'producer-exception'):
                with self.subTest(variant=variant, fault=fault):
                    _, summary, rows = self.run_case(variant, fault=fault)
                    self.assertFalse(summary['complete'])
                    self.assertTrue(summary['failures'])
                    self.assertEqual(sum(row['kind'] == 'publication' for row in rows), 140)

    def test_verifier_faults_release_actual_grants(self):
        for variant in ('whole', 'coordinator'):
            for fault in ('byte', 'consumer-exception'):
                with self.subTest(variant=variant, fault=fault):
                    _, summary, rows = self.run_case(variant, fault=fault)
                    self.assertFalse(summary['complete'])
                    verification = next(row for row in rows if row['kind'] == 'verification')
                    self.assertEqual(verification['status'], 'mismatch' if fault == 'byte' else 'aborted')
                    self.assertTrue(any(row['kind'] == 'release' and row['phase'] == 'failure' for row in rows))

    def test_delayed_post_publication_stamp_is_accepted(self):
        for variant in ('whole', 'coordinator'):
            with self.subTest(variant=variant):
                _, summary, rows = self.run_case(variant, fault='publication-pause')
                self.assertTrue(summary['complete'])
                selection = next(row for row in rows if row['kind'] == 'selection')
                publication = next(row for row in rows if row['kind'] == 'publication' and row['event_id'] == selection['event_id'])
                tolerance = summary['cross_thread_tolerance_ns']
                self.assertEqual(int(selection['event_id']), 141)
                self.assertGreaterEqual(int(publication['after_ns']) + tolerance, int(selection['after_ns']))
                self.assertLessEqual(int(publication['before_ns']), int(selection['before_ns']) + tolerance)

    def test_pending_and_held_shutdown(self):
        for fault in ('pending-shutdown', 'held-shutdown'):
            with self.subTest(fault=fault):
                result, summary, rows = self.run_case('coordinator', fault=fault)
                self.assertTrue(summary['complete'])
                self.assertTrue(summary['shutdown_acknowledged'])
                if fault == 'pending-shutdown':
                    self.assertEqual(result['accepted_grants'], 0)
                    self.assertTrue(any(row['kind'] == 'outcome' and row['status'] == 'closed' for row in rows))
                else:
                    self.assertEqual(result['shutdown_release_count'], 1)
                    self.assertEqual(result['accepted_grants'], result['verified_grants'])
                self.assertIsNone(result['shutdown_censored_requested_holds'])


if __name__ == '__main__':
    unittest.main()
