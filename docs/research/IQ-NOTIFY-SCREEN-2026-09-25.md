# Notification handoff: correct integration, CPU screen rejected

25 September 2026. Implementation revision
`86690944510ff787c5225f391ba7854f310eadb8`.
The fixed six-run experiment completed once, with no retry or changed thresholds.
The notification candidate **fails promotion**: median process CPU is 5.98% lower,
short of the preregistered 10%, and it wins only one of three paired CPU comparisons.
Every request verifies correctly. Producer tail latency improves in all pairs,
but that does not override the failed CPU gates.

This is a source-storage/handoff experiment using deterministic opaque bytes.
It does not establish faster DMR, NXDN or P25 decoding, better reception, clearer
audio, lower phone battery use, or simultaneous radio-channel capacity.

## What was implemented and tested

The new schema-5 observer uses the unchanged bounded slab/coordinator and tested
notification primitive. One immutable token mapping is published before core
submission, captured at the actual Acquired phase and signaled only at its
matching Ready phase. Normal notification waits do not poll the source stage.
Error responses still require take/drain; an error notification cannot create
a successful lease or override a source deadline. Exceptional cleanup is explicit
and excluded from measurement. Both roles join before object destruction.

An independent sidecar validator applies the frozen schema-4 source checks using
an explicit version projection. It preserves counts, identities, status and
timestamps, then checks request/token lifecycle, exact three-phase binding,
charged owner intervals, wait provenance, shutdown, counters and bounded storage.
No strict notify-return-before-wait-return assumption is imposed: those brackets
can overlap. The underlying predicate/condition-variable ordering follows the
[C++ condition-variable contract](https://eel.is/c++draft/thread.condition.condvar).

Final checks pass 26 observer methods under both normal and optimized Python:
23 synthetic validation controls and three groups containing 18 short native
cases per mode. Twenty independent driver-policy tests check the fixed ordering,
exact gate boundaries, complete timing ledger, rejected and late replies,
retained-output hashes, input integrity and failure preservation.

Earlier short failures are retained. They exposed unfinished source outcomes
after failed notification waits, mismatched expectations about explicit cleanup
identity, and confusion between source-ready and notifier-ready after close.
Review also corrected the driver's handling of rejected requests and required
saved CSV/sidecar hashes to match the exact bytes validated, with final rechecks.
All fixes preceded the first performance trial. No earlier core or schema changed.

Both [PR CI](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36132421014)
and [push CI](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36132416869)
pass Windows/MSVC, Linux, ASan/UBSan and TSan. Each TSan job first diagnoses all
three predetermined deliberate races. Existing receiver/NXDN, observer,
coordinator and framework checks pass. Macroscope remains skipped at its
configured cost limit; it is not counted as a new review pass.

The actual research executable also cross-compiles for Android arm64-v8a and
armeabi-v7a, with ELF identity checks. These are console research targets, not
new APKs. Device execution, physical RF and listening acceptance remain pending.

## Fixed comparison

The [preregistration](IQ-NOTIFY-SCREEN-PREREGISTRATION-2026-09-25.md) was committed
before measurement. One fresh Release executable serves both modes. Each run is
30 seconds with 140 prefill blocks, 8 MiB useful history, 15 MiB source payload,
3.072 MS/s CF32-sized input, 10 ms owner cadence and 300 requests for 250 ms
snapshots. Source eligibility remains 50 ms; the separate notification safety
timeout is two seconds. Both agents and all local builds stopped during timing.
Ordinary OS and user background activity was uncontrolled, not terminated.

The CPU window includes worker launch, waiting, byte verification and shutdown
through join; it excludes prefill and serialization. Producer p99 includes
generation, source copies, core service, notification/binding work and trace
writes. CPU and wall time are separate measurements.

| Round / fixed order | Poll CPU (s) | Notify CPU (s) | Poll owner p99 (ms) | Notify owner p99 (ms) | Poll take p99 upper (ms) | Notify take p99 upper (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1: poll → notify | 5.750000 | 6.031250 | 1.5610 | 1.1657 | 16.7254 | 16.6834 |
| 2: notify → poll | 5.250000 | 5.406250 | 1.5583 | 1.2887 | 16.5555 | 16.6882 |
| 3: poll → notify | 6.062500 | 5.156250 | 1.5529 | 1.1882 | 17.1038 | 16.7031 |

Both modes deliver **900/900 eligible, accepted and exactly byte-verified requests**.
No run adds owner work above 10 ms. All per-pair owner and take latency guards
pass. Notification's normal wait polling count is zero. Median CPU is
5.40625 s versus 5.75 s: a 5.98% decrease, with only one paired win. Therefore
both CPU gates fail and the candidate stays experimental.

An additional reported metric moves the other way: request-to-verification p99
upper bounds are 30.9804 / 31.0083 / 30.4798 ms with notification versus
28.5085 / 28.1374 / 29.1828 ms with polling in rounds 1 / 2 / 3. This was not a
preregistered promotion gate, so it is reported separately rather than silently
changing the decision rules. It prevents any claim that all delivery latency
improved; producer completion and consumer verification are different endpoints.

Three pairs are a screening result, not a significance estimate. The producer
tail improvement does not prove why CPU changed, and wall-clock subintervals
cannot be subtracted from process CPU to assign a cause. The synthetic generator
and verifier are substantial parts of this workload; their cost is not a radio
decoder's cost. No comparison against historical schema-4 CPU values is used.

## Evidence and next decision

[Machine-readable result](evidence/iq-notify-screen-2026-09-25.json) and
[raw evidence archive](evidence/iq-notify-screen-2026-09-25-raw.zip) preserve all
six attempts, source and sidecar traces, exact commands, fresh executable/build
identities, immutable manifest, Android ELF targets, local/CI logs, independent
audit and earlier failing controls. Archive integrity details appear in the
machine-readable record. Sources and outputs are rehashed after validation;
the earlier 64-input study and its frozen raw archives remain unchanged.
The independent audit reproduced all six saved metric sets and the decision,
and verified 70 frozen inputs plus 42 retained-output hashes, including a final
112-file recheck.
The raw archive contains 1,027 entries and 10,556,503 bytes; SHA-256
`2fcb49f7f2da60c2e97e699a2a449cde70219f73c63b8a640ea473d698e18bfa`.
Every archive entry was reopened and byte-verified.

Do not repeat this same comparison until it appears favorable or expand the
storage design into application defaults. If further storage work is justified,
first perform one separately preregistered attribution study using actual worker
CPU counters with explicit process/thread accounting scopes. OS/CV allocations,
native forced safety-timeout and standard-library exception injection remain
unmeasured. Fixed object sizes and vector capacities are not RSS.

The next receiver priority is the existing
[sample-indexed acquisition/recovery plan](ACQUISITION-HYPOTHESES-2026-09-25.md):
tie initial valid frames and audio to consumed input samples, then test bounded
timing/recovery candidates against known payloads, impaired captures and negative
controls. A useful storage design must eventually show benefit on those actual
receiver outcomes. Released APK/EXE artifacts, defaults and user settings remain
unchanged by this experiment.
