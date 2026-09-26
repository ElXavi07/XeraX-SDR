# IQ-history latency experiment — 25 September 2026

## Hypothesis and decision rule, written before the screening trials

Releasing the history mutex between small, validated copy chunks may reduce
producer tail delay. It may also reject more snapshots under contention. A
latency improvement bought by discarding useful work is not an automatic win.

Compare five variants: no snapshots, the frozen previous whole-copy credit
prototype, the updated whole-copy credit path, 64 KiB chunks, and 256 KiB chunks.
The updated whole path isolates the change to atomic credit release; chunked
paths additionally use try-lock, cooperative deadlines, cancellation and an
internal reset generation. The original baseline files are frozen independently.

For the first three-round CF32 screening, a chunked variant is only worth the
next longer workload test if all of these hold:

1. Every accepted snapshot matches every expected byte and its interval; no
   append rejection, leaked credit or payload-budget mismatch occurs.
2. At least 95% as many snapshots complete as in the frozen whole-copy baseline
   at the same request/hold setting.
3. The median of per-run append p99 times is at least 25% lower than baseline,
   and its p99 is lower in at least two of the three matching rounds.
4. Append calls taking longer than a 10 ms input block are no more frequent.

These are screening criteria, not statistical proof, hard-real-time guarantees,
or permission to enable this code in the APK/EXE. Remaining gates include longer
and different workloads, phone measurement, live sample provenance, bounded
integration and duplicate-free retrospective/live handoff.

## Reproducible workload

`experiments/iq_history/latency.cpp` drives a producer with 10 ms blocks at the
equivalent byte rate of 3.072 million complex samples/s. CU8 uses two bytes per
sample and CF32 uses eight. Contents are deterministic index-dependent opaque
bytes; this is not an RF signal, modulator or physical device.

The ring is 8 MiB with one preallocated 7 MiB snapshot slot: 15 MiB of payload,
excluding C++/allocator overhead, the producer block and measurement traces.
The 300 ms prefill is outside measurement. Requests copy the latest 250 ms at
10 requests/s. The selected hold duration is a minimum starting after byte
verification. Release is checked only on the next 100 ms request tick, so a
requested 500 ms commonly occupies about 600 ms; actual lease lifetime was not
recorded by this first harness. Further requests during a held lease return
busy. The chunked deadline is 50 ms.

Measure each append call separately from producer wake lateness. The scheduled
deadline is the next 10 ms block boundary; also count append calls themselves
exceeding 10 ms. Neither counter is a physical SDR drop count. The producer never
silently skips source indices. Every successful snapshot is fully verified;
verification is additional consumer CPU/cache work outside the copy-call timer.
Rejected-request times and completed-request times are reported separately.
Fewer accepted snapshots also mean less verification work, which confounds
latency-only comparisons; the completion gate prevents calling that a win.
Consumer wake lateness and catch-up bursts are not measured: zeroes in the CSV
snapshot wake column are placeholders, not observed zero latency.

`run_latency.py` executes variants sequentially with rotated order between
rounds, records binary/source/trace hashes, preserves stdout/stderr and raw CSV,
and recomputes reported nearest-rank percentiles and counts from the trace.
No timer-resolution, scheduling-priority, affinity or power-plan changes are made.
Host background activity and thermal/frequency state are uncontrolled.
Three rotations do not fully balance five variants. Confirmation would require
balanced ordering and more repetitions; this is only a screening experiment.

First screen: three 30-second CF32 rounds, hold 0 ms. Secondary observations:
one 15-second CU8 round with hold 0 ms, and one 15-second CF32 round with hold
500 ms. These short secondary runs cannot establish a reproducible improvement.

Example (after building the frozen and candidate executables):

```powershell
python experiments/iq_history/run_latency.py --baseline build/iq-history-frozen-274677a/latency.exe --candidate build/iq-latency-20260925/xerax_iq_history_latency.exe --out build/iq-latency-screen-cf32 --seconds 30 --rounds 3 --formats cf32 --holds 0
```

## Timing basis and limits

Use `std::chrono::steady_clock` interval measurements rather than civil time or
direct processor-cycle counts. Microsoft's [high-resolution timestamp guidance](https://learn.microsoft.com/en-us/windows/win32/sysinfo/acquiring-high-resolution-time-stamps)
distinguishes local interval measurement from UTC time and warns against direct
TSC assumptions. Its [Sleep documentation](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-sleep)
also explains that becoming runnable does not guarantee immediate execution.
That is why wake lateness is separate from append-call duration here. We do not
assume a ready software thread emulates a USB driver's timing.

Reducing bytes copied per critical section does not bound wall-clock lock time:
the scheduler may preempt a lock holder. A cooperative deadline is checked at
chunk boundaries; it cannot interrupt an in-progress copy or OS scheduling pause.
No missed RF sample, uncaptured frequency or unknown encrypted payload can be
recovered by this storage experiment.

The first harness checks every accepted byte, epoch, interval and length. It
does not independently compare every stream metadata field in the timed run;
the separate contract tests exercise those fields. A verification exception
fails the process, but this harness writes CSV only after successful joins and
checks, so a failed process may have incomplete trace evidence. Later harness
revisions must preserve partial traces and detailed failure context rather than
changing or replacing the measurements already made here.

## Primary CF32 results

Three 30-second rounds completed for every variant. Each trial ingested 3,000
blocks; each snapshot-enabled trial requested 300 snapshots. Every accepted
snapshot passed the harness's byte/interval checks, and every run ended with
zero outstanding credits and the declared 15 MiB payload budget.

| Variant | Median of three per-run append p99 | Completed snapshots | Per-round append p99, microseconds |
| --- | ---: | ---: | --- |
| No snapshots | 108.9 microseconds | Not requested | 101.5 / 108.9 / 123.8 |
| Frozen whole-copy baseline | 728.0 microseconds | 900 / 900 | 681.6 / 728.0 / 798.1 |
| Updated whole-copy credits | 749.5 microseconds | 900 / 900 | 704.1 / 761.6 / 749.5 |
| 64 KiB chunks | 988.8 microseconds | 280 / 900 | 873.0 / 988.8 / 1,020.7 |
| 256 KiB chunks | 1,038.1 microseconds | 443 / 900 | 977.6 / 1,038.1 / 1,118.2 |

**Both chunked candidates fail the predeclared screen.** They complete only
31.1% and 49.2% of baseline's useful requests, below the 95% gate. Their median
append p99 is 35.8% and 42.6% higher, rather than at least 25% lower. Neither
beats baseline in any paired round. All rejected primary requests are `Busy`;
there are no deadline or not-retained rejections in this workload. Updated
whole-copy credit release does not demonstrate a latency improvement either.

No append call exceeds 10 ms. Nevertheless, between 2,591 and 2,688 of 9,000
scheduled block deadlines are missed per variant, including 2,591 with no
snapshots. Wake scheduling is a substantial limitation of this desktop pacing
experiment. These counts are not physical SDR drops or proof that a production
driver would lose samples. The whole-copy path also remains unqualified for
live deployment; winning against this rejected candidate does not satisfy the
remaining application gates.

The result rules out promoting this particular try-lock chunking design under
the declared workload. It does not prove that every chunking design must fail,
or establish causality between a particular lock/cache mechanism and the delay.
Keep the experiment, failures and frozen baseline; investigate a separately
declared bounded ownership design before another performance screen.

## Secondary observations

These are single 15-second trials per variant, not confirmation runs. The
500 ms hold condition intentionally makes a one-slot pool return `Busy` while
the consumer holds its previous lease. It is not a request for 150 simultaneously
retained snapshots. Its release quantization is described above.

| Variant | CU8 hold 0: append p99 | CU8 completed | CF32 minimum hold 500: append p99 | CF32 completed |
| --- | ---: | ---: | ---: | ---: |
| No snapshots | 56.1 microseconds | Not requested | 103.9 microseconds | Not requested |
| Frozen whole-copy baseline | 280.8 microseconds | 150 / 150 | 209.4 microseconds | 26 / 150 |
| Updated whole-copy credits | 262.6 microseconds | 150 / 150 | 284.6 microseconds | 26 / 150 |
| 64 KiB chunks | 298.6 microseconds | 73 / 150 | 464.4 microseconds | 19 / 150 |
| 256 KiB chunks | 323.5 microseconds | 104 / 150 | 485.6 microseconds | 23 / 150 |

Neither chunk size improves the frozen baseline's p99 or completed-work count
in either secondary condition. One CU8 run favors updated whole-copy credits
slightly, but the primary repeated CF32 screen does not support a general
improvement. All accepted secondary snapshots also pass byte/interval checks.

## Evidence and next step

The [machine-readable report](evidence/iq-history-latency-2026-09-25.json) preserves
all 25 trial summaries, source/binary/trace hashes, calculated gates and limits.
The [raw evidence archive](evidence/iq-history-latency-2026-09-25-raw.zip) includes
all 25 CSV/stdout/stderr traces, frozen baseline and candidate source, the exact
original orchestrator, reproduction instructions and an entry-level SHA-256
manifest. It contains no application executable or radio capture. Its 96 entries
were re-read and verified after packaging; archive SHA-256 is
`acd459a7df64d8c7ff35f86c3d3babaaafb2c74c3c716e5a0d3d96fc676fbd03`.

After measurement, the orchestrator gained explicit exceptions in place of
Python assertions, exact rejection-category/workload checks, launch-failure
records and its own source hash. Fourteen negative/positive-control unit tests
pass in both normal and optimized Python. The stricter validator rechecked all
25 saved trials and their trace hashes; no measurement was edited or rerun.
The original script remains in the evidence archive so this hardening cannot
silently change the provenance of the first screen.

Next, improve failure trace retention and consumer/lease timing before testing
the [bounded immutable ownership hypothesis](IQ-HISTORY-NEXT-HYPOTHESIS-2026-09-25.md).
That proposal retains an exact memory ledger and comparable useful retention.
It remains a theory until independent contract tests and paced measurements
pass. The current prototypes remain disconnected from the live receiver.
