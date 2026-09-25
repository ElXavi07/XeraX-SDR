"""Validate schema-2 observations without turning failed/partial trials into wins.

Use --summary <stdout-json> --trace <csv> to inspect saved evidence. No receiver
is launched here. Schema 1 is deliberately handled by the unchanged validator.
"""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path

COLUMNS = ['kind', 'index', 'first_sample', 'end_sample', 'due_us', 'wake_us',
           'begin_us', 'end_us', 'verified_us', 'released_us', 'status', 'verification', 'release_kind']
NUMERIC = ['due_us', 'wake_us', 'begin_us', 'end_us', 'verified_us', 'released_us']
NULLABLE = {'verified_us', 'released_us'}
# CSV uses 12 significant digits. At the maximum 600-second workload, 0.002
# microseconds covers rounding between independently printed stamps.
STAMP_TOLERANCE_US = .002
PREFILL_END_SAMPLE = 30 * 30720


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, field):
    require(type(value) is int and value >= 0, f'{field} must be a nonnegative integer')
    return value


def distribution(values):
    if not values:
        return None
    values = sorted(values)
    return {'n': len(values), 'p50': values[math.ceil(len(values) * .50) - 1],
            'p95': values[math.ceil(len(values) * .95) - 1],
            'p99': values[math.ceil(len(values) * .99) - 1], 'max': values[-1]}


def analyze(trace, summary, *, allow_failure=False):
    require(type(summary) is dict and type(summary.get('schema')) is int and summary['schema'] == 2,
            'Expected schema 2 summary')
    require(type(summary.get('complete')) is bool, 'Missing completion flag')
    require(summary.get('trace_written') is True and summary.get('trace_error') is None,
            'Trace is not confirmed written')
    require(summary.get('variant') in ('none', 'whole', 'chunk64', 'chunk256'), 'Unknown variant')
    require(summary.get('format') in ('cu8', 'cf32'), 'Unknown format')
    require(summary.get('injection') in ('none', 'byte', 'stream', 'epoch', 'rate', 'frequency',
                                       'width', 'first', 'end', 'size', 'append', 'consumer-exception',
                                       'verify-exception', 'overcommit'), 'Unknown injection')
    seconds = integer(summary.get('seconds'), 'seconds')
    hz = integer(summary.get('snapshot_hz'), 'snapshot_hz')
    hold = integer(summary.get('hold_ms'), 'hold_ms')
    require(1 <= seconds <= 600 and 1 <= hz <= 100 and hold <= 10000, 'Workload outside bounds')
    require(summary.get('sample_rate_hz') == 3072000 and summary.get('block_samples') == 30720
            and summary.get('snapshot_samples') == 768000, 'Unexpected sample workload')
    require(summary.get('payload_bytes') == 15 * 1024 * 1024, 'Payload budget mismatch')
    require(summary.get('input_vector_bytes') == 30720 * (2 if summary['format'] == 'cu8' else 8),
            'Unaccounted producer input vector')
    integer(summary.get('outstanding_credits'), 'outstanding_credits')
    require(type(summary.get('failures')) is list, 'Missing failures array')
    if summary['complete']:
        require(not summary['failures'] and summary['outstanding_credits'] == 0,
                'Complete trial reports errors or leaked credits')
    else:
        require(allow_failure, 'Failed trial is not a performance result')
        require(bool(summary['failures']), 'Incomplete trial has no failure explanation')
    append_limit = seconds * 100
    snapshot_limit = 0 if summary['variant'] == 'none' else seconds * hz
    rows = {'append': [], 'snapshot': []}
    # Capture once: validation and the reported digest must describe identical
    # bytes even if another process replaces the path while analysis proceeds.
    trace_bytes = Path(trace).read_bytes()
    with io.StringIO(trace_bytes.decode('utf-8'), newline='') as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames == COLUMNS, 'Unknown or malformed observation columns')
        for number, row in enumerate(reader):
            require(number < append_limit + snapshot_limit, 'Excess observation rows')
            require(set(row) == set(COLUMNS) and all(value is not None for value in row.values()), 'Malformed observation row')
            require(row['kind'] in rows, 'Unknown observation kind')
            for name in ('index', 'first_sample', 'end_sample', 'status'):
                require(row[name].isascii() and row[name].isdigit(), f'Invalid {name}')
                row[name] = int(row[name])
            for name in NUMERIC:
                if name in NULLABLE and row[name] == '':
                    row[name] = None
                else:
                    row[name] = float(row[name])
                    # These are signed offsets from a scheduled future origin,
                    # not durations. A pre-origin observation is not missing data.
                    require(math.isfinite(row[name]), f'Invalid {name}')
                    if name == 'due_us':
                        require(row[name] >= 0, 'Invalid schedule origin')
            require(row['index'] == len(rows[row['kind']]), 'Nonsequential observations')
            require(row['begin_us'] >= row['wake_us'] and row['end_us'] >= row['begin_us'], 'Reversed operation timing')
            require(row['end_sample'] - row['first_sample'] == (30720 if row['kind'] == 'append' else 768000),
                    'Wrong sample interval length')
            period = 10000 if row['kind'] == 'append' else 1000000 / hz
            require(abs(row['due_us'] - row['index'] * period) <= STAMP_TOLERANCE_US, 'Wrong scheduled deadline')
            if row['kind'] == 'append':
                require(row['verification'] == 'not_applicable' and row['release_kind'] == 'not_applicable'
                        and row['verified_us'] is None and row['released_us'] is None, 'Append has invented lease observations')
                if row['status'] == 0:
                    require(row['first_sample'] == (30 + row['index']) * 30720, 'Invalid successful input sequence')
                if summary['complete']:
                    require(row['status'] == 0, 'Complete trial reports a rejected input')
            else:
                require(row['status'] in (0, 5, 6, 7, 8, 9, 11, 12, 13), 'Unknown snapshot result')
                if row['status'] == 0:
                    require(row['verification'] in ('ok', 'failed', 'aborted'), 'Accepted payload lacks a verification outcome')
                    require(row['verified_us'] is not None and row['verified_us'] >= row['end_us'], 'Missing/reversed verification timing')
                    require(row['released_us'] is not None and row['released_us'] >= row['verified_us'], 'Missing/reversed lease release')
                    require(row['release_kind'] in ('immediate', 'tick', 'shutdown', 'failure'), 'Unknown release kind')
                    if row['verification'] != 'ok':
                        require(row['release_kind'] == 'failure', 'Failed verification lacks a failure release')
                    if row['release_kind'] == 'tick':
                        require(row['released_us'] - row['verified_us'] + STAMP_TOLERANCE_US >= hold * 1000,
                                'Lease released before requested minimum hold')
                    if row['release_kind'] == 'immediate':
                        require(hold == 0, 'Immediate release with a requested hold')
                    if summary['complete']:
                        require(row['verification'] == 'ok' and row['release_kind'] != 'failure', 'Complete trial includes failed snapshot')
                else:
                    require(row['verification'] == 'not_applicable' and row['verified_us'] is None and row['released_us'] is None
                            and row['release_kind'] == 'not_applicable', 'Rejected snapshot has invented payload/lease evidence')
                    if summary['complete']:
                        require(row['status'] in (9, 11, 13), 'Unexpected rejection in a complete trial')
            rows[row['kind']].append(row)
    for kind, field, limit in (('append', 'appends', append_limit), ('snapshot', 'snapshot_attempts', snapshot_limit)):
        require(len(rows[kind]) == integer(summary.get(field), field) <= limit, 'Observation count mismatch')
        if summary['complete']:
            require(len(rows[kind]) == limit, 'Complete trial has missing attempts')
    appends, snapshots = rows['append'], rows['snapshot']

    # The harness has one producer and one consumer. Timestamps are signed clock
    # offsets, but each worker's observations still have a sequential order.
    for previous, current in zip(appends, appends[1:]):
        require(previous['end_us'] <= current['wake_us'] + STAMP_TOLERANCE_US,
                'Producer observations overlap or reverse')
        require(previous['status'] == 0, 'Producer continued after a rejected append')
    for previous, current in zip(snapshots, snapshots[1:]):
        finished = previous['verified_us'] if previous['status'] == 0 else previous['end_us']
        require(finished <= current['wake_us'] + STAMP_TOLERANCE_US,
                'Consumer observations overlap or reverse')
        require(previous['verification'] not in ('failed', 'aborted'), 'Consumer continued after failed verification')

    # An append end stamp bounds a feasible source interval, but does NOT record
    # when latest.store publishes it or latest.load selects it. Either thread can
    # be preempted between those events and its observed stamp. Reject impossible
    # intervals without claiming these bounds prove actual publication timing.
    # The missing publication/selection observations prohibit performance use.
    completed_frontier = PREFILL_END_SAMPLE
    append_cursor = 0
    previous_requested_end = PREFILL_END_SAMPLE
    for row in snapshots:
        while append_cursor < len(appends) and appends[append_cursor]['end_us'] <= row['begin_us'] + STAMP_TOLERANCE_US:
            appended = appends[append_cursor]
            if appended['status'] == 0:
                completed_frontier = appended['end_sample']
            append_cursor += 1
        require(row['end_sample'] >= PREFILL_END_SAMPLE and row['end_sample'] % 30720 == 0,
                'Snapshot source frontier is outside the published block sequence')
        require(previous_requested_end <= row['end_sample'] <= completed_frontier,
                'Snapshot source frontier regresses or exceeds completed input')
        previous_requested_end = row['end_sample']

    owned = [row for row in snapshots if row['status'] == 0]
    for previous, current in zip(owned, owned[1:]):
        require(previous['released_us'] <= current['begin_us'] + STAMP_TOLERANCE_US,
                'Accepted snapshots overlap the single ownership credit')
    shutdown = [row for row in owned if row['release_kind'] == 'shutdown']
    require(len(shutdown) <= 1, 'Multiple shutdown-censored leases in a single-credit trial')
    if shutdown:
        require(shutdown[0] is owned[-1], 'Shutdown release is not the final owned lease')
        final = snapshots[-1]
        final_completion = final['verified_us'] if final['status'] == 0 else final['end_us']
        require(shutdown[0]['released_us'] + STAMP_TOLERANCE_US >= final_completion,
                'Shutdown release predates the final consumer observation')
        if summary['complete']:
            require(hold > 0, 'Complete zero-hold trial invents a shutdown-censored lease')

    accepted = [r for r in snapshots if r['status'] == 0 and r['verification'] == 'ok']
    uncensored = [r for r in accepted if r['release_kind'] in ('immediate', 'tick')]
    structurally_valid = summary['complete'] and summary['injection'] == 'none'
    return {'schema': 2, 'scope': 'storage observations only', 'performance_eligible': False,
        'structurally_valid_workload': structurally_valid,
        'performance_ineligible_reason': 'source_publication_time_unobserved',
        'trace_sha256': hashlib.sha256(trace_bytes).hexdigest(),
        'accepted_verified_snapshots': len(accepted), 'snapshot_attempts': len(snapshots),
        'snapshot_status_counts': {str(status): sum(r['status'] == status for r in snapshots) for status in sorted({r['status'] for r in snapshots})},
        'producer_call_us': distribution([r['end_us'] - r['begin_us'] for r in appends]),
        'producer_wake_lateness_us': distribution([max(0, r['wake_us'] - r['due_us']) for r in appends]),
        'producer_early_wakes': sum(r['wake_us'] < r['due_us'] for r in appends),
        'producer_signed_wake_offset_us': distribution([r['wake_us'] - r['due_us'] for r in appends]),
        'producer_calls_over_10ms': sum(r['end_us'] - r['begin_us'] > 10000 for r in appends),
        'producer_finished_after_next_block': sum(r['end_us'] > r['due_us'] + 10000 for r in appends),
        'consumer_wake_lateness_us': distribution([max(0, r['wake_us'] - r['due_us']) for r in snapshots]),
        'consumer_early_wakes': sum(r['wake_us'] < r['due_us'] for r in snapshots),
        'consumer_signed_wake_offset_us': distribution([r['wake_us'] - r['due_us'] for r in snapshots]),
        'copy_return_us': distribution([r['end_us'] - r['begin_us'] for r in accepted]),
        'verification_us': distribution([r['verified_us'] - r['end_us'] for r in accepted]),
        'request_to_verified_us': distribution([r['verified_us'] - r['begin_us'] for r in accepted]),
        'observed_copy_return_to_release_us': distribution([r['released_us'] - r['end_us'] for r in uncensored]),
        'observed_post_verification_hold_us': distribution([r['released_us'] - r['verified_us'] for r in uncensored]),
        'shutdown_censored_holds': sum(r['release_kind'] == 'shutdown' for r in accepted),
        'failures': summary['failures'],
        'limits': ['No schema-2 observation is performance-eligible: source publication/selection event times are unobserved.',
                   'Feasible source bounds and structural validation do not prove actual publication timing.',
                   'Diagnostic statistics from failed/injected runs are not performance evidence.',
                   'Release is observed after reset returns; acquisition inside copy call is not timestamped.',
                   'Request-tick release quantization is retained and measured.',
                   'Shutdown-censored holds are excluded from hold distributions.',
                   'No driver drops, RF data or decoder performance measured.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary', type=Path, required=True)
    parser.add_argument('--trace', type=Path, required=True)
    parser.add_argument('--allow-failure', action='store_true')
    args = parser.parse_args()
    print(json.dumps(analyze(args.trace, json.loads(args.summary.read_bytes()), allow_failure=args.allow_failure), indent=2))
