"""Schema-5 notification-sidecar checks; no comparative performance claim.

The source and sidecar are each captured once. The frozen schema-4 checker sees
the same source bytes through a private temporary copy, with only the explicitly
declared schema-version projection. No count, status or timing is normalized.
All verification uses exceptions, including under Python -O.
"""
import argparse
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile

_spec = importlib.util.spec_from_file_location(
    '_xerax_frozen_screen', Path(__file__).resolve().parents[1] / 'iq_screen' / 'inspect_screen.py')
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
require, integer = base.require, base.integer

COLUMNS = ['kind', 'phase', 'role', 'id', 'request_id', 'event_id', 'token_domain',
           'token_generation', 'parent_owner_id', 'parent_service_id', 'base_row_id',
           'before_ns', 'after_ns', 'status', 'deadline_ns', 'stage_loads', 'yield_calls']
WORDS = {'kind', 'phase', 'role', 'status'}
TIMES = {'before_ns', 'after_ns', 'deadline_ns'}
IDENTITY = ('request_id', 'event_id', 'token_domain', 'token_generation')
KINDS = {'arm', 'map_publish', 'bind', 'notify', 'wait', 'abandon', 'close'}


def parse_rows(raw):
    try:
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8'), newline=''))
    except UnicodeDecodeError as error:
        raise ValueError('Sidecar is not UTF-8') from error
    require(reader.fieldnames == COLUMNS, 'Unknown schema-5 sidecar columns')
    rows = []
    for row in reader:
        require(set(row) == set(COLUMNS) and all(value is not None for value in row.values()),
                'Truncated/malformed sidecar row')
        require(row['kind'] in KINDS and row['role'] in {'producer', 'consumer'}, 'Unknown sidecar operation/role')
        for key in set(COLUMNS) - WORDS:
            value = row[key]
            if value == '':
                row[key] = None
                continue
            digits = value[1:] if key in TIMES and value.startswith('-') else value
            require(digits.isascii() and digits.isdigit(), f'Invalid/nonfinite sidecar {key}')
            number = int(value)
            low, high = (-(1 << 63), (1 << 63) - 1) if key in TIMES else (0, (1 << 64) - 1)
            require(low <= number <= high, f'Sidecar {key} outside declared integer domain')
            row[key] = number
        base.bracket(row)
        rows.append(row)
    return rows


def _one(rows, kind, phase=None, required=True):
    found = [row for row in rows if row['kind'] == kind and (phase is None or row['phase'] == phase)]
    require(len(found) <= 1 and (not required or len(found) == 1), f'Missing/duplicate sidecar {kind}/{phase}')
    return found[0] if found else None


def _same_identity(first, second):
    require(all(first[key] == second[key] for key in IDENTITY), 'Notification mapping/token identity mismatch')


def _accounting(summary, sides):
    values = summary.get('notification_accounting')
    require(type(values) is dict, 'Missing bounded notification accounting')
    fields = ('object_storage_bytes', 'active_object_bytes', 'shared_domain_counter_bytes', 'token_value_bytes',
              'mapping_entry_bytes', 'mapping_capacity', 'mapping_reserved_bytes', 'mapping_publication_atomic_bytes',
              'owner_binding_bytes', 'consumer_binding_bytes', 'producer_trace_capacity', 'consumer_trace_capacity',
              'mapping_vector_object_bytes', 'sidecar_trace_object_bytes',
              'producer_reserved_capacity', 'consumer_reserved_capacity', 'sidecar_row_bytes',
              'sidecar_reserved_bytes', 'producer_rows', 'consumer_rows', 'dropped_event_count')
    for key in fields:
        integer(values.get(key), 'Notification accounting ' + key)
    require(values.get('opaque_runtime_allocation') is True, 'Opaque synchronization resources must remain explicit')
    require(values['dropped_event_count'] == 0, 'Dropped sidecar events prevent validation')
    require(values['token_value_bytes'] == 16 and values['shared_domain_counter_bytes'] >= 8 and
            values['mapping_publication_atomic_bytes'] >= 8, 'Missing token/domain/publication storage')
    require(values['mapping_entry_bytes'] >= 32 and values['owner_binding_bytes'] == values['mapping_entry_bytes'] and
            values['consumer_binding_bytes'] == values['mapping_entry_bytes'], 'Captured mapping storage is omitted or inconsistent')
    pointer_bytes = summary['abi']['pointer_bytes'] if type(summary.get('abi')) is dict else 1
    require(values['mapping_vector_object_bytes'] >= 3 * pointer_bytes and
            values['sidecar_trace_object_bytes'] >= 2 * values['mapping_vector_object_bytes'],
            'Mapping/vector/trace facade storage is omitted')
    count = summary['expected_requests']
    require(values['mapping_capacity'] >= count + 1 and
            values['mapping_reserved_bytes'] == values['mapping_capacity'] * values['mapping_entry_bytes'],
            'Mapping allocation capacity/bytes do not reconcile')
    require(values['object_storage_bytes'] > values['active_object_bytes'] and
            (values['active_object_bytes'] > 0 if summary['wait_mode'] == 'notify' else values['active_object_bytes'] == 0),
            'Optional notification object/active storage contradicts mode')
    for role, factor in (('producer', 3), ('consumer', 7)):
        require(values[role + '_trace_capacity'] == count * factor + 32 and
                values[role + '_reserved_capacity'] >= values[role + '_trace_capacity'], 'Unexpected bounded sidecar profile')
        actual = sum(row['role'] == role for row in sides)
        require(values[role + '_rows'] == actual <= values[role + '_trace_capacity'], 'Sidecar count/capacity mismatch')
    require(values['sidecar_row_bytes'] >= 128 and values['sidecar_reserved_bytes'] ==
            (values['producer_reserved_capacity'] + values['consumer_reserved_capacity']) * values['sidecar_row_bytes'],
            'Sidecar trace storage omits actual ABI row/capacity accounting')
    return dict(values)


def analyze(trace, summary, *, sidecar, allow_failure=False):
    require(type(summary) is dict and type(summary.get('schema_version')) is int and summary['schema_version'] == 5 and
            type(summary.get('base_projection_schema_version')) is int and summary['base_projection_schema_version'] == 4,
            'Schema-5 requires explicit unchanged schema-4 base projection')
    require(summary.get('variant') == 'coordinator' and summary.get('wait_mode') in {'poll', 'notify'}, 'Unknown notification profile')
    require(summary.get('sidecar_written') is True and summary.get('sidecar_error') is None, 'Sidecar persistence unavailable')
    require(type(summary.get('safety_wait_timeout_ns')) is int and summary['safety_wait_timeout_ns'] == 2000000000,
            'Notification safety wait is not the declared separate two-second profile')
    raw, side_raw = Path(trace).read_bytes(), Path(sidecar).read_bytes()
    projection = dict(summary, schema_version=4)
    with tempfile.TemporaryDirectory(prefix='xerax-schema5-') as directory:
        captured = Path(directory) / 'captured-source.csv'
        captured.write_bytes(raw)
        result = base.analyze(captured, projection, allow_failure=allow_failure)
    require(result['trace_sha256'] == hashlib.sha256(raw).hexdigest(), 'Base projection did not validate captured source bytes')
    source = base.parse_rows(raw)
    sides = parse_rows(side_raw)
    accounting = _accounting(summary, sides)
    tolerance = summary['cross_thread_tolerance_ns']
    mode = summary['wait_mode']
    by_source = {(row['role'], row['id']): row for row in source}
    owners = {row['id']: row for row in source if row['kind'] == 'owner'}
    requests = {row['request_id']: row for row in source if row['kind'] == 'request'}
    selections = {row['request_id']: row for row in source if row['kind'] == 'selection'}
    shutdowns = {row['role']: row for row in source if row['kind'] == 'shutdown'}
    for role in ('producer', 'consumer'):
        events = [row for row in sides if row['role'] == role]
        require([row['id'] for row in events] == list(range(1, len(events) + 1)), 'Sidecar role identities missing/reused/regressing')
        for previous, current in zip(events, events[1:]):
            require(previous['after_ns'] <= current['before_ns'], 'Sidecar same-role operations overlap/regress')
        # Sidecar calls are additional synchronous work, never concurrent with
        # source API calls on the same role. Owner containers are excluded.
        leaves = sorted(events + [row for row in source if row['role'] == role and row['kind'] != 'owner'],
                        key=lambda row: (row['before_ns'], row['after_ns']))
        for previous, current in zip(leaves, leaves[1:]):
            require(previous['after_ns'] <= current['before_ns'], 'Source and sidecar work overlap on the same role')
    cpu = summary.get('process_cpu')
    if cpu is not None:
        for row in sides:
            require(cpu['start_after_ns'] <= row['before_ns'] <= row['after_ns'] <= cpu['end_before_ns'],
                    'CPU window omits notification work')
    for row in sides:
        kind = row['kind']
        if kind != 'wait':
            require(row['stage_loads'] is None and row['yield_calls'] is None, 'Polling counters attached to non-wait operation')
            require(row['deadline_ns'] is None, 'Non-wait operation invents safety deadline')
        if kind == 'close':
            require(mode == 'notify' and row['status'] == 'closed' and row['phase'] in {'failure', 'shutdown'}, 'Invalid sticky-close event')
            require(all(row[key] is None for key in IDENTITY + ('parent_owner_id', 'parent_service_id', 'base_row_id', 'deadline_ns')),
                    'Close invents request/token provenance')
            require(row['phase'] != 'failure' or not summary['complete'], 'Clean workload contains failure-only close')
            if row['phase'] == 'shutdown':
                end = shutdowns.get(row['role'])
                require(end is not None, 'Notification close lacks corresponding role shutdown')
                require(row['after_ns'] <= end['before_ns'] if row['role'] == 'consumer' else end['after_ns'] <= row['before_ns'],
                        'Notification close/shutdown ordering contradicts observer')
            continue
        require(row['request_id'] in selections, 'Detached notification operation')
        if kind != 'wait' or row['phase'] != 'cleanup_poll':
            require(row['event_id'] == selections[row['request_id']]['event_id'], 'Notification uses wrong selected source event')
        if kind in {'bind', 'notify'}:
            service = by_source.get(('producer', row['parent_service_id']))
            owner = owners.get(row['parent_owner_id'])
            wanted = 'acquired' if kind == 'bind' else 'ready'
            require(mode == 'notify' and row['role'] == 'producer' and row['phase'] == wanted and service is not None and
                    service['kind'] == 'service' and service['field'] == wanted and service['status'] == 'ok' and
                    service['parent_id'] == row['parent_owner_id'] and owner is not None, 'Notification is detached from actual owner transition')
            require(service['after_ns'] <= row['before_ns'] <= row['after_ns'] <= owner['after_ns'] and
                    owner['before_ns'] <= row['before_ns'], 'Owner work interval omits binding/notification cost')
            require(row['base_row_id'] is None and row['deadline_ns'] is None, 'Owner notification has fabricated consumer call/deadline')
        else:
            require(row['role'] == 'consumer' and row['parent_owner_id'] is None and row['parent_service_id'] is None,
                    'Client notification operation has wrong role/parent')
    arms = [row for row in sides if row['kind'] == 'arm']
    successful_arms = [row for row in arms if row['status'] == 'ok']
    waits = [row for row in sides if row['kind'] == 'wait']
    cleanups = [row for row in waits if row['phase'] == 'cleanup_poll']
    reasons = list(result['measurement_ineligible_reasons'])
    if cleanups:
        reasons.append('notification_cleanup_poll')
    if mode == 'poll':
        require(all(row['kind'] == 'wait' and row['phase'] in {'poll', 'cleanup_poll'} for row in sides), 'Polling mode contains active notifier operations')
        require(summary.get('notification_state_after') is None, 'Polling mode invents active notification state')
    else:
        state = summary.get('notification_state_after')
        require(type(state) is dict, 'Missing final notification state')
        for key in ('domain', 'last_generation', 'predicate_checks'):
            integer(state.get(key), 'Final notification ' + key, minimum=1 if key == 'domain' else 0)
        require(all(type(state.get(key)) is bool for key in ('armed', 'ready', 'waiting', 'closed')) and
                state['closed'] and not state['armed'] and not state['ready'] and not state['waiting'],
                'Notification ownership is not closed and quiescent after join')
        require(state['last_generation'] == len(successful_arms), 'Final generation disagrees with admitted arm trace')
        for generation, arm in enumerate(successful_arms, 1):
            require(arm['phase'] == 'request' and arm['status'] == 'ok' and arm['token_domain'] == state['domain'] and
                    arm['token_generation'] == generation and arm['base_row_id'] is None, 'Invalid, reused or nonmonotonic arm identity')
        for arm in arms:
            if arm['status'] != 'ok':
                require(not summary['complete'] and arm['phase'] == 'request' and arm['status'] == 'closed' and
                        arm['token_domain'] is None and arm['token_generation'] is None and arm['base_row_id'] is None,
                        'Failed arm fabricates a token or contradicts supported closed-before-arm failure')
                require(any(row['kind'] == 'close' and row['before_ns'] <= arm['after_ns'] + tolerance for row in sides),
                        'Closed arm lacks a feasible prior stop')
                reasons.append('notification_arm_closed')
        for role in ('producer', 'consumer'):
            role_events = [row for row in sides if row['role'] == role]
            terminal = _one(role_events, 'close', 'shutdown')
            require(role_events[-1] is terminal, 'Notification role continues after terminal shutdown close')
        for row in sides:
            if (row['kind'] in {'arm', 'notify', 'abandon'} or row['kind'] == 'wait' and row['phase'] == 'notify') and row['status'] in {'ok', 'ready'}:
                require(not any(close['kind'] == 'close' and close['after_ns'] +
                                (0 if close['role'] == row['role'] else tolerance) < row['before_ns'] for close in sides),
                        'Successful notification operation follows completed sticky close')
    phase_rows = [row for row in source if row['kind'] == 'service' and row['status'] == 'ok' and
                  row['field'] in {'acquired', 'granted', 'ready'}]
    admitted_calls = [call for call in requests.values() if call['status'] == 'ok']
    cycles = {call['request_id']: phase_rows[index * 3:index * 3 + 3] for index, call in enumerate(admitted_calls)}
    for request_id, call in requests.items():
        events = [row for row in sides if row['request_id'] == request_id]
        normal = [row for row in events if row['kind'] == 'wait' and row['phase'] != 'cleanup_poll']
        admitted = call['status'] == 'ok'
        if mode == 'notify':
            arm = _one(events, 'arm')
            pre = next(row for row in source if row['request_id'] == request_id and row['kind'] == 'eligibility' and row['phase'] == 'pre_call')
            require(pre['after_ns'] <= arm['before_ns'] <= arm['after_ns'] <= call['before_ns'],
                    'Arm precedes source selection/eligibility or follows submission')
            if arm['status'] != 'ok':
                require(call['status'] == 'closed' and all(row['kind'] in {'arm'} for row in events),
                        'Failed notification arm must close and drain through an actual rejected source call')
                continue
            published = _one(events, 'map_publish')
            _same_identity(arm, published)
            require(published['phase'] == 'request' and published['status'] == 'ok' and published['base_row_id'] is None and
                    arm['after_ns'] <= published['before_ns'] <= published['after_ns'] <= call['before_ns'],
                    'Arm and immutable mapping publication must precede source submission')
            if admitted:
                bind, notify = _one(events, 'bind'), _one(events, 'notify')
                _same_identity(arm, bind)
                _same_identity(bind, notify)
                require(bind['status'] == 'ok' and notify['status'] in {'ok', 'closed'}, 'Unexpected binding/notification result')
                cycle = cycles[request_id]
                require(len(cycle) == 3 and bind['parent_service_id'] == cycle[0]['id'] and
                        notify['parent_service_id'] == cycle[2]['id'], 'Request binding and notification belong to different owner cycles')
                require(published['before_ns'] <= bind['after_ns'] + tolerance and
                        call['before_ns'] <= bind['after_ns'] + tolerance and bind['after_ns'] <= notify['before_ns'],
                        'Owner binding cannot observe an unpublished request or future token')
                require(not any(row['kind'] == 'abandon' for row in events), 'Admitted source work cannot be silently abandoned')
            else:
                abandoned = _one(events, 'abandon')
                _same_identity(arm, abandoned)
                require(abandoned['phase'] == 'rejected' and abandoned['status'] in {'ok', 'closed'} and
                        abandoned['base_row_id'] == call['id'] and call['after_ns'] <= abandoned['before_ns'],
                        'Rejected source admission lacks explicit notification-interest cleanup')
                require(not any(row['kind'] in {'bind', 'notify'} for row in events), 'Rejected source work has invented owner transitions')
        require(len(normal) == (1 if admitted else 0), 'Missing/excess wait for source admission')
        if admitted:
            wait = normal[0]
            require(wait['phase'] == mode and wait['base_row_id'] == call['id'] and call['after_ns'] <= wait['before_ns'],
                    'Wait is detached from its actual submitted source request')
            takes = [row for row in source if row['request_id'] == request_id and row['kind'] == 'take']
            require(takes and wait['after_ns'] <= takes[0]['before_ns'], 'Take precedes matching wait completion')
            if mode == 'notify':
                _same_identity(_one(events, 'arm'), wait)
                require(wait['status'] in {'ready', 'closed', 'timed_out', 'counter_exhausted'} and
                        wait['deadline_ns'] == wait['before_ns'] + summary['safety_wait_timeout_ns'],
                        'Invalid notification wait result or conflated safety/source deadline')
                notify = _one(events, 'notify')
                if wait['status'] == 'ready':
                    require(notify['status'] == 'ok' and notify['before_ns'] <= wait['after_ns'] + tolerance,
                            'Ready wait has no feasible matching notification')
                else:
                    require(not summary['complete'], 'Failed notification wait cannot be a clean workload')
                    if wait['status'] == 'timed_out':
                        require(wait['after_ns'] >= wait['deadline_ns'], 'Notification timeout precedes its actual clock deadline')
                    if wait['status'] == 'counter_exhausted':
                        require(summary['notification_state_after']['predicate_checks'] == (1 << 64) - 1,
                                'Predicate exhaustion contradicts the observer default lifetime counter limit')
                    if wait['status'] == 'closed':
                        require(any(row['kind'] == 'close' and row['before_ns'] <= wait['after_ns'] + tolerance for row in sides),
                                'Closed wait lacks a feasible actual stop')
                    reasons.append('notification_wait_' + wait['status'])
            else:
                require(wait['status'] in {'ready', 'owner_ended'} and wait['deadline_ns'] is None and
                        wait['token_domain'] is None and wait['token_generation'] is None, 'Polling wait fabricates notification identity')
    for row in sides:
        if row['kind'] not in {'close'}:
            require(row['request_id'] in requests, 'Notification mapping exists without a recorded source admission call')
    if mode == 'notify':
        transitions = [row for row in source if row['kind'] == 'service' and row['status'] == 'ok' and row['field'] in {'acquired', 'ready'}]
        bindings = [row for row in sides if row['kind'] in {'bind', 'notify'}]
        require([row['parent_service_id'] for row in bindings] == [row['id'] for row in transitions],
                'Owner transition reused, omitted or given an invented notification')
    counts = dict(normal_stage_loads=0, normal_yield_calls=0, cleanup_stage_loads=0, cleanup_yield_calls=0)
    for wait in waits:
        stage, yields = integer(wait['stage_loads'], 'Wait stage loads'), integer(wait['yield_calls'], 'Wait yields')
        if wait['phase'] == 'notify':
            require(stage == yields == 0, 'Normal notification waiting secretly polls source stage')
        else:
            require(stage == yields + 2, 'Polling wait counters omit loop/status predicate observations')
        prefix = 'cleanup' if wait['phase'] == 'cleanup_poll' else 'normal'
        counts[prefix + '_stage_loads'] += stage
        counts[prefix + '_yield_calls'] += yields
        if wait['phase'] == 'cleanup_poll':
            require(not summary['complete'] and wait['status'] in {'ready', 'owner_ended'} and
                    wait['deadline_ns'] is None,
                    'Cleanup polling is not explicitly separated from normal measurement')
            call = requests[wait['request_id']]
            normal = _one([row for row in waits if row['request_id'] == wait['request_id'] and row['phase'] != 'cleanup_poll'], 'wait')
            take = next(row for row in source if row['kind'] == 'take' and row['request_id'] == wait['request_id'])
            _same_identity(normal, wait)
            require(wait['base_row_id'] == call['id'], 'Inline failure cleanup lost original source admission identity')
            require(call['status'] == 'ok' and normal['status'] != 'ready' and
                    normal['after_ns'] <= wait['before_ns'] <= wait['after_ns'] <= take['before_ns'] and
                    sum(row['request_id'] == wait['request_id'] for row in cleanups) == 1,
                    'Cleanup polling lacks retained pending work or lies outside its actual drain')
    require(summary.get('wait_counts') == counts and all(type(value) is int for value in summary['wait_counts'].values()),
            'Summary waiting counters disagree with observed brackets')
    for key, kind in (('mapping_published_count', 'map_publish'), ('owner_binding_count', 'bind'), ('notification_count', 'notify')):
        require(type(summary.get(key)) is int and summary[key] == sum(row['kind'] == kind for row in sides), 'Mapping lifecycle summary count mismatch')
    for row in sides:
        if row['kind'] == 'notify' and row['status'] == 'closed':
            require(any(close['kind'] == 'close' and close['before_ns'] <= row['after_ns'] + tolerance for close in sides),
                    'Closed notification result lacks feasible sticky close')
            reasons.append('notification_closed_before_notify')
    result.update(schema_version=5, scope='single-run notification integration validation; no paired improvement claim',
                  base_projection_schema_version=4, wait_mode=mode,
                  notification_structural_valid=True, sidecar_sha256=hashlib.sha256(side_raw).hexdigest(),
                  sidecar_rows=len(sides), notification_accounting=accounting, wait_counts=counts,
                  notification_wait_ns=base.distribution([row['after_ns'] - row['before_ns'] for row in waits if row['phase'] == mode]),
                  cleanup_poll_count=len(cleanups), measurement_eligible=not reasons,
                  measurement_ineligible_reasons=list(dict.fromkeys(reasons)))
    result['limits'] += ['Notification brackets prove feasible matching, not exact wake or predicate linearization times.',
                         'A matched wait may return before the producer records notify.after; this is legitimate.',
                         'Normal-wait polling counts are declared instrumentation and exclude the post-wait one-shot Ready assertion.',
                         'Notification runtime mutex/CV allocations remain opaque; ABI accounting is not process RSS.',
                         'Trace checks cannot prove that instrumentation omitted no source operations or counter increments.']
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trace', type=Path, required=True)
    parser.add_argument('--summary', type=Path, required=True)
    parser.add_argument('--sidecar', type=Path, required=True)
    parser.add_argument('--allow-failure', action='store_true')
    args = parser.parse_args()
    print(json.dumps(analyze(args.trace, json.loads(args.summary.read_text()), sidecar=args.sidecar,
                             allow_failure=args.allow_failure), indent=2))
