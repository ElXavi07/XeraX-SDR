# Polling versus matched notification: preregistered screen

25 September 2026. Written before any comparative notification performance run.
Starting revision: dcddc4dc572ac5e034424ca602a860285f2e05a3. Frozen source archive
`build/iq-notify-screen-baseline-dcddc4d.zip` SHA-256:
`d36c978b2149364e9313ff7fa95a13cbf0208afd25e1cdb45a7c71946810dda0`.
The [primitive and mailbox contract](IQ-NOTIFICATION-CONTRACT-2026-09-25.md)
and rejected schema-4 study remain unchanged.

## Hypothesis

Replacing yield polling with one matching readiness notification reduces process
CPU while preserving request completion and producer/take latency. The workload
tests storage, scheduling, exact-byte verification and handoff. Opaque CF32-sized
bytes are not radio waveforms. This cannot measure decoder accuracy, RF recovery,
audio quality, multi-channel decoding or application battery life.

## Prerequisites and fixed treatment

New schema-5 observer, independent core/sidecar validation and corruption controls;
strict Release builds and Python checks with and without optimization; Windows,
Linux, ASan/UBSan and TSan (after all three deliberate-race controls diagnose).
Android targets compile and ELF identities are checked; phone runtime is pending.
The schema-4 projection declares its version and changes no source observations,
counts, status or timing. Existing source/slab/mailbox/notification cores remain
frozen. Every trace operation is bounded and complete or the run is invalid.

Use one freshly built executable for both modes, so compiler flags and code
identity match exactly. `poll` keeps the coordinator's original stage-yield loop;
`notify` arms before submission, publishes an immutable token by request ID,
captures it at Acquired and signals only that captured token at matching Ready.
Ready error replies still require core take/drain. A notification is not a lease.
The normal notification wait has a two-second safety deadline, separate from
unchanged 50 ms core eligibility checks. Exception-only bounded cleanup polling
must be traced and makes the run ineligible, as do failed waits or missing rows.
No assumption requires notify-return to precede wait-return: calls can overlap.

Both modes trace waiting; notification mode additionally traces arm, mapping,
bind, notify and cleanup. These additional operations are part of the treatment,
not subtracted as instrumentation overhead. Full producer intervals include
mapping, signaling and trace writes. All objects, token arrays and trace storage
have explicit actual-size/capacity accounting. Opaque standard-library/OS
synchronization allocations remain unmeasured; no RSS comparison is inferred.

## Fixed workload and order

One attempt at each of six 30-second runs, three sequential pairs:

1. Poll, notify.
2. Notify, poll.
3. Poll, notify.

Each run uses 140 prefill blocks, fully retained 8 MiB history, unchanged bounded
15 MiB slab payload, 3.072 MS/s CF32-sized deterministic byte source, 10 ms producer
period, 250 ms snapshots, 300 scheduled requests at 10 Hz and 50 ms soft checks.
Process CPU is measured before worker launch through join, including waiting,
verification and drain, excluding prefill and serialization. Windows sums user
and kernel counters; its 100 ns storage unit is not measured accounting precision.
[Microsoft API](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes).

Record actual compiler version/hash, commands, host/power plan/priority, all
source/build/binary hashes, core CSV and sidecar hashes. Verify immutable inputs
before build, after build, around every trial and after the final trial. Freeze
the manifest before trial one. Agents and builds stop during timing; ordinary
OS/user background applications are uncontrolled and are not closed. No retry of
a failed or negative comparison. Preserve every attempt and partial output.

## All promotion gates must pass

- At least 10% lower median process CPU, and strictly lower CPU in at least two
  of three contemporaneous pairs.
- At least 95% of scheduled requests eligible and byte-verified in each mode
  every round, and candidate count at least 95% of its paired baseline.
- Candidate full producer p99 at most 1.05 times baseline in every round.
- Candidate request-to-take p99 upper bound at most baseline plus 1 ms in every
  round. Use nearest-rank p99 over all successfully taken/verified replies,
  including late replies; never silently discard them to improve latency.
- No additional producer work intervals exceeding 10 ms in any paired round.
- All identity, exact-byte, source ownership, shutdown, memory, trace completeness
  and provenance controls pass; accepted grants equal verified grants.

These are engineering screening thresholds, not statistical significance.
Three paired rounds cannot establish a general speedup. Any integrity/correctness
failure stops the series. Negative performance completes a valid experiment but
fails promotion. Passing permits a longer independent study only, not a released
default, app integration, whole-decoder speed or RF claim.

The runner and its negative controls are part of the frozen inputs. If a defect
prevents measurement, retain the failed preflight and describe the fix before a
new preregistration or attempt; never silently change gates after seeing results.
