# Fully warmed IQ-history screen: measured rejection

**25 September 2026. The candidate did not pass.** Across three fixed paired rounds,
complete producer p99 was **15.4% higher** for the immutable-slab/coordinator
candidate. Median measured process CPU was **11.9% higher**. Both implementations
completed all 900/900 deadline-eligible, fully verified requests. The candidate
remains an isolated experiment; no APK/EXE default or release package changes.

## Frozen design and evidence

The [preregistration](IQ-SCREEN-PREREGISTRATION-2026-09-25.md) was written before
comparative timing. The new schema 4 observer at revision
`98457d76788e077a55f2ea88ed18fc67eeaee2b2` uses actual process CPU counters,
140 prefill blocks, full 8 MiB useful retention, bounded source ownership and
conservative per-request grant bounds. The four whole-copy comparator files
are byte-identical to Git revision `274677a`. Previous schemas and results stay frozen.

The runner built fresh Release/Ninja binaries with GNU 16.1 and identical effective
compiler options. It ignores only generated output-object paths in that parity
check, not flags. Input hashes were recorded before building, checked after
preparation, frozen before the first trial, and checked around every run.
The manifest binds sources, binaries, actual compile commands, separate allocation
calibration, host context and the predetermined nine-trial order. No trial was
repeated or discarded. The final decision and all nine traces were independently
revalidated; regenerated metrics exactly matched the saved reports.

This is a synthetic **opaque storage-byte workload**, not a CF32 demodulation
waveform. It exercises 3.072 MS/s in 10 ms blocks, 250 ms snapshots at 10 Hz and 50 ms
soft return checks. Exact verification occurs after the return check and is
reported separately. Each run contains 3,000 timed producer iterations; every
accepted byte is checked. This does not measure receiver sensitivity, frame error
rate, call acquisition, vocoder quality or app audio latency.

Host: Intel Core i5-1038NG7, 4 cores/8 logical processors, Windows x64, Balanced
power plan and normal process priority. Agent work and competing experiment/build
jobs stopped during trials; normal OS/user background activity was uncontrolled.

## All nine runs

Producer p99 includes generation, copies, source-state/publication observations,
coordinator service and reclamation. CPU is actual aggregate process time from
before worker launch through joins; it includes verification, waits and drain,
and excludes prefill and report serialization.

| Round | Variant | Producer p99(ms) | Process CPU(s) | Eligible / scheduled | Work >10 ms | Finished after next block |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | No reader | 1.1706 | 1.328125 | 0 / 0 | 0 | 979 |
| 1 | Frozen whole copy | 1.2783 | 5.046875 | 300 / 300 | 0 | 994 |
| 1 | Candidate | 1.4767 | 5.453125 | 300 / 300 | 0 | 965 |
| 2 | Frozen whole copy | 1.2775 | 4.875000 | 300 / 300 | 0 | 994 |
| 2 | Candidate | 1.4717 | 5.203125 | 300 / 300 | 0 | 931 |
| 2 | No reader | 1.2022 | 1.406250 | 0 / 0 | 0 | 980 |
| 3 | Candidate | 1.4752 | 5.875000 | 300 / 300 | 0 | 1020 |
| 3 | No reader | 1.1684 | 1.750000 | 0 / 0 | 0 | 1003 |
| 3 | Frozen whole copy | 1.2782 | 4.859375 | 300 / 300 | 0 | 970 |

Baseline median of per-run p99: **1.2782 ms**. Candidate: **1.4752 ms**.
Per-round regressions are 15.52%, 15.20%, 15.41%; the candidate wins 0/3 rounds.
The required 25% median reduction and at least 2/3 paired wins both fail.
All completion, exact-byte, ownership and work-over-10-ms gates pass. The final
negative performance decision is therefore a completed experiment, not a broken
test that should be repeated until passing.

Median process CPU per 30-second run: 1.40625 s no-reader, 4.875 s whole-copy,
5.453125 s candidate. The candidate uses more CPU in every paired round.
Windows CPU counters use 100 ns storage units; this is not an empirical resolution
claim. No confidence interval or universal performance conclusion follows from
three rounds on one host.

All variants have substantial scheduling lateness: producer p99 wake offsets
are roughly 23.8–25.8 ms. The last column counts scheduled completion overruns,
not long producer-work intervals. These are Windows scheduling observations,
**not observed RF/sample losses**; the synthetic source catches up its sequence.

## Handoff and cost interpretation

Per-run request-to-grant p99 upper bounds are 1.159–1.293 ms for whole-copy and
16.541–16.841 ms for the candidate. Candidate request-to-take upper-bound p99
closely follows 16.543–16.844 ms. Selection-to-verified p99 is 15.22–15.59 ms for
whole-copy and 27.68–28.43 ms for the candidate. These are conservative operation
brackets and observed completion intervals, never exact internal grant times.
Publication-to-selection p99 age is approximately 29–30 ms in both. All requests
still pass the declared soft return checks.

Generation accounts for 91.66–91.74% of summed candidate producer wall intervals
and 94.74–94.91% of whole-copy intervals. Generation p50 is similar, around
640–644 microseconds, while generation p99 is higher in the candidate runs.
Nested wall intervals include preemption, and percentiles are nonadditive:
these observations do not isolate the cause of the producer regression.
Candidate non-generation p50 is about 53 microseconds versus 26; its non-generation
p99 is lower, about 134 versus 169–219 microseconds. Reporting only this smaller
component would conceal the failure of the complete producer interval.

Calculated explicit source-copy payload lengths per timed reader run are
2,580,480,000 bytes for whole-copy (ingress plus snapshot copies) and
1,474,560,000 bytes for the candidate (two ingress copies). Both verify/read
1,843,200,000 snapshot bytes. These are code-path payload lengths, **not measured
DRAM traffic**, cache misses or bandwidth. Fewer explicit copy bytes did not
produce lower overall CPU consumption in this screen.

## Memory accounting

Both endpoints retain exactly 8,388,608 useful bytes within 15,728,640 payload bytes.
Every run ends with zero outstanding ownership. The independent whole-copy
calibrator observes five allocations and five frees, no operational allocations,
240 heap metadata bytes including its 136-byte facade, and a 96-byte lease
reservation: 336 metadata bytes. It explicitly tests source destruction while a
lease survives, followed by zero remaining tracked bytes.

The candidate exposes 48,152 bytes of slab/ledger metadata, 832 bytes of coordinator
reservation and 48 facade bytes. Baseline source allowance is 15,728,976 bytes;
candidate source allowance is 15,777,672 bytes. **Do not interpret this subtraction
as a process-memory comparison.** The metadata bases differ: measured C++ heap
requests plus one lease reservation versus API allocations/fixed reservations.
They exclude allocator overhead, RSS, thread stacks, runtime objects, trace
buffers and input storage. Those observer buffers are disclosed separately.
Equal bounded payload and returned ownership are the common gates.

## Correctness, builds and preserved failures

- 49 observer methods pass in normal and optimized Python, including 20 short native
 cases and both calibration formats. Sixteen independent runner-policy controls
 cover ordered gates, completion, metric validity, compilation parity, failure
 retention and integrity failures overriding otherwise-passing metrics.
- An initial short optimized check rejected a legitimate Pending/TickRegression
 service result. Its failure log remains archived. The correction requires a
 feasible newer client submission tick and never treats this nontransition as
 acquired/granted/ready; impossible ordering and missing-cycle controls remain.
- [Final PR CI](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36126716528) and
 [final push CI](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36126712343)
 pass Windows/MSVC, Linux, ASan/UBSan and TSan. Each TSan job first diagnoses
 all three predetermined deliberate races. Its allocation calibrator explicitly
 reports unavailable because replacement allocation operators conflict with
 that instrumentation; this omission cannot authorize a memory-performance gate.
- Existing receiver/NXDN, coordinator, prior observer and benchmark checks pass.
 The third-party Macroscope review skipped this revision at its configured
 per-PR cost limit; it is not counted as a new review pass.
- Both research executables cross-compile for Android arm64-v8a and armeabi-v7a;
 ELF targets are verified. No phone runtime or RF acceptance is claimed.

## Next falsifiable experiment

Keep this failed implementation and result frozen. Test replacing only the
coordinator consumer's yield-poll wait with one preallocated notification token.
The owner would signal terminal readiness inside its already charged service
interval, with no extra service thread, no additional phases and no earlier
source selection. The hypothesis is reduced polling CPU, not a presumption that
polling caused the observed producer regression.

Before measuring, specify and test generation matching, notification-before-wait,
close-before-wait, spurious wakeups, timeout, no lost wakeup and safe destruction.
A standard condition-variable implementation must retain a checked predicate
and the required mutex/lifetime discipline; notification alone is not stored
work. [C++ condition-variable contract](https://eel.is/c++draft/thread.condition.condvar)
Windows WaitOnAddress also requires a value recheck and allows early wakeups;
a platform-specific implementation must document a separate contract.
[Microsoft WaitOnAddress documentation](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitonaddress)

Proposed gates to freeze before new trials: at least 10% lower median process CPU
versus the unchanged polling coordinator; at least 95% absolute and paired eligible
completions; producer p99 no more than 5% worse; request-to-take p99 upper bound no
more than 1 ms worse; all byte, shutdown and metadata-budget checks pass. Charge
all notifier work/memory and preserve every attempted run. A passing CPU screen
would still need longer loads and decoder/source integration; it would not turn
a waiting-time result into faster radio decoding.

## Reproduction record

[Machine-readable result](evidence/iq-warmed-screen-2026-09-25.json) and
[frozen raw archive](evidence/iq-warmed-screen-2026-09-25-raw.zip) preserve all
nine traces, summaries, hashes, build/CI logs, calibration, failed check, source
inputs and Android ELF evidence. The archive contains 176 entries, 4,673,055 bytes,
SHA-256 `6a1ed58d0d67886a69ccffdfa7fb7d66735750167b444f07d80af31b5a95c8b5`.
Every entry was reopened and checked against its captured bytes. Experimental
binaries inside the evidence are research tools, not an APK or Windows installer.
The prior frozen archives, released 4.3.2-rc.1 packages, settings and defaults
remain unchanged.
