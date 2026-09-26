"""Require three fixed, independently executed deliberate-race diagnostics.

Every invocation must pass. These are repeated controls, never retries that
discard a failed detector. Candidate checks must not run if any control fails.
"""
import json
from pathlib import Path
import subprocess
import sys

PROBE_RUNS = 3
DIAGNOSTIC = b'WARNING: ThreadSanitizer: data race'


def _bytes(value):
    if value is None:
        return b''
    return value.encode('utf-8', errors='replace') if isinstance(value, str) else value


def check_probes(executable, output_directory=Path('build')):
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    results = []
    for number in range(1, PROBE_RUNS + 1):
        returncode, error = None, None
        try:
            run = subprocess.run([str(executable)], capture_output=True, timeout=30)
            returncode, stdout, stderr = run.returncode, run.stdout, run.stderr
        except subprocess.TimeoutExpired as failure:
            stdout, stderr = failure.output, failure.stderr
            error = 'timeout'
        except OSError as failure:
            stdout, stderr = b'', str(failure).encode('utf-8', errors='replace')
            error = type(failure).__name__
        stdout, stderr = _bytes(stdout), _bytes(stderr)
        (output_directory / f'tsan-probe-{number}.stdout').write_bytes(stdout)
        (output_directory / f'tsan-probe-{number}.stderr').write_bytes(stderr)
        passed = error is None and returncode == 66 and DIAGNOSTIC in stderr
        results.append({'invocation': number, 'returncode': returncode,
                        'error': error, 'race_diagnostic': DIAGNOSTIC in stderr, 'passed': passed})
        label = 'EXPECTED' if passed else 'FAILED'
        print(f'BEGIN {label} CONTROL {number}/{PROBE_RUNS} (deliberately broken probe, not receiver)', flush=True)
        print(stderr.decode('utf-8', errors='replace'), end='', flush=True)
        print(f'END {label} CONTROL {number}/{PROBE_RUNS}', flush=True)
    (output_directory/'tsan-probe-results.json').write_text(json.dumps(results, indent=2)+'\n', encoding='utf-8')
    failed = [result['invocation'] for result in results if not result['passed']]
    if failed:
        raise RuntimeError(f'Instrumentation control failed for invocations {failed}: every fixed invocation requires a race diagnostic and exit66')
    print(f'All {PROBE_RUNS} independent deliberate-race controls passed. These are not receiver failures.', flush=True)


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: check_tsan_probe.py INSTRUMENTED_PROBE')
    try:
        check_probes(sys.argv[1])
    except RuntimeError as failure:
        raise SystemExit(str(failure)) from failure


if __name__ == '__main__':
    main()
