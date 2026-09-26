# IQ comparison observer, schema 3

This standalone correctness experiment records source publication and consumer selection explicitly. It does **not** run in XeraX SDR, decode a radio protocol, establish a speed improvement or authorize a performance comparison. Every summary reports `performance_eligible: false`. Schema 1, schema 2, the immutable slab core and the coordinator core are unchanged.

The three adapters are:

| Variant | Producer | Consumer |
| --- | --- | --- |
| `none` | Whole-copy history: input generation, append, state and source publication | No requests; controls for the cost of adding readers |
| `whole` | Same whole-copy producer | Synchronous `CreditHistory::snapshot`, exact verification and immediate release |
| `coordinator` | Immutable slabs, source publication, at most three mailbox service calls and reclaim inside each iteration | Submit once, await the explicit reply, take, verify and release |

The whole-copy adapter uses only the older common API. CMake's required provenance choice is visible through `XERAX_WHOLE_SOURCE_DIR`: by default this points at the current `../iq_history` source, **not** the historical frozen implementation. To compare a frozen version, configure this variable to its independently verified four-file source directory. The runner must hash the actual selected sources, executable, observer, validator and trace; the executable does not invent a frozen provenance label.

## Workload and source ownership

The initial correctness profile produces one 10 ms block at 3.072 million complex samples per second. CU8 blocks are 61,440 bytes; CF32 blocks are 245,760 bytes. A request selects one published source event every 100 ms, starting 5 ms after the scheduled run origin, and requests the preceding 768,000 samples (250 ms). The eligibility deadline is 50 ms after the selection load's **after** observation. A request does not reselect an easier or newer interval after rejection.

There are exactly 30 prefill blocks (300 ms), explicitly traced before the scheduled origin. This does **not** fill the whole 8 MiB useful retention capacity, particularly for CU8. These are short correctness runs, not a fully warmed retention benchmark. A subsequent preregistered comparison needs a common full-retention warmup. The byte generator is deterministic opaque data indexed by absolute byte offset. CF32 labels describe the storage width; these are not meaningful floating-point radio waveforms or decoder test vectors.

Each successful producer append is followed by a state query. An immutable, preallocated descriptor records the exact retained first sample, published end sample, stream identity, epoch, rate, frequency, sample width, and real pool/generation identifiers where exposed by the slab core. Whole-copy identifiers absent from that API stay missing. Both ingress sizes pack complete slabs, so the published slab frontier and whole-copy block frontier coincide. No filling-tail approximation is used.

The producer then release-stores the descriptor's monotonically increasing event ID to `latest`. A consumer brackets one acquire-load and copies only the corresponding immutable descriptor. Records remain allocated and unmodified until both threads join. The producer's post-store timestamp lives in its own trace row, not in the descriptor concurrently read by the consumer.

## What the observations establish

All event times are signed integer nanoseconds relative to one scheduled steady-clock origin. Prefill times may be negative. `before_ns` and `after_ns` bracket a call or atomic operation; **neither is claimed to be the exact operation instant**. In particular, a consumer can observe a release-store before the producer resumes to record `after_ns`. Publication/selection association follows the recorded event identity and release/acquire ownership, not a guess that the latest completed producer timestamp must have been the selected publication.

`check_ns` and `deadline_ns` use the same relative trace domain. The coordinator receives nonnegative ticks computed from those actual sampled steady-clock values minus a separate fixed setup origin; the CSV retains their equivalent relative nanoseconds. These are supplied checks, not additional hidden measurements inside the library. A service row brackets the actual `Mailbox::service` call and records its returned stage in `field`. It deliberately has no request ID: this wrapper cannot safely attribute an internal service transition to a particular concurrently changing client request without changing the core. It does not claim an exact per-request grant timestamp.

The independent validator requires unique ordered acquired/granted/ready progress cycles with feasible call brackets for admitted/taken requests. Those are necessary event/tick checks, **not a complete replay or proof of the coordinator state machine**. In particular, terminal acknowledgement remains an observer-reported summary value rather than a reconstruction of every internal shutdown transition. The core's separate ownership contracts and state-model tests remain necessary.

Windows summaries report QPC frequency when available. `steady_clock`'s C++ period is nominal, and the observer has not proved its platform clock mapping or measured hardware clock resolution. The cross-role feasibility tolerance is explicitly declared as the larger of 1,000 ns and one QPC tick, when available. It is not a calibration result. Same-role event ordering requires no tolerance. Cross-role overlapping store/load brackets are valid; a tolerance must not turn an impossible source identity or byte interval into a valid one.

The owner container begins before byte generation and ends after append, state/publication bookkeeping, up to three coordinator service calls and reclaim. There is no hidden service worker. Individual operations have nested trace rows. Producer prefill, timed work and final drain use separate `phase` values; final drain cannot silently enter timed-work distributions. Trace row allocation is preallocated, but filling trace rows, calls to the clock, generation and synchronization still impose observer costs.

Every actual core grant is counted in `accepted` and verified against independently derived expected metadata and every source byte. Verification includes observed identity, interval, byte count, and slab pool/generation where applicable; span coverage must be contiguous and exact. Per-byte progress is written to the verification row so a failure preserves its progress. That observer work differs from schema 1/2 and can significantly affect scheduling; results cannot be extrapolated to those older harnesses or an uninstrumented application.

`eligible` counts successful request outcomes that pass the post-call deadline check. It is distinct from `accepted`: a whole-copy call cannot be interrupted at its deadline, and any late returned grant is still verified and released before receiving a `deadline_expired` outcome. Coordinator submit and take checks also use explicit supplied ticks, and a wrapper post-call check records whether the call had already overrun. This does not create a hard deadline guarantee. Verification is outside the eligibility interval; no deadline is quietly extended to make a request pass.

## Finite evidence and failure handling

The CSV schema uses blank cells for missing observations, never fabricated zero timestamps or identities. IDs are contiguous per role across all event kinds. Owner containers precede their children; `parent_id` links only owner-child events. Consumer events link through `request_id`. The summary reports scheduled versus completed counts, actual grants, successful verification, eligible outcomes, trace capacities, explicit failures, trace persistence and shutdown acknowledgement.

Trace vectors, publication descriptors and the ingress buffer are allocated before worker launch. Owner capacity is `(30 + timed iterations + 1000) * 10 + 16` rows; consumer capacity is `requests * 12 + 32` rows. Durations are bounded to 100–60,000 ms in multiples of 10. A trace-capacity exception increments `dropped_event_count` and invalidates the run. Up to 1,000 final drain iterations are permitted. These buffers, stacks, timestamps, exception runtime storage and allocator overhead are **excluded from the source histories' memory budgets**, and their separate requested capacities are reported. Process CPU time and measured source/retirement memory statistics are explicitly null in this checkpoint; these gaps block a future performance screen.

Both thread objects start empty and construction occurs inside a guarded launch path. Failures signal a stop, retain the first failure per role and count secondary failures. Consumer cleanup consumes an outstanding reply where possible, closes the mailbox and releases held ownership. Threads are joined before facade destruction. Any exceptional post-join ownership cleanup is explicitly flagged, excluded from recorded owner iterations and makes the run fail. Failed runs preserve their bounded trace and JSON summary. A trace-write failure retains a failed summary with `trace_written: false` and `trace_error`; an absent trace cannot be a successful result. Initial setup failure before worker launch exits separately with stderr and no success summary.

The normal profile releases immediately; it has no requested hold duration or hold-censoring measurement. Shutdown acknowledgement means mailbox quiescence, not a claim about process-wide memory reclamation.

Normal take, exception cleanup and post-join rescue share `take_pending`. A non-consuming `Empty`, `TickRegression` or `NotCurrent` result preserves the pending ticket; a caller must not erase the only identity needed to drain a still-Ready response. The separate deterministic real-core `test_pending_take.cpp` exercises this ownership rule with controlled supplied ticks, including an exception between a rejected take and fresh shutdown cleanup. These controlled ticks are not mixed into the observer's real-clock trace schema.

## Bounded fault controls and build

Supported `--fault` values are `none`, `append`, `byte`, `publication-pause`, `producer-exception`, `consumer-exception`, and coordinator-only `pending-shutdown` / `held-shutdown`.

- `append` passes a deliberately misaligned first timed byte count. Its trace reports the actual attempted byte count and the intended sample interval; rejection publishes no replacement samples.
- `byte` alters one local verifier observation at byte offset 17, preserving the immutable source and recording expected/actual values, progress and release.
- `publication-pause` uses a bounded diagnostic rendezvous after the first timed release-store. It forces selection before the producer's post-store stamp and tests legal overlapping publication brackets. It is never an unmodified workload.
- Worker exceptions exercise generation failure and an acquired grant whose verification aborts. The held grant is released with explicit failure evidence.
- Pending/held shutdown controls close the coordinator in those phases and retain reply/drain observations without revoking an acquired lease.

```text
cmake -S experiments/iq_comparison -B build/iq-comparison-agent -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build/iq-comparison-agent
ctest --test-dir build/iq-comparison-agent --output-on-failure

xerax_iq_comparison --variant coordinator --format cu8 --duration-ms 100 --fault none --csv trace.csv
```

The executable emits one JSON summary to stdout and writes the CSV after both workers join. CTest supplies `XERAX_COMPARISON_EXE` to the independently maintained validator/tests and runs Python normally and with `-O`. Strict compilation is enabled on GNU/Clang and MSVC. Short fault-control passes verify instrumentation behavior only; no latency ranking, decoder result or app release is established by this target.
