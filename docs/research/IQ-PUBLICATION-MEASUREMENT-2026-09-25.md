# IQ publication measurement: observation contract before comparison

**25 September 2026 — standalone instrumentation work, not an application speed result.**

The existing schema-2 observer cannot identify the source publication observed
by a reader. Its producer completion timestamp is only an upper bound on when
those samples could have become available. All schema-2 observations therefore
remain performance-ineligible. This increment creates a separate schema and
tests the measurement itself before running another candidate comparison.

The starting revision is `a295c26da26b98673ef8bef9113cb4ae10f659b7`.
The frozen local source archive `build/iq-comparison-baseline-a295c26.zip` has
SHA-256 `eb16b66d45f1d99a148e04a286a34eed774941d2e2fd2fa2d45f9c34d9e69031`.
It preserves whole-copy history, immutable slabs and the shared-budget
coordinator. Earlier measurement sources, raw archives and release artifacts
must remain unchanged. The new observer is under `experiments/iq_comparison`.

## Hypotheses and independent responsibilities

**Measurement hypothesis:** a producer's actual source-publication operation
and a consumer's actual selection can be identified without inventing exact
event times, and the observer can reject impossible or incomplete traces while
accepting a consumer that reads a publication before the producer records its
post-operation timestamp.

**Future performance hypothesis:** removing the snapshot payload copy from
producer synchronization reduces complete producer work at matched useful
retention, request completion and byte verification. Bounded descriptor work,
two ingress copies, cache traffic and owner scheduling may instead make it
slower. That is an acceptable experimental result.

One implementation agent owns the C++ observer and adapters. A second agent
owns independent trace validation and corrupted-trace/executable controls.
The parent owns this preregistration, review, cross-platform checks and evidence.
No long timing comparison runs while these implementation tasks are active.

## Event identity and time bounds

Initialize each immutable source descriptor before release-publishing its
unique ID. Record timestamps immediately before and after the atomic store.
The client records its own timestamps around an acquire load and the ID
actually returned, then uses that descriptor's exact source interval. The
producer's post-store timestamp belongs to a separate owner-only trace row;
the client must not read it while it is still being written.

Release/acquire ordering establishes visibility when the reader observes the
publication. It does not guarantee a scheduling deadline. This follows from
the [C++ memory-order contract](https://eel.is/c++draft/atomics.order).
The timestamp brackets bound operations; neither endpoint is an exact
linearization timestamp. A source ID ties selection to publication independently
of whether the timestamp brackets overlap.

For a selected publication bracket `[p0,p1]` and selection bracket `[s0,s1]`,
the simple necessary causal bound is `p0 <= s1`, subject to declared
cross-thread clock uncertainty. Requiring `p1 <= s0` would incorrectly reject
a reader that observed the store while the producer was preempted before `p1`.
Matching IDs, initialized metadata, valid coverage, source progression and
same-role order are additional requirements; this single inequality cannot
prove an entire trace correct. Newer publications provide observed-staleness
diagnostics, not an invented portable happens-before relationship from wall
time alone.

Clock metadata must distinguish the nominal C++ steady-clock period from
measured or platform-reported resolution. Microsoft's QPC guidance explicitly
calls cross-thread values within one counter tick ambiguous. A validator
must not reject such near-equal observations as certainly impossible. Prefer
a documented platform counter basis; never use UTC for elapsed work.
[Windows high-resolution timing guidance](https://learn.microsoft.com/en-us/windows/win32/sysinfo/acquiring-high-resolution-time-stamps)

Sleep/wakeup lateness remains a host-scheduling measurement. Resource and
scheduling delays can extend a requested wait; these timestamps do not
measure hardware I/Q loss. [C++ timing requirements](https://eel.is/c++draft/thread.req.timing)

## Work accounting and matched source profile

The first instrumentation profile uses 3.072 MS/s, 10 ms producer blocks,
250 ms snapshots at 10 requests/s, one stream/epoch, and an exact 8 MiB useful
history capacity. Its initial 30-block prefill does not yet reach that capacity
(1,843,200 CU8 bytes or 7,372,800 CF32 bytes); record actual retention separately.
The later comparative screen requires full-retention warmup in both formats.
CU8 and CF32 contain deterministic opaque bytes; byte checks do not
make these synthetic RF waveforms or test a demodulator. The source pattern and
verification must match across adapters. Both formats have slab-aligned block
ends in this profile, so no adapter receives a newer unsealed partial tail.

The whole-copy adapter uses the frozen-compatible `CreditHistory` interface.
The candidate uses immutable slabs and the already tested coordinator with
the required shared retirement budget. The no-reader control keeps the
whole-copy producer path and disables snapshot requests.

The main producer work interval must include input-pattern generation,
append/copies, state lookup, source-descriptor preparation/publication,
coordinator service and reclamation. At most three coordinator service phases
occur in an owner iteration, each with its own call bracket, all charged to
that same producer interval. There is no unmeasured service worker. Payload
generation is included and must also be reported separately so it cannot
conceal the cost of the history implementation.

Trace buffer allocation happens before the timed workload. Per-role trace
storage and input buffers are declared separately from the 15 MiB source
payload budget, metadata reservations, and actual process resident memory.
Log serialization happens after both workers join. Final drain, close and
reclamation are separately measured/reported rather than silently discarded
or mixed into regular block percentiles. Timing instrumentation has its own
cost; the no-reader control does not remove every differential overhead.

A client selects its source once per scheduled request. Busy, deadline,
missing-history, failed append and abandoned requests remain in the result.
Never retry against an easier interval and count only the successful attempt.
Verify all accepted bytes and stream ID, epoch, rate, center frequency,
format/width and sample interval. This first observer releases immediately
after verification; exception controls also test cleanup of obtained leases.
Release is observed after ownership reset returns. Later held-lease workloads
must start the hold clock after verification and label a shutdown-shortened
hold as censored rather than count it as a complete requested hold.

The coordinator's supplied tick checks are soft admission checks. Owner service
call brackets observe phases, but without request attribution they cannot
provide a particular request's exact grant latency. Take brackets identify when
the reader obtained a result. The whole-copy operation can block during its copy, so an
after-copy elapsed check cannot enforce a hard deadline. Record deadline
outcomes and observed latency separately. A queued request is not a granted
or verified snapshot.

## Instrumentation acceptance before timing

Require all of the following before a new comparative speed screen:

- Normal no-reader, whole-copy and coordinator runs preserve source identity,
  requested work, ownership and every accepted byte.
- Deliberately pause after the publication store and before its post-stamp;
  prove that the reader can select this version during the bracket and that
  independent validation accepts the overlap.
- Controls detect an unknown/unpublished ID, wrong provenance or interval,
  impossible time bounds, duplicated or missing rows, nonfinite numbers,
  altered bytes, failed append and incomplete worker output.
- Exceptions join workers, retain failed attempts and produce useful evidence.
  A trace hash is computed from the same one-time byte read that is parsed.
- Validation remains active under optimized Python. Strict native builds,
  Windows/Linux execution, and separate memory/race checks gate readiness.
  Android compilation alone does not establish phone runtime correctness.
- Structural validity is distinct from readiness for performance inference.
  An observer cannot prove from its own trace that its source omitted no work;
  source review and a frozen build identity remain necessary.

## Preregistered future screen

Freeze the exact harness, validator, runner, binaries and source revisions
after the instrumentation checks. Preserve complete commands, host/compiler,
clock, power/scheduling context and raw traces. Use sequential isolated trials,
three 30-second CF32 rounds per variant with rotated order, then a no-reader
control in each round. The run order must be recorded before the first run.
Warmup, exact request count, drain interval and percentile definition must be
fixed in the runner manifest before timing begins.

The earlier gates remain: at least 95% of contemporaneous baseline completed
requests; exact accepted bytes; no in-profile append rejection; at least 25%
lower median of complete-producer p99 values; and lower p99 in at least two of
three paired rounds. No additional producer work intervals may exceed 10 ms.
Report request-to-grant/take/verification, completion and deadline counts,
source age, wake lateness, process CPU time, copying/verification work and
payload/metadata/retirement reservations. Never substitute historical 728 us
for the new paired baseline. Missing required observations block promotion.

Passing permits longer tests with other formats, held leases, irregular
callbacks and delayed workers. App integration still requires actual source
drivers, decoder scatter/gather continuity, duplicate-free history-to-live
handoff, RF/device acceptance and protocol/frame/PCM regressions. This
instrumentation increment does not produce an APK/EXE release.

## Result status

Local reviewed builds pass **34 Python test methods** in both normal and
optimized execution: 29 independent synthetic methods and five executable
groups covering 20 bounded cases. A separate real-core cleanup test passes
**four groups, 4,083 checks and 4,000 exact bytes**. These same checks pass when
the observer is rebuilt against the four byte-verified historical whole-copy
files. The parent preserved 20 current-source and 11 frozen-source short runs,
including failed input, exceptions, byte corruption, overlapping publication
and pending/held shutdown. These 31 runs are correctness evidence, not samples
from the future performance experiment.

The independent review found and corrected two measurement gaps: semantic
phase order could previously be fabricated by reordering rows, and a successful
coordinator take could appear without any acquisition/grant/ready transitions.
Validation now requires unique, bracket-feasible transition cycles and checks
the supplied deadline ticks, including exact equality. It still does not replay
the entire coordinator state machine or independently derive the observer's
shutdown acknowledgement. Necessary event checks are not a full concurrency
proof.

Review also found a cleanup defect in this new observer: it cleared a pending
ticket even when `take` returned without consuming the reply. The shared
`take_pending` helper now retains that ticket for exception/shutdown cleanup.
The separate deterministic C++ test exercises real Empty, TickRegression and
NotCurrent results, successful delivery and consuming error replies. It does
not depend on inducing a host clock anomaly during a timed run. No change to
the previously frozen history or coordinator libraries was required.

Both observer and cleanup-test executables cross-compile with NDK 28.2 for
Android arm64-v8a and armeabi-v7a; ELF class/machine match each target. These
executables have not run on a phone and are not an APK. Remote Windows/Linux
and sanitizer results will be recorded at the pushed code revision.

Every result remains performance-ineligible. CPU-time and measured memory
fields are explicitly null; warmup is not yet full-retention; exact per-request
grant attribution and a frozen comparative runner remain pending. The observer
uses immediate release and expensive per-byte progress recording. No latency
ranking, decoder-quality claim, application change or new public package is
established by this checkpoint.

### Preserved remote detector-control failure

At observer code `67f398ad39d2f908b0f73d9dc8ef080234fdb4b8`, the
[PR workflow](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36123911463)
passed Windows/MSVC, Linux, ASan/UBSan and TSan, including its actual deliberate
race diagnostic. However, the duplicate
[push workflow](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36123907941)
correctly stopped its TSan job before candidate tests: the single-write control
exited zero without a race diagnostic. Both outcomes and full logs are
preserved. The passing run must not hide the failed control.

The exact cause of that miss is unknown. The bounded control now exposes
1,048,576 intentionally conflicting volatile writes per writer with periodic
yields, and the checker runs three predetermined independent processes.
**Every process must produce the actual race diagnostic and exit 66.** A miss,
unrelated error or timeout fails the gate; there is no retry-until-success.
Each process's raw stdout/stderr and classification are retained. Ten
independent checker tests pass in normal/optimized Python, including early,
last and all-failed controls, wrong exits, unrelated diagnostics and timeout
output preservation. Those mocked checker tests are not sanitizer execution.

Longer conflicting-access exposure is a test hypothesis, not an explanation
of the original miss or a promise of universal race detection. TSan observes
executed instrumented code and has documented limitations.
[ThreadSanitizer documentation](https://clang.llvm.org/docs/ThreadSanitizer.html)
