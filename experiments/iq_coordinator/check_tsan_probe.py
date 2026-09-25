"""Require an actual data-race diagnostic, not an arbitrary nonzero exit."""
from pathlib import Path
import subprocess
import sys

if len(sys.argv) != 2:
    raise SystemExit('Usage: check_tsan_probe.py INSTRUMENTED_PROBE')
run = subprocess.run([sys.argv[1]], capture_output=True, timeout=30)
Path('build/tsan-probe.stdout').write_bytes(run.stdout)
Path('build/tsan-probe.stderr').write_bytes(run.stderr)
if run.returncode != 66 or b'WARNING: ThreadSanitizer: data race' not in run.stderr:
    sys.stderr.write(run.stderr.decode('utf-8', errors='replace'))
    raise SystemExit(f'Instrumentation control failed: expected race diagnostic and exit66, got {run.returncode}')
print('Expected deliberate data race detected; instrumentation control passed. This is not a coordinator failure.')
