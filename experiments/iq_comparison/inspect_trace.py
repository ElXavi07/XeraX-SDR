"""Validate schema-3 source publication evidence, not comparative performance.

All checks use explicit exceptions and remain active under ``python -O``.
The trace is read once: its digest identifies exactly the bytes validated.
"""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path

COLUMNS = [
    'kind', 'role', 'id', 'parent_id', 'phase', 'status', 'source_status',
    'event_id', 'request_id', 'stream_id', 'epoch', 'rate_hz', 'frequency_hz',
    'width', 'pool_id', 'generation', 'first_sample', 'end_sample', 'byte_count',
    'before_ns', 'after_ns', 'due_ns', 'check_ns', 'deadline_ns', 'verified_bytes',
    'field', 'expected', 'actual', 'offset',
]
NUMBERS = set(COLUMNS) - {'kind', 'role', 'phase', 'status', 'field', 'expected', 'actual'}
SIGNED = {'before_ns', 'after_ns', 'due_ns', 'check_ns', 'deadline_ns'}
META = ('stream_id', 'epoch', 'rate_hz', 'frequency_hz', 'width', 'pool_id', 'generation')
SOURCE = META + ('first_sample', 'end_sample', 'byte_count')
KINDS = {'owner', 'generate', 'append', 'state', 'publication', 'service', 'reclaim',
         'selection', 'request', 'take', 'verification', 'release', 'shutdown', 'outcome', 'eligibility'}
OWNER_CHILDREN = {'generate', 'append', 'state', 'publication', 'service', 'reclaim'}
VARIANTS = {'none', 'whole', 'coordinator'}
FAULTS = {'none', 'append', 'byte', 'publication-pause', 'producer-exception', 'consumer-exception',
          'pending-shutdown', 'held-shutdown'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, name, *, minimum=0):
    require(type(value) is int and minimum <= value <= (1 << 64) - 1,
            f'{name} must be an integer in its declared range')
    return value


def distribution(values):
    if not values:
        return None
    values = sorted(values)
    return {'n': len(values), 'p50': values[math.ceil(.50 * len(values)) - 1],
            'p95': values[math.ceil(.95 * len(values)) - 1],
            'p99': values[math.ceil(.99 * len(values)) - 1], 'max': values[-1]}


def parse_rows(raw):
    try:
        stream = io.StringIO(raw.decode('utf-8'), newline='')
    except UnicodeDecodeError as error:
        raise ValueError('Trace is not UTF-8') from error
    reader = csv.DictReader(stream)
    require(reader.fieldnames == COLUMNS, 'Unknown schema-3 trace columns')
    rows = []
    for row in reader:
        require(set(row) == set(COLUMNS) and all(value is not None for value in row.values()),
                'Malformed or truncated trace row')
        require(row['kind'] in KINDS, 'Unknown event kind')
        for field in NUMBERS:
            value = row[field]
            if value == '':
                row[field] = None
                continue
            digits = value[1:] if field in SIGNED and value.startswith('-') else value
            require(digits.isascii() and digits.isdigit(), f'Invalid/nonfinite {field}')
            number = int(value)
            minimum, maximum = (-(1 << 63), (1 << 63) - 1) if field in SIGNED else (0, (1 << 64) - 1)
            require(minimum <= number <= maximum, f'Out-of-range {field}')
            row[field] = number
        rows.append(row)
    return rows


def same_fields(first, second, fields, context):
    require(all(first[key] == second[key] for key in fields), context)


def bracket(row):
    require(row['before_ns'] is not None and row['after_ns'] is not None,
            f"Missing {row['kind']} operation bracket")
    require(row['before_ns'] <= row['after_ns'], f"Reversed {row['kind']} operation bracket")


def one(rows, kind, *, required=True):
    matches = [row for row in rows if row['kind'] == kind]
    require(len(matches) <= 1 and (not required or len(matches) == 1), f'Missing/duplicate {kind} event')
    return matches[0] if matches else None


def _summary(summary):
    require(type(summary) is dict and type(summary.get('schema_version')) is int and summary['schema_version'] == 3,
            'Expected schema_version 3')
    require(summary.get('variant') in VARIANTS and summary.get('format') in {'cu8', 'cf32'}, 'Unknown profile')
    require(summary.get('fault') in FAULTS, 'Unknown fault control')
    require(type(summary.get('complete')) is bool and type(summary.get('failures')) is list,
            'Missing completion/failure declaration')
    require(summary.get('trace_written') is True and summary.get('trace_error') is None,
            'Trace persistence is not confirmed')
    require(integer(summary.get('dropped_event_count'), 'dropped_event_count') == 0,
            f"Dropped trace events prevent validation: {summary.get('dropped_event_count')}")
    duration = integer(summary.get('duration_ms'), 'duration_ms')
    require(100 <= duration <= 60000 and duration % 10 == 0, 'Invalid duration profile')
    for key, expected in {'producer_period_ns': 10000000, 'request_period_ns': 100000000,
                          'snapshot_samples': 768000, 'deadline_ns': 50000000,
                          'rate_hz': 3072000, 'stream_id': 1, 'epoch': 1,
                          'frequency_hz': 451100000}.items():
        require(type(summary.get(key)) is int and summary[key] == expected, f'Unexpected {key} profile')
    require(summary.get('width') == (2 if summary['format'] == 'cu8' else 8), 'Format/width mismatch')
    expected_requests = 0 if summary['variant'] == 'none' else (duration + 94) // 100
    require(summary.get('expected_owner_iterations') == duration // 10 and
            summary.get('expected_requests') == expected_requests, 'Expected workload cardinality mismatch')
    for field in ('expected_owner_iterations', 'expected_requests', 'completed_owner_iterations',
                  'completed_requests', 'accepted', 'verified', 'eligible', 'csv_rows',
                  'producer_trace_capacity', 'consumer_trace_capacity', 'trace_reserved_bytes'):
        integer(summary.get(field), field)
    require(summary.get('prefill_iterations') == 30 and type(summary.get('shutdown_acknowledged')) is bool,
            'Missing warmup/shutdown declaration')
    require(integer(summary.get('input_buffer_bytes'), 'input_buffer_bytes') == 30720 * summary['width'],
            'Input buffer declaration does not match bounded ingress')
    integer(summary.get('publication_descriptor_bytes'), 'publication_descriptor_bytes', minimum=1)
    clock = summary.get('clock')
    require(type(clock) is dict and clock.get('is_steady') is True and type(clock.get('provenance')) is str and
            bool(clock['provenance']), 'Missing steady-clock provenance')
    integer(clock.get('period_num'), 'clock period numerator', minimum=1)
    integer(clock.get('period_den'), 'clock period denominator', minimum=1)
    tolerance = integer(summary.get('cross_thread_tolerance_ns'), 'cross_thread_tolerance_ns', minimum=1)
    qpc = clock.get('qpc_frequency_hz')
    require('qpc_frequency_hz' in clock, 'Missing explicit clock availability')
    if qpc is not None:
        integer(qpc, 'QPC frequency', minimum=1)
    require(tolerance == max(1000, (1000000000 + qpc - 1) // qpc if qpc else 0),
            'Cross-thread tolerance differs from declared observer profile')
    require(summary.get('performance_eligible') is False, 'Observer cannot declare comparative performance eligibility')
    require(summary.get('emergency_cleanup') is False, 'Untraced emergency cleanup prevents validation')
    integer(summary.get('secondary_failure_count'), 'secondary_failure_count')
    for failure in summary['failures']:
        require(type(failure) is dict and failure.get('role') in {'producer', 'consumer', 'trace'} and
                type(failure.get('message')) is str and bool(failure['message']), 'Malformed failure context')
    if summary['complete']:
        require(not summary['failures'], 'Complete trace reports a failure')
    else:
        require(bool(summary['failures']), 'Incomplete trace needs a failure explanation')
    return tolerance


def analyze(trace, summary, *, allow_failure=False):
    """Validate one saved observer trace; no receiver or benchmark is launched."""
    tolerance = _summary(summary)
    require(summary['complete'] or allow_failure, 'Failed workload requires allow_failure')
    raw = Path(trace).read_bytes()
    rows = parse_rows(raw)
    require(len(rows) == summary['csv_rows'], 'Trace row cardinality mismatch')
    require(len(rows) <= summary['producer_trace_capacity'] + summary['consumer_trace_capacity'],
            'Trace exceeds declared fixed capacities')
    roles = {}
    for row in rows:
        require(row['role'] in {'producer', 'consumer'}, 'Unknown role')
        require(row['id'] is not None, 'Missing role event identity')
        bracket(row)
        roles.setdefault(row['role'], []).append(row)
    for role, events in roles.items():
        ids = [row['id'] for row in events]
        require(ids == list(range(1, len(ids) + 1)),
                'Duplicate, missing or regressing per-role row identity')
        require(len(events) <= summary[f'{role}_trace_capacity'], f'{role} trace capacity exceeded')
        # Owner intervals intentionally contain their children. Leaves alone
        # describe nonoverlapping calls in each sequential worker.
        leaves = [row for row in events if row['kind'] != 'owner']
        for previous, current in zip(leaves, leaves[1:]):
            require(previous['after_ns'] <= current['before_ns'], f'Reversed/overlapping {role} event order')
    owners = [row for row in rows if row['kind'] == 'owner']
    owner_by_id = {row['id']: row for row in owners}
    require(len(owner_by_id) == len(owners), 'Duplicate owner identity')
    children = {key: [] for key in owner_by_id}
    for row in rows:
        if row['kind'] in OWNER_CHILDREN:
            require(row['role'] == 'producer' and row['parent_id'] in owner_by_id,
                    'Producer operation lacks enclosing owner iteration')
            parent = owner_by_id[row['parent_id']]
            require(parent['before_ns'] <= row['before_ns'] <= row['after_ns'] <= parent['after_ns'],
                    'Producer work interval omits a recorded generation/append/service/publication operation')
            children[row['parent_id']].append(row)
        else:
            require(row['parent_id'] is None, 'Unexpected parent identity')
        if row['kind'] == 'owner':
            require(row['role'] == 'producer' and row['phase'] in {'prefill', 'timed', 'drain'}, 'Invalid owner phase')
        elif row['kind'] == 'shutdown':
            require((row['role'], row['phase']) in {('producer', 'owner'), ('consumer', 'client')},
                    'Unknown shutdown role')
        elif row['kind'] not in OWNER_CHILDREN:
            require(row['role'] == 'consumer', 'Consumer event has wrong role')
    for previous, current in zip(owners, owners[1:]):
        require(previous['after_ns'] <= current['before_ns'], 'Owner iterations overlap or reverse')
    timed = [row for row in owners if row['phase'] == 'timed']
    prefill = [row for row in owners if row['phase'] == 'prefill']
    drain = [row for row in owners if row['phase'] == 'drain']
    require(len(prefill) == 30 and len(drain) <= 1000, 'Warmup/drain cardinality mismatch')
    require(sum(row['status'] == 'ok' for row in timed) == summary['completed_owner_iterations'] and
            len(timed) <= summary['expected_owner_iterations'],
            'Timed owner cardinality mismatch')
    if summary['complete']:
        require(len(timed) == summary['expected_owner_iterations'], 'Complete workload misses producer work')
    for index, owner in enumerate(timed):
        require(owner['due_ns'] == index * summary['producer_period_ns'], 'Producer schedule mismatch')
    # Detailed owner, source, request and shutdown invariants are checked below.
    return _events(rows, summary, raw, tolerance, owners, children, timed)


def _events(rows, summary, raw, tolerance, owners, children, timed):
    def metadata(row):
        for key in META[:5]:
            require(row[key] == summary[key], f'Source identity mismatch: {key}')
        if summary['variant'] == 'coordinator':
            require(row['pool_id'] is not None and row['pool_id'] > 0 and
                    row['generation'] is not None and row['generation'] > 0, 'Missing real coordinator source identity')
        else:
            require(row['pool_id'] is None and row['generation'] is None, 'Invented unobserved whole-copy source identity')

    def interval(row):
        metadata(row)
        require(row['first_sample'] is not None and row['end_sample'] is not None and
                row['first_sample'] <= row['end_sample'] and
                row['byte_count'] == (row['end_sample'] - row['first_sample']) * summary['width'],
                'Source interval/byte count mismatch')

    publications = {}
    frontier = 0
    prior_identity = None
    phases = [row['phase'] for row in owners]
    phase_order = {'prefill': 0, 'timed': 1, 'drain': 2}
    require([phase_order[value] for value in phases] == sorted(phase_order[value] for value in phases),
            'Owner workload phases regress')
    failed_timed = [row for row in timed if row['status'] != 'ok']
    require(len(failed_timed) <= 1 and (not failed_timed or failed_timed[-1] is timed[-1]),
            'Producer continues after failed timed iteration')
    for owner in owners:
        require(owner['status'] in {'ok', 'failed'}, 'Owner lacks a terminal status')
        require(owner['status'] == 'ok' or not summary['complete'], 'Complete run has a failed owner iteration')
        operations = children[owner['id']]
        by_kind = {kind: [row for row in operations if row['kind'] == kind] for kind in OWNER_CHILDREN}
        services = by_kind['service']
        needs_service = summary['variant'] == 'coordinator' and owner['phase'] in {'timed', 'drain'} and owner['status'] == 'ok'
        require(len(services) == (3 if needs_service else 0), 'Missing or excess recorded owner service phases')
        if services:
            require([row['phase'] for row in services] == ['step1', 'step2', 'step3'], 'Service phase identity mismatch')
            for service in services:
                require(service['check_ns'] == service['before_ns'] and service['request_id'] is None,
                        'Service clock check or unattributed request mapping is invalid')
                require(service['field'] in {'idle', 'submitting', 'pending', 'acquired', 'granted',
                                            'ready', 'taking', 'held', 'consumed', 'closed'}, 'Unknown service stage')
                require(service['status'] in {'ok', 'empty', 'busy', 'closed'}, 'Unexpected service result')
        require(len(by_kind['reclaim']) == (1 if needs_service else 0), 'Missing or invented explicit owner reclamation')
        if owner['status'] == 'ok':
            expected_order = [] if owner['phase'] == 'drain' else ['generate', 'append', 'state', 'publication']
            if needs_service:
                expected_order += ['service', 'service', 'service', 'reclaim']
            require([row['kind'] for row in operations] == expected_order, 'Producer semantic operation order mismatch')
        if owner['phase'] == 'drain':
            require(summary['variant'] == 'coordinator' and not any(by_kind[key] for key in ('generate', 'append', 'state', 'publication')),
                    'Drain invents new source input/publication')
            continue
        generated = one(operations, 'generate')
        require(generated['status'] == 'ok' and generated['first_sample'] == frontier and
                generated['end_sample'] == frontier + 30720 and generated['byte_count'] == 30720 * summary['width'],
                'Generation does not describe exact next source block')
        appended = one(operations, 'append', required=owner['status'] == 'ok')
        state = one(operations, 'state', required=owner['status'] == 'ok')
        published = one(operations, 'publication', required=owner['status'] == 'ok')
        if appended is None:
            require(state is None and published is None, 'Source publication lacks an append')
            continue
        metadata(appended)
        require(appended['first_sample'] == frontier and appended['end_sample'] == frontier + 30720 and
                generated['after_ns'] <= appended['before_ns'], 'Append source sequence/order mismatch')
        require(appended['source_status'] is not None, 'Append lacks actual core status')
        if appended['status'] == 'rejected':
            require(appended['source_status'] != 0 and owner['status'] == 'failed' and state is None and published is None,
                    'Rejected append publishes unavailable replacement samples')
            require(appended['byte_count'] is not None and 0 <= appended['byte_count'] <= 30720 * summary['width'],
                    'Rejected append lacks bounded actual attempted bytes')
            continue
        require(appended['status'] == 'ok' and appended['source_status'] == 0 and
                appended['byte_count'] == 30720 * summary['width'], 'Successful append has invalid input/status')
        frontier += 30720
        require(state is not None and published is not None, 'Accepted input has missing source publication observations')
        interval(state); interval(published)
        require(state['status'] == 'ok' and state['first_sample'] == max(0, frontier - 8388608 // summary['width']) and
                state['end_sample'] == frontier, 'Observed source frontier/retention contradicts accepted input')
        require(appended['after_ns'] <= state['before_ns'] and state['after_ns'] <= published['before_ns'],
                'Publication precedes observed appended source state')
        same_fields(state, published, SOURCE + ('event_id',), 'Publication identity differs from initialized source descriptor')
        require(published['event_id'] == len(publications) + 1, 'Missing/duplicate publication version')
        require(published['phase'] == 'release_store' and published['status'] in {'ok', 'failed'}, 'Unknown publication operation')
        require(published['status'] == 'ok' or not summary['complete'], 'Complete run reports failed publication observation')
        identity = tuple(published[field] for field in META)
        require(prior_identity is None or identity == prior_identity, 'One-epoch profile changes source identity')
        prior_identity = identity
        publications[published['event_id']] = published
    require(publications, 'Missing source publication provenance')

    shutdowns = [row for row in rows if row['kind'] == 'shutdown']
    owner_shutdown = [row for row in shutdowns if row['role'] == 'producer']
    client_shutdown = [row for row in shutdowns if row['role'] == 'consumer']
    require(len(owner_shutdown) == 1 and len(client_shutdown) == (0 if summary['variant'] == 'none' else 1),
            'Missing/duplicate worker shutdown observation')
    require(all(row['status'] == 'ok' for row in shutdowns), 'Shutdown observation incomplete')
    for shutdown in shutdowns:
        role_rows = [row for row in rows if row['role'] == shutdown['role']]
        require(role_rows[-1] is shutdown and all(row['after_ns'] <= shutdown['before_ns'] for row in role_rows[:-1]),
                'Shutdown precedes work or is not the final role observation')
    if summary['complete']:
        require(summary['shutdown_acknowledged'], 'Complete workload lacks shutdown acknowledgement')
    requests = {}
    for row in rows:
        if row['role'] == 'consumer' and row['kind'] != 'shutdown':
            require(row['request_id'] is not None and row['request_id'] > 0, 'Missing client request identity')
            requests.setdefault(row['request_id'], []).append(row)
    require(list(requests) == list(range(1, len(requests) + 1)) and len(requests) <= summary['expected_requests'],
            'Missing, duplicate or excess scheduled request identity')
    if summary['complete']:
        require(len(requests) == summary['expected_requests'], 'Complete run omits a scheduled request')
    outcomes, grants, verifications, releases, ages, source_intervals = [], [], [], [], [], []
    transition_rows = [row for row in rows if row['kind'] == 'service' and row['status'] == 'ok' and
                       row['field'] in {'acquired', 'granted', 'ready'}]
    transition_index = 0
    previous_selected = 0
    for request_id, events in requests.items():
        selection = one(events, 'selection')
        require(selection['phase'] == 'acquire_load' and selection['status'] == 'ok', 'Unknown source selection operation')
        require(selection['due_ns'] == 5000000 + (request_id - 1) * summary['request_period_ns'], 'Client schedule mismatch')
        event_id = selection['event_id']
        require(event_id in publications, 'Selection observes unknown/unpublished source identity')
        require(event_id >= previous_selected, 'Consumer publication identity regresses')
        previous_selected = event_id
        published = publications[event_id]
        same_fields(selection, published, SOURCE, 'Selected source descriptor does not match actual publication identity')
        # Store/load are points somewhere inside these brackets. An observed
        # release/acquire identity permits overlap; the producer post-stamp can
        # legitimately follow the consumer's selection and verification.
        require(published['before_ns'] <= selection['after_ns'] + tolerance,
                'Selection necessarily precedes its publication even with clock tolerance')
        first, end = selection['end_sample'] - summary['snapshot_samples'], selection['end_sample']
        require(first >= selection['first_sample'], 'Selected publication cannot cover requested snapshot')
        requested = {**selection, 'first_sample': first, 'end_sample': end,
                     'byte_count': summary['snapshot_samples'] * summary['width']}
        deadline = selection['after_ns'] + summary['deadline_ns']
        ages.append({'request_id': request_id, 'event_id': event_id,
                     'lower_ns': max(0, selection['before_ns'] - published['after_ns'] - tolerance),
                     'upper_ns': max(0, selection['after_ns'] - published['before_ns'] + tolerance),
                     'newer_completed_publications': sum(pub['event_id'] > event_id and pub['after_ns'] <= selection['before_ns']
                                                          for pub in publications.values())})
        source_intervals.append({'request_id': request_id, 'first_sample': first, 'end_sample': end,
                                 'stream_id': selection['stream_id'], 'epoch': selection['epoch'],
                                 'rate_hz': selection['rate_hz'], 'frequency_hz': selection['frequency_hz'], 'width': selection['width']})
        eligibility = [row for row in events if row['kind'] == 'eligibility']
        require([row['phase'] for row in eligibility] in (['pre_call'], ['pre_call', 'post_call']),
                'Missing/duplicate eligibility check')
        for row in eligibility:
            same_fields(row, requested, SOURCE + ('event_id',), 'Eligibility check changed selected request')
            require(row['check_ns'] == row['before_ns'] and row['deadline_ns'] == deadline,
                    'Eligibility clock/deadline mapping is invalid')
            require(row['status'] == ('deadline_expired' if row['check_ns'] >= deadline else 'ok'),
                    'Eligibility result contradicts supplied clock equality rule')
        require(selection['after_ns'] <= eligibility[0]['before_ns'], 'Eligibility precedes source selection')
        call = one(events, 'request', required=eligibility[0]['status'] == 'ok')
        require((call is not None) == (eligibility[0]['status'] == 'ok'),
                'Request was attempted despite expired pre-call eligibility')
        take = one(events, 'take', required=False)
        verification = one(events, 'verification', required=False)
        release = one(events, 'release', required=False)
        outcome = one(events, 'outcome')
        same_fields(outcome, requested, SOURCE + ('event_id',), 'Outcome changed request provenance')
        require(outcome['deadline_ns'] == deadline and outcome['check_ns'] == eligibility[-1]['check_ns'],
                'Outcome mislabels a supplied eligibility check')
        require(outcome['status'] in {'ok', 'deadline_expired', 'busy', 'source_error', 'closed', 'cancelled', 'failed',
                                     'counter_exhausted', 'tick_regression', 'not_current', 'too_late'}, 'Unknown request outcome')
        outcomes.append(outcome)
        grant = None
        if call:
            require(len(eligibility) == 2 and call['phase'] == ('submit' if summary['variant'] == 'coordinator' else 'whole_copy'),
                    'Request operation lacks matching adapter/post-call check')
            same_fields(call, requested, SOURCE + ('event_id',), 'Request changed selected source interval')
            require(call['check_ns'] == call['before_ns'] and call['deadline_ns'] == deadline, 'Request clock/deadline mismatch')
            require(eligibility[0]['after_ns'] <= call['before_ns'], 'Request precedes pre-call eligibility check')
            require(call['status'] in {'ok', 'busy', 'source_error', 'closed', 'counter_exhausted', 'tick_regression',
                                      'deadline_expired'},
                    'Unknown request operation status')
            if summary['variant'] == 'coordinator':
                require((take is not None) == (call['status'] == 'ok'), 'Admitted coordinator request is not taken exactly once')
                if call['status'] == 'ok':
                    require(call['check_ns'] < deadline,
                            'Coordinator admitted request at or after its supplied deadline')
                if take:
                    require(take['phase'] == 'mailbox' and call['after_ns'] <= take['before_ns'],
                            'Take precedes admission or lacks mailbox phase')
                    require(take['status'] in {'ok', 'deadline_expired', 'source_error', 'closed', 'cancelled',
                                               'not_current', 'tick_regression', 'too_late'}, 'Unknown take status')
                    same_fields(take, requested, SOURCE + ('event_id',), 'Taken reply source provenance mismatch')
                    require(take['check_ns'] == take['before_ns'] and take['deadline_ns'] == deadline,
                            'Take clock/deadline mapping is invalid')
                    # A single sequential client and one mailbox slot make the
                    # ordered transition triplets uniquely necessary, although
                    # no row identifies an exact internal grant instant. Stores
                    # may be observed before the service/submit post-stamp.
                    transitions = transition_rows[transition_index:transition_index + 3]
                    require([row['field'] for row in transitions] == ['acquired', 'granted', 'ready'],
                            'Taken reply lacks unique owner acquisition/grant/ready evidence')
                    require(all(row['after_ns'] + tolerance >= call['before_ns'] and
                                row['before_ns'] <= take['after_ns'] + tolerance for row in transitions),
                            'Owner transitions cannot lie causally between admission and take')
                    transition_index += 3
                    if take['status'] == 'ok':
                        require(take['check_ns'] < deadline and
                                all(row['check_ns'] < deadline for row in transitions),
                                'Successful coordinator grant contradicts supplied deadline checks')
                        grant = take
            else:
                require(take is None, 'Whole-copy adapter invents a coordinator take')
                if call['status'] == 'ok': grant = call
            require((take or call)['after_ns'] <= eligibility[-1]['before_ns'],
                    'Post-call eligibility check precedes actual operation return')
        else:
            require(len(eligibility) == 1 and take is None and eligibility[0]['status'] == 'deadline_expired',
                    'Missing request is not explained by pre-call expiry')
        if grant is None:
            require(verification is None and release is None, 'Rejected request invents a granted payload')
            expected_outcome = (take or call or eligibility[0])['status']
            require(outcome['status'] == expected_outcome, 'Rejected request outcome contradicts observed operation')
            require(eligibility[-1]['after_ns'] <= outcome['before_ns'], 'Outcome precedes eligibility check')
            continue
        grants.append(grant)
        require(grant['source_status'] == 0, 'Successful grant lacks successful core status')
        require(verification is not None and release is not None, 'Accepted grant lacks verification or ownership release')
        require(verification['status'] in {'ok', 'mismatch', 'aborted'} and verification['phase'] == 'exact_bytes',
                'Accepted grant has unknown verification result')
        if verification['status'] == 'ok':
            same_fields(verification, requested, SOURCE + ('event_id',), 'Verified payload provenance mismatch')
            require(verification['verified_bytes'] == requested['byte_count'], 'Successful verification omits accepted bytes')
        elif verification['status'] == 'mismatch':
            require(not summary['complete'] and verification['field'] and verification['expected'] != verification['actual'],
                    'Mismatch lacks explicit unequal expected/actual failure evidence')
            require(verification['verified_bytes'] is not None and 0 <= verification['verified_bytes'] <= requested['byte_count'],
                    'Mismatch lacks bounded verified-prefix count')
            if verification['field'] == 'byte':
                require(verification['offset'] is not None and 0 <= verification['offset'] < requested['byte_count'] and
                        verification['verified_bytes'] == verification['offset'], 'Byte mismatch offset/prefix is inconsistent')
                require(all(value.isascii() and value.isdigit() and 0 <= int(value) <= 255
                            for value in (verification['expected'], verification['actual'])),
                        'Byte mismatch diagnostics are not numeric bytes')
        else:
            require(not summary['complete'], 'Complete run contains aborted verification')
            require(verification['verified_bytes'] is None or 0 <= verification['verified_bytes'] <= requested['byte_count'],
                    'Aborted verification invents an impossible prefix')
        require(verification['deadline_ns'] == deadline and eligibility[-1]['after_ns'] <= verification['before_ns'],
                'Verification precedes post-call eligibility check')
        same_fields(release, requested, SOURCE + ('event_id',), 'Release changed original grant provenance')
        require(release['status'] == 'ok' and release['phase'] in {'normal', 'failure', 'shutdown'} and
                verification['after_ns'] <= release['before_ns'], 'Invalid or premature ownership release')
        require(outcome['before_ns'] >= release['after_ns'], 'Finished outcome precedes ownership cleanup')
        if verification['status'] != 'ok':
            require(release['phase'] == 'failure' and outcome['status'] == 'failed', 'Failed verification is reported as successful work')
        else:
            expected_outcome = 'deadline_expired' if eligibility[-1]['check_ns'] >= deadline else 'ok'
            require(outcome['status'] == expected_outcome, 'Grant eligibility mislabels soft post-call deadline')
        verifications.append(verification); releases.append(release)
    require(len(outcomes) == summary['completed_requests'], 'Completed request cardinality mismatch')
    require(transition_index == len(transition_rows), 'Unconsumed owner transition cycle lacks a taken request')
    require(len(grants) == summary['accepted'] and sum(row['status'] == 'ok' for row in verifications) == summary['verified'] and
            sum(row['status'] == 'ok' for row in outcomes) == summary['eligible'], 'Grant/verification/outcome summary mismatch')
    for release, next_grant in zip(releases, grants[1:]):
        require(release['after_ns'] <= next_grant['before_ns'], 'Accepted grants overlap the single ownership credit')
    if summary['complete']:
        require(len(outcomes) == summary['expected_requests'], 'Complete workload misses request outcomes')
    complete_clean = summary['complete'] and summary['fault'] == 'none'
    duration = lambda row: row['after_ns'] - row['before_ns']
    generation = {owner['id']: sum(duration(row) for row in children[owner['id']] if row['kind'] == 'generate') for owner in timed}
    return {
        'schema_version': 3, 'scope': 'publication instrumentation correctness only',
        'structural_valid': True, 'complete_clean_workload': complete_clean, 'performance_eligible': False,
        'performance_ineligible_reasons': ['preregistered_comparison_not_validated', 'instrumentation_correctness_only'],
        'trace_sha256': hashlib.sha256(raw).hexdigest(), 'csv_rows': len(rows), 'dropped_event_count': 0,
        'publication_count': len(publications), 'source_intervals': source_intervals,
        'publication_to_selection_ns_bounds': ages,
        'accepted_grants': len(grants), 'verified_grants': summary['verified'], 'eligible_requests': summary['eligible'],
        'completed_requests': len(outcomes), 'request_status_counts': {status: sum(row['status'] == status for row in outcomes)
                                                                    for status in sorted({row['status'] for row in outcomes})},
        'timed_owner_work_ns': distribution([duration(row) for row in timed]),
        'timed_generation_ns': distribution(list(generation.values())),
        'timed_other_owner_work_ns': distribution([duration(row) - generation[row['id']] for row in timed]),
        'owner_work_over_10ms': sum(duration(row) > 10000000 for row in timed),
        'owner_signed_wake_offset_ns': distribution([row['before_ns'] - row['due_ns'] for row in timed]),
        'owner_finished_after_next_block': sum(row['after_ns'] > row['due_ns'] + 10000000 for row in timed),
        'drain_owner_work_ns': distribution([duration(row) for row in owners if row['phase'] == 'drain']),
        'verification_ns': distribution([duration(row) for row in verifications]),
        'selection_to_verified_ns': distribution([verification['after_ns'] - one(requests[verification['request_id']], 'selection')['before_ns']
                                                   for verification in verifications if verification['status'] == 'ok']),
        'shutdown_release_count': sum(row['phase'] == 'shutdown' for row in releases),
        'shutdown_censored_requested_holds': None, 'failures': summary['failures'],
        'limits': [
            'Brackets constrain store/load feasibility; they are not exact linearization timestamps.',
            'Cross-thread clock tolerance is declared, not independently calibrated by this validator.',
            'Observed newer publications do not impose an invented wall-clock happens-before relationship.',
            'Owner interval contains every recorded child; a trace cannot prove that source code omitted no work.',
            'Unattributed coordinator service brackets do not provide exact per-request grant latency.',
            'Ordered owner transition triplets establish necessary one-slot feasibility, not exact internal linearization times.',
            'This is not a full coordinator state-machine replay; terminal acknowledgement is observer-reported.',
            'Eligibility checks use supplied clock samples and do not enforce hard deadlines.',
            'This profile releases immediately after verification; shutdown labels are not measured requested-hold censoring.',
            'Known opaque source bytes are not RF, protocol, intelligibility or decoding-speed measurements.',
        ],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary', type=Path, required=True)
    parser.add_argument('--trace', type=Path, required=True)
    parser.add_argument('--allow-failure', action='store_true')
    args = parser.parse_args()
    print(json.dumps(analyze(args.trace, json.loads(args.summary.read_bytes()), allow_failure=args.allow_failure), indent=2))
