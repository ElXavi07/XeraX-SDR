# Fully warmed IQ-history comparison: preregistration

**25 September 2026. Written before comparative timing.** The first target is
an engineering screen on this Windows host, not application integration or a
claim about RF acquisition, frame recovery, intelligibility or phone performance.

Starting revision: `78dcd40b46f740e41ca9cf3f12844a740664e256`. Frozen local source
archive: `build/iq-screen-baseline-78dcd40.zip`, SHA-256
`2921936a2576b9f6b16af03e6dcd142eb584fbcc748868f5490f9d2d2450d7ec`.
The [schema-3 observations](IQ-PUBLICATION-MEASUREMENT-2026-09-25.md), earlier
archives and all released packages remain unchanged. Schema 4 lives separately
under `experiments/iq_screen` and retains the prior observer's event semantics.

## Falsifiable prediction

At equal fully warmed useful retention and deadline-eligible verified work,
immutable slabs with a bounded owner-serviced request will reduce complete
producer p99 relative to the preserved whole-copy implementation. The candidate
must include its two ingress copies, ownership work and reclamation. Increased
CPU consumption, slow grants or missed work are possible costs to measure;
moving work outside the append call cannot earn a speedup.

The comparator uses the four whole-copy files frozen at `274677a`, each verified
against its Git blob. The same new observer and compiler options build the
baseline and candidate. The no-reader control uses the frozen whole-copy
producer, not a different source-generation loop. Libraries remain unchanged.

## Workload fixed before measurement

| Parameter | Value |
| --- | --- |
| Input | Opaque deterministic CF32 bytes, 3,072,000 complex samples/s |
| Producer | 30,720 samples every 10 ms; 3,000 timed iterations per run |
| Warmup | 140 generated/appended blocks before workers launch |
| Useful retention | Exactly 8,388,608 bytes at the first timed publication |
| Snapshot | Last 768,000 samples of the selected publication: 250 ms |
| Requests | Every 100 ms, first due 5 ms after origin; 300 per reader run |
| Deadline | Existing 50 ms soft admission/return checks from selection |
| Verification | Every accepted byte and all exposed source metadata |
| Release | Immediate after verification; no requested additional hold |
| Timed duration | 30,000 ms, with prefill and final drain reported separately |
| Replication | Three predetermined rounds, sequential subprocesses |
| Percentiles | Nearest rank: sorted element at `ceil(p × n) - 1` |

The same 140-block warmup also fills CU8 retention in correctness tests.
Warmup is not a time-based claim about hardware settling. Source bytes remain
synthetic storage data, not meaningful CF32 radio waveforms.

Run order is fixed:

1. No-reader control → frozen whole-copy → coordinator.
2. Frozen whole-copy → coordinator → no-reader control.
3. Coordinator → no-reader control → frozen whole-copy.

Do not run agent experiments, builds or other benchmark jobs concurrently with
this screen. Ordinary OS/user background activity is not fully controlled;
record the host, power plan and that limitation. Use normal process priority.
Do not stop unrelated user applications. Preserve every attempted run, including
failures. A correctness failure stops the screen; a bad performance result is
retained, not rerun until it passes. Instrumentation/source changes require a
new frozen manifest and cannot silently replace part of a paired set.

## Required accounting

Complete owner work includes generation, append, state lookup, descriptor
publication, at most three coordinator phases and reclamation. Keep nested
generation timing as a separate diagnostic; the primary gate uses the complete
interval. Clock reads and trace construction remain observer overhead in all
variants. Scheduler lateness and completion after a scheduled block deadline
are separate from work duration and are not RF-loss measurements.

Sample true process CPU counters before worker launch and after both joins.
That window excludes prefill and CSV serialization but includes launches,
scheduled waits, verification, drain and joins. Windows `GetProcessTimes`
reports aggregate kernel/user CPU across threads in 100 ns storage units;
aggregate CPU can exceed wall time on multiple cores. Storage units do not
establish accounting precision. [Microsoft API contract](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes)

Do not use Microsoft CRT `clock()` as CPU time: its documented result is wall
time. [Microsoft CRT documentation](https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/clock?view=msvc-170)
The POSIX implementation uses the process CPU clock and reports its queried
resolution separately. Counter failures are missing evidence, never zero CPU.

CPU plausibility uses only a deliberately loose bound: reported logical CPU
count times the outer elapsed bracket plus 20 ms per reported logical CPU.
This is a gross contradiction check, not an empirical precision bound. The
logical count is a system hint and not necessarily a container CPU quota.
Zero/unknown CPU count prevents eligibility. Retain raw counter/bracket values.

Memory observations identify fixed source payload, exposed arena metadata,
coordinator retirement reservations, useful retention and outstanding ownership
at endpoints. The whole-copy API does not expose all metadata allocations.
A separate, bounded allocation-calibration executable may measure requested
source heap bytes; allocator hooks must never be linked into the timed binary.
Freeze that executable and the actual selected sources alongside its output.
Do not equate allocator-request bytes or declared fixed reservations with RSS,
commit charge or total process memory. Declare façade, runtime, trace, input,
stack and allocator-overhead inclusions/exclusions precisely. Unequal scopes
cannot support a memory-saving claim. No source ownership may remain outstanding
after the declared drain.

For each admitted coordinator reply, map the unique ordered owner
acquired/granted/ready cycle to the single sequential request. Derive conservative
grant-time bounds from its granted-call bracket and submission constraints;
derive whole-copy grant bounds from its call bracket. Preserve legitimate
overlap with submit/take post-stamps. Report bounds, not invented exact instants.
Request-to-take and verified completion use their own observed intervals.

## Measurement and improvement gates

Before timing, strict builds and independent synthetic/native tests must cover
source provenance, full warmup, legal overlapping brackets, clock/deadline
contradictions, CPU arithmetic, memory scopes and rejected/failed work. Tests
remain active under optimized Python. Retain existing race-control requirements:
all three predetermined deliberate-race processes must diagnose the race before
any clean TSan execution counts. Phone execution remains a separate pending gate.

The runner first freezes commands, source/binary/validator hashes, calibration
identities and host context. A single well-formed trace establishes measurement
eligibility only; the paired decision is separate. Accept a screen for longer
experiments only when all of these predeclared gates pass:

- All nine runs have complete, coherent observations; no in-profile append
  rejection, altered accepted bytes, missing required metrics or leaked ownership.
- Every baseline and candidate reader run completes at least 95% of its 300
  scheduled requests with both successful byte verification and deadline-eligible
  return. Candidate completion is also at least 95% of its paired baseline in
  every round. Late returned grants still get verified and reported separately.
- Candidate median of per-run complete-producer p99 is at least 25% lower than
  the contemporaneous baseline median, and candidate p99 is lower in at least
  two of the three corresponding rounds.
- No round adds producer-work intervals exceeding 10 ms relative to its paired
  baseline. Report no-reader outliers and scheduling overruns separately.

Report all per-run values and paired deltas, CPU totals, grant/take/verification
bounds, source age, completed/rejected/deadline counts, input copies, verification
work and accounting scopes. Three rounds are a screen, not strong statistical
evidence of a universal benefit. No historical p99 value substitutes for the
new baseline. No CPU-saving, RF, GPU or whole-decoder claim follows from a
storage/ownership result.

Passing permits a longer workload study; it does not enable the candidate in
APK/EXE defaults. Failing rejects this implementation/profile as a latency
improvement under the declared gates. Preserve either result and choose the
next experiment from evidence.

## Status

Measurement implementation and independent checks are in progress. No
comparative timing under this contract has started.
