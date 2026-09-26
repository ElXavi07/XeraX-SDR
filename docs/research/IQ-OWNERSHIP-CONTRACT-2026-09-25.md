# IQ ownership and observation contracts — 25 September 2026

This continues the failed [chunked-copy screen](IQ-HISTORY-LATENCY-2026-09-25.md).
It implements and checks the next storage **correctness** hypothesis. There is
no new receiver-speed result, radio capture, protocol improvement or application
package in this increment.

## Implemented synchronous ownership core

The standalone [slab experiment](../../experiments/iq_slabs/README.md) retains
immutable sample spans instead of copying a snapshot while excluding the source
writer. One owner calls its methods synchronously. A move-only lease can be
transferred to another thread; completion is published through a preallocated
state, and only the owner reclaims the underlying slabs. Existing leases remain
valid across retunes, history eviction and destruction of the service facade.

The source payload is exactly 15,728,640 bytes: 252 reusable 61,440-byte slabs
and four permanently reserved ingress-scratch slabs. Useful history is exactly
8 MiB after warmup, with up to 138 physical history spans for the partial-tail
case. One snapshot may hold at most 101 slabs; live readers have a separate
aggregate cap of eight slab claims. The shared process ledger remains charged
while an old arena survives through an outstanding lease, preventing an
unaccounted replacement when the same ledger is used for restart.

The implementation explicitly stages incoming data through scratch before
packing slabs: **two ingress copies**, not a single-copy adapter. It publishes
full slabs and one explicitly closed final partial slab. Filling delays and
partial-callback behavior must be measured in a future acquisition comparison.
No asynchronous request coordinator, cancellation/deadline handshake, live
delivery queue or retrospective/live handoff is implemented yet. Timers never
revoke a reader's still-usable pointer.

## Independent contract results

Fifteen test groups pass on local Windows x64 with GNU C++ 16.1 and warnings
treated as errors. The captured final CTest run checked 23,042 assertions and
49,909,846 independently generated/model-checked bytes. Concurrent repetitions
perform different numbers of safe owner iterations, so totals can vary; the
group count and required invariants do not depend on those totals.

Coverage includes exact retention and arbitrary snapshot alignment, CU8 and
CF32 little-/big-endian opaque-byte parity, short callbacks and closed partial
tails, long-lived snapshot/live pins, retunes and public identity reuse,
service-pool identity, counter exhaustion, arithmetic overflow, atomic argument
rejection, genuine concurrent read/release against owner reuse, service-first
destruction, budget rejection and no heap allocation on normal operational
paths. Source bytes come from an independent generator and a simple retention
model; the candidate's snapshot function is not its own truth generator.

The tests found two defects before this checkpoint:

- After a known input gap, append/grant/seal operations returned `NoEpoch`.
  They now preserve `Discontinuity` until a valid new epoch is established.
- The process ledger's own control allocation needed an admission check before
  allocation. Undersized metadata limits now reject it without temporarily
  exceeding the declared limit.

Local accounted metadata is 48,152 bytes: 48,056 for arena/shared control plus
96 for the process ledger/shared control. This is below the 128 KiB profile,
but excludes allocator/page overhead, caller handle/stack objects, external
input buffers, drivers and decoder workspaces. It is not whole-process RSS.

Both Android `arm64-v8a` and `armeabi-v7a` versions of the library and contract
executable cross-compile with NDK 28.2.13676358, Android API 29 and static libc++.
ELF inspection confirms AArch64/64-bit and ARM/32-bit targets respectively.
These executables have **not run on phones**; compiler acceptance does not prove
ARM atomic behavior, runtime correctness, audio, RF or thermal performance.

## A separate, more observable measurement harness

The original schema-1 harness, its 25 measurements and frozen executables remain
unchanged. New `latency_observed.cpp` and `observe_latency.py` use schema 2 and
record source intervals plus scheduled wake, observed wake, call start/return,
verification end and lease-release observations. Missing events use empty CSV
fields/nulls rather than invented zeroes. Relative offsets can be negative when
an observation precedes the chosen future origin; durations still require
causal ordering. Early wakes are counted separately from positive lateness.

The harness checks all stream metadata fields and every accepted byte. Runtime
verification failure, aborted verification, consumer exceptions and rejected
appends retain partial CSV and structured failure context. Byte failures include
the requested interval, failing offset and expected/observed byte. Setup failures
before an active workload remain setup errors; a trace-write failure is explicit
and cannot be reported as a successful measurement. This does not promise that
an OS crash or exhausted storage can always preserve a trace.

The validator rejects impossible source ranges, missing attempts, overlapping
accepted leases, inconsistent shutdown releases and reversed or nonfinite
times. Validation and the reported SHA-256 use the same single-read byte buffer,
even if another process replaces the trace path during analysis. A failed or
deliberately injected run cannot become a successful performance result.
Fault injection changes only the verifier's observation or
an explicitly labelled test control path; it is not evidence of a new library
corruption. Synthetic observation fixtures independently exercise the validator.

The archived checkpoint's nineteen tests pass with the candidate library under optimized Python and with
the frozen whole-copy library under normal Python. They include nine synthetic
contract tests and ten executable test groups. Final raw stdout/CSV/stderr are
retained. Earlier attempts exposed two harness-test assumptions: rejecting signed
pre-origin timestamps, and assuming setting a timestamp to zero always reverses
it. Both have deterministic regressions; earlier local failure logs remain.

Release timing is measured **after the reset call returns**. The internal pool's
original acquisition instant is not observable, so copy-return-to-release is
an observed ownership interval, not an exact total lock/credit-hold duration.
Requested holds still start after verification and release on request ticks;
shutdown-shortened holds are marked censored and excluded from hold statistics.
All these executions are correctness/fault tests, sometimes alongside builds,
not a new isolated performance screen. Review found that a producer call-end
timestamp does not establish the later source-publication or consumer-selection
instant. Feasible source bounds can reject impossible intervals, but cannot
prove the actual publication sequence. The hardened validator therefore marks
**every schema-2 observation performance-ineligible**, including complete clean
runs, with `source_publication_time_unobserved`. Structural validity is reported
separately. Actual publication/selection observations and a preregistered
controlled workload are required before comparative claims.

The C++ [timing requirements](https://eel.is/c++draft/thread.req.timing) account
for implementation and resource-contention delays. Microsoft's
[QPC guidance](https://learn.microsoft.com/en-us/windows/win32/sysinfo/acquiring-high-resolution-time-stamps)
distinguishes local interval measurement from synchronized wall time. Those
sources support keeping scheduling and call duration separate; they do not
establish an SDR sample-drop count or a hard real-time bound.

## Preserved evidence

The [machine-readable record](evidence/iq-ownership-contract-2026-09-25.json)
contains the recorded contract totals, source/executable hashes, ABI build scope
and original local log hashes. The [160-entry raw evidence archive](evidence/iq-ownership-contract-2026-09-25-raw.zip)
contains source, final functional/fault traces and logs, including earlier test
failures. Its entry manifest was checked after packaging; archive SHA-256 is
`4b5fca77d06754f1988c765c90848263d69f3256512e1e671439e317457b0821`.
Named corrupted/shifted CSV fixtures are labelled as validator test inputs;
they must not be treated as real performance observations.

The archive is frozen at the original local checkpoint. Later review fixes
(portable test expressions, single-read hashing and conservative performance
eligibility) remain visible in Git history; they do not replace its source or
captured results. In particular, an archived `performance_eligible: true` field
from the earlier analyzer is superseded by the restriction above and is not
evidence that the timing gates passed.

After those fixes, all 21 observer tests (11 synthetic and ten executable groups)
pass with the current library under optimized Python and with the frozen
whole-copy library under normal Python. New local traces/logs are kept under
`build/iq-observed-review-evidence`, `build/iq-observed-baseline-review-evidence`
and their matching `*-review-tests.log` files. The rebuilt local slab contract
also passes all 15 groups. These checks validate the revised evidence handling;
they remain functional executions, not performance comparisons.

At code commit `ad5dbde96ce15539c42ab14964b112501536477c`,
[remote receiver CI](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36115691105)
passes on Windows/MSVC and Linux, including the separate Linux address and
undefined-behavior sanitizer job and the independent NXDN references.
[Benchmark CI](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36115691121)
also passes its Windows/Linux Python matrix and soft-metric comparison.

## Next gates

1. Finish the bounded request/coordinator, cancellation, completion and shutdown
   contracts. Test queued-but-unclaimed grants, owner stalls, stale completion
   messages and deferred final deallocation before attaching timing code.
2. Measure input copy **and** owner maintenance/grant/reclamation together.
   Count request-to-grant and verified completion, accepted work, memory and
   actual source publication/selection events and delay. Do not hide work outside
   the timer or infer publication solely from the producer call-end timestamp.
3. Use an upgraded but identical harness for a fresh contemporaneous baseline
   and candidate comparison, with exact matched retention and source patterns.
   Keep the existing failed screen intact. The previously declared completion,
   p99 and deadline gates still apply; shorter or fewer requests are not a win.
4. Run ARM correctness/thermal tests and live source-provenance/frame/PCM
   regressions before any APK/EXE integration. Existing release packages and
   settings are unchanged.
