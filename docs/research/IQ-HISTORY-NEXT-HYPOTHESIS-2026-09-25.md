# Next IQ-history hypothesis: bounded immutable slab ownership

**25 September 2026 — research proposal only.** This document proposes a standalone experiment after reviewing the current history implementation and paced latency screen. It contains no implementation, new benchmark run, live-engine integration or decoding-speed result.

## Observed evidence

The current [`History`](../../experiments/iq_history/iq_history.cpp) writes and copies retained bytes under one history mutex. `snapshot_into` holds it for the complete copy; `snapshot_chunked_into` takes it separately for each chunk and rejects the request if any acquisition fails. The latter also checks cancellation, deadlines, the original complete interval and an internal reset generation. [`CreditHistory`](../../experiments/iq_history/credit_history.cpp) preallocates snapshot storage and caps outstanding leases, but successful snapshots still copy their entire payload. These observations follow directly from the inspected code.

The completed local report `build/iq-latency-screen-cf32/report.json` records three 30-second rounds per variant, 3.072 MS/s CF32, 10 ms appends, 250 ms snapshots at 10 requests/s, and zero additional lease hold time. Its SHA-256 when read for this document was `044a4348ac2cb59e41949ce363fa11b59efe8c48be30222c623e2183fac74248`.

| Variant | Median of the three append p99 values | Completed snapshots |
| --- | ---: | ---: |
| No snapshots | 108.9 microseconds | Not requested |
| Frozen whole-copy baseline | 728.0 microseconds | 900/900 |
| Updated whole-copy credits | 749.5 microseconds | 900/900 |
| 64 KiB try-lock chunks | 988.8 microseconds | 280/900 |
| 256 KiB try-lock chunks | 1,038.1 microseconds | 443/900 |

Both chunk sizes lost to the frozen baseline in all three paired append-p99 comparisons. The report records no append call exceeding 10 ms in any variant. Scheduled-deadline misses occurred even without snapshots; these are host scheduling measurements, not measured RF sample losses. Accepted snapshots were byte-checked by the harness. This document reads that recorded evidence; it does not repeat the runs or independently reconstruct all raw traces. Workload details and limits belong to the [latency experiment](IQ-HISTORY-LATENCY-2026-09-25.md).

**Inference:** splitting one copy into many opportunistic lock acquisitions did not achieve the declared screening goal on this workload. The result does not prove that every chunk size, scheduler or platform will fail. It does justify testing whether removing the reader's payload copy from writer synchronization is more useful than subdividing it. Reader verification, cache traffic, owner bookkeeping and scheduling can still defeat that new hypothesis.

## Falsifiable hypothesis

At the same useful history duration, request rate and completed work, preallocated immutable source slabs with explicitly bounded snapshot/live ownership will reduce producer tail delay relative to the frozen whole-copy path. A snapshot will acquire a bounded list of retained spans instead of copying megabytes while excluding the producer. The test must include request-to-grant delay and complete byte verification; measuring only the time to enqueue a request would be misleading.

The first candidate should have one source owner, one snapshot coordinator and one live consumer. General multi-consumer publication, GPU storage and direct driver-buffer retention are deferred. The predicted benefit is reduced snapshot-induced producer contention, **not** faster synchronization, clearer voice, stronger decryption or recovery of samples never captured.

## Primary-source basis and its limits

- **Explicit acquired-buffer lifetime is an established SDR interface pattern.** SoapySDR exposes direct receive-buffer acquisition, an associated handle and explicit release. Its direct-buffer count bounds acquisitions before release; zero means the driver does not support that interface. This supports using an explicit ownership contract, but does not establish that RTL-SDR, HackRF or every installed driver can donate buffers to XeraX history. Holding a driver's finite buffers for a stalled snapshot may prevent further input. The first experiment should copy ingress once into its own bounded arena and promptly release any driver-owned buffer. [SoapySDR Device API](https://pothosware.github.io/SoapySDR/doxygen/latest/classSoapySDR_1_1Device.html)
- **Reader lifetime must govern reuse.** GNU Radio's buffer interface describes one writer and multiple readers, available write space and absolute item counts. Its implementation also explicitly protects buffer/reader indices with a mutex. The useful precedent is source-position and reader bookkeeping, not a claim that GNU Radio's entire buffer path is lock-free. [GNU Radio buffer source](https://github.com/gnuradio/gnuradio/blob/main/gnuradio-runtime/include/gnuradio/buffer.h)
- **Publication and reclamation are different operations.** The Linux RCU explanation separates removing an object from discoverable state from reclaiming it after existing readers finish. The proposed slabs follow that lifetime principle without importing Linux RCU into Windows/Android. Waiting for a grace period on the producer or allocating replacement slabs indefinitely would violate this proposal's goals. [Linux RCU documentation](https://docs.kernel.org/RCU/whatisRCU.html)
- **A queue's guarantee has strict preconditions.** Boost's documented SPSC queue permits one pushing thread and one popping thread. If used, publish fixed, trivial descriptors with preallocated capacity; multiple UI workers must first pass through the single coordinator. Its queue-operation guarantee does not establish a bound on the surrounding service, copied payloads or scheduling. The cited version is the successfully inspected 1.73 reference, not a claim about the newest release. [Boost SPSC contract](https://www.boost.org/doc/libs/1_73_0/doc/html/boost/lockfree/spsc_queue.html)
- **Lifetime safety is not a wait-free guarantee.** Even `atomic<shared_ptr<T>>` has an implementation-defined lock-free property; associated destruction/deallocation occurs after the atomic update. Ordinary shared ownership in the C++17 prototype cannot justify stronger latency claims. Keep per-slab allocation, shared-pointer refcount churn and final arena destruction off the measured producer path. [C++ atomic shared-pointer specification](https://eel.is/c++draft/util.smartptr.atomic)
- **Visibility and progress need separate evidence.** Publishing initialized bytes with release semantics and observing that publication with acquire semantics supplies a synchronization edge. It does not prevent preemption. Integer atomic lock-free properties depend on the implementation; verify the actual types on Windows x64, Android arm64 and any supported armeabi-v7a target. Do not assume a 64-bit generation requires a lock-free 64-bit atomic: immutable descriptor fields can be transferred behind a checked publication state. [C++ memory ordering](https://eel.is/c++draft/atomics.order), [atomic lock-free properties](https://eel.is/c++draft/atomics.lockfree)

## Proposed ownership and publication contract

Allocate one arena before streaming. Its fixed payload unit is a **61,440-byte slab**, divisible by both supported complex-sample widths. One owner alone mutates the free list, retained-history index, generations and pin accounting. Consumers never obtain raw pointers by inspecting an unpinned mutable history table.

The producer copies each incoming bounded block into exclusively owned free slabs, then seals them. Sealed payload and source metadata remain immutable until every ownership claim is gone. Publication carries the pool identity, internal reset generation, public stream/epoch, source interval, rate, frequency, format/endianness, valid byte count and slab incarnation. Retained history, live delivery and snapshots may refer to the same sealed slab; that overlap saves storage but is not required for the worst-case budget proof.

Use the following lifecycle as an implementation requirement, not implemented pseudocode:

1. **Free → filling:** only the owner may remove a slab from a fixed free list and write it. Input blocks larger than the declared 10 ms maximum need a separately specified bounded adapter; never silently enlarge the scratch buffer or monopolize the owner with arbitrary input size.
2. **Filling → sealed:** finish payload and immutable metadata, install history ownership and publish the initialized descriptor. Never expose partially filled bytes. In a continuous epoch, pack complete slabs rather than sealing every short driver callback; otherwise small fragments would invalidate the descriptor-count budget. A final short slab may be sealed explicitly at an epoch boundary.
3. **Snapshot request → grant:** the coordinator submits an exact half-open source interval and reset generation through one preallocated request slot. One credit covers pending, granted-but-unclaimed and held states. The owner processes at most one request per input block boundary, verifies continuous coverage and metadata, pins the entire list, and only then publishes a successful result. A request must end at or before the published frontier; it must not substitute an older interval for unavailable newest samples. The owner is the linearization point, so there is no reader-side search/retry against a moving ring.
4. **Lease:** a move-only result exposes a bounded array of read-only spans with exact first/last offsets, at most 101 slabs for this profile. The consumer verifies or decodes them in source order without making an unbudgeted contiguous vector. The source slab may be evicted from the history index while the immutable lease still protects it. Dropping a history reference alone never permits reuse.
5. **Release → reclaim:** the final consumer action publishes completion for that particular lease generation. The owner acknowledges it and removes its pins before permitting credit or slab reuse. Completion cannot be dropped because a generic return queue is full; reserve a completion state per admitted lease. A deadline/cancellation flag only requests release; it cannot revoke a pointer that a consumer might still use.

A bounded scan of up to 138 history descriptors, including the partial closure edge discussed below, and pinning/releasing up to 101 snapshot slabs replaces the large synchronized snapshot copy. Those operations are additional producer work and must be timed. Fixed free-list operations can remain owner-only; an implementation that substitutes a mutex-protected allocator, free list or metadata registry must expose and measure that contention. **Neither this design description nor preallocation proves nonblocking ingress or a wall-clock bound.**

The request state must prevent a cancelled generation from modifying a reused request slot. Release/acquire publication must protect payload, descriptor initialization and completion acknowledgement in both directions. Avoid callbacks, arbitrary deleters, logging, allocation and device I/O while granting or reclaiming leases. A fixed amount of work is a useful design property; OS pauses, memory faults and cache contention still affect elapsed time.

## Byte budget and useful retention at 3.072 MS/s

These values are arithmetic, not measurements. `MiB = 1,048,576 bytes`; indices count complex I/Q samples, not scalar components.

| Quantity | CU8: 2 bytes/complex sample | CF32: 8 bytes/complex sample |
| --- | ---: | ---: |
| Payload rate | 6,144,000 bytes/s | 24,576,000 bytes/s |
| 10 ms input block, 30,720 samples | 61,440 bytes | 245,760 bytes |
| One 61,440-byte slab | 30,720 samples; 10 ms | 7,680 samples; 2.5 ms |
| Exact 250 ms request, 768,000 samples | 1,536,000 bytes | 6,144,000 bytes |
| Maximum slabs pinned by an unaligned 250 ms request | 26; 1,597,440 bytes | 101; 6,205,440 bytes |
| Exact 8 MiB useful history | 4,194,304 samples; 1,365.333 ms | 1,048,576 samples; 341.333 ms |

The first/last partial spans explain why physical pinned bytes can exceed the requested payload. The count assumes a continuously packed epoch, not arbitrarily fragmented callback storage. Requests exceeding the 250 ms/count cap must be rejected explicitly or use a separately budgeted profile. At another source rate, the same byte/slab caps imply different retention and maximum snapshot durations; recompute them before accepting the configuration. A rate change must not silently enlarge the 101-slab snapshot or 245,760-byte ingress limit.

**Match the existing useful history in paired tests.** Merely keeping 136 complete slabs retains 8,355,840 bytes, which is 32,768 bytes below the existing 8 MiB ring: only 1,360 ms CU8 or 340 ms CF32. For the slab-aligned frontier in the paced workload, reserve 137 physical history slabs and trim the first exposed span so that useful retained history is exactly 8,388,608 bytes after warmup. Their physical capacity is 8,417,280 bytes; the extra 28,672 bytes is counted, not treated as free memory. If an implementation instead uses the shorter 136-slab history, both paired variants must match that sample duration or prominently disclose the difference.

There is an additional closure edge: sealing a short final slab makes the frontier unaligned. An arbitrary 8 MiB interval can then intersect **138** slabs, because its length is not a whole slab multiple. Reserve one additional slab for that case, raising worst-case physical history to 8,478,720 bytes, or explicitly exclude such grants. The budget below includes it. Frequent short callback sealing is still forbidden; one closure-edge reservation cannot cover arbitrary fragmentation.

| Reservation within one service | Slabs | Maximum payload bytes |
| --- | ---: | ---: |
| Current retained history at an aligned frontier, including head trimming | 137 | 8,417,280 |
| Additional partial closure-edge history slab | 1 | 61,440 |
| One outstanding snapshot, including an arbitrarily stalled old-epoch lease | 101 | 6,205,440 |
| Live-consumer pins/queued deliveries, separately capped across all epochs | 8 | 491,520 |
| Exclusive producer write reservation | 4 | 245,760 |
| Ingress staging scratch, never available for consumer pinning | 4 | 245,760 |
| Uncommitted reserve | 1 | 61,440 |
| **Total preallocated service payload** | **256** | **15,728,640 = 15 MiB** |

This is a conservative sum of potentially disjoint reservations. At steady state history and consumer views often share slabs; that overlap must not be required to satisfy the cap. One arena may contain 252 reusable slabs plus four permanent scratch slabs. Snapshot/live admission limits are charged by the complete physical slabs retained, not just by requested subranges. Live delivery must cap both count and total pin bytes; two CF32 input blocks exhaust its eight-slab reservation. A new epoch does not create new snapshot or live credits.

The old latency profile counts 15 MiB of ring/snapshot payload **excluding** the producer input vector. Its total including that input vector is 15,974,400 bytes for CF32 and 15,790,080 bytes for CU8. This proposal's 15 MiB includes one maximum-size ingress scratch area. Report both useful history and every memory category when comparing variants rather than presenting those unlike totals as identical.

All descriptor arrays, indices, request/result mailboxes and ownership state must also be fixed-capacity and accounted. Start with a separate **128 KiB maximum metadata allocation contract**, to be checked using actual types, padding, alignment and allocator requests on each ABI before accepting that profile. No post-start container growth is allowed. Allocator/page overhead and resident memory must be measured separately; 15 MiB is a source-payload cap, not a whole-process RAM claim. Driver/DMA buffers, DSP workspaces and output audio are distinct measured budgets. Any additional app-owned copy of these live/history/snapshot source bytes, including contiguous materialization, must be charged to this ledger or an explicitly larger declared profile.

Retired arenas still count. A lease that keeps an old service arena alive cannot permit an unaccounted replacement arena on restart. A process-level budget token must remain charged until that arena is actually reclaimed; admission of another arena may fail. Retunes within the service should reuse the existing arena with new generations, preserving the byte cap even while old leases survive.

## Retunes, gaps, reader stalls and shutdown

| Situation | Required behavior |
| --- | --- |
| Retune, rate/format change or source replacement | Begin a new internal reset generation and public epoch; clear current history ownership; retain old leased payload unchanged and labelled with its old metadata. Reuse fixed-size slabs without allocating another format-sized pool. Pending requests for the earlier generation fail if not already granted. |
| Public identity changes A → B → A | The private generation still changes. Matching public IDs must not make an old request or completion valid again. |
| Noncontiguous, overlapping or reordered input | Reject the offending append, mark the continuity break and require an explicit new epoch as the existing contract does. Do not zero-fill, relabel, join separate spans or infer the gap duration. Already granted pre-gap leases remain immutable historical data. |
| Snapshot consumer never returns | Keep its at-most-101 slabs protected indefinitely; further snapshots return busy. History ingestion can continue within the remaining explicit reservations. Never reclaim after a timeout while its pointer remains usable. |
| Live consumer stalls | Preserve its bounded pins. Reject additional live deliveries and report the skipped source intervals; the source/history path may continue. Finite storage cannot guarantee lossless output to an indefinitely stalled consumer. These delivery drops differ from RF/driver drops. |
| Cancellation before grant | Owner acknowledges cancellation and returns the request credit without publishing spans. |
| Cancellation racing with/after grant | Consumer must observe the grant and release it, or complete a specified cancellation handshake. An abandoned granted result continues to consume its bounded credit; it cannot become a dangling pointer. |
| Service facade destroyed with held leases | Close admission and stop/join the owner on a control thread. The arena/control state must outlive all leases, and their releases must never call a destroyed service. Destruction/deallocation of the last arena belongs off the producer path. |
| Unexpected free-list exhaustion despite correct admission | Report a broken invariant or explicit bounded failure, never allocate fallback slabs or spin waiting for a reader. Distinguish this from deliberate rejection of requests beyond the profile. |

A single lifetime reference to the preallocated arena may be useful for safe facade destruction. It must not be confused with using per-slab `shared_ptr` operations as a latency guarantee. The final-deallocation path and any global-budget bookkeeping still need inspection and measurement.

## Correctness, ABA and lease tests required before timing

All expected bytes must come from independent deterministic source-index/epoch patterns, not from the candidate's snapshot implementation. Compare the exact concatenated requested interval, every metadata field and every reported failure against a simple sequential model.

1. **Publication interleavings:** pause at free-list acquisition, after payload fill, before publication, during grant, before reply consumption and before completion acknowledgement. A consumer must see a complete immutable result or a specific failure, never a partly updated descriptor.
2. **Slab ABA:** delay a handle for slot `i`, retire/recycle that slot repeatedly, then inject the stale handle/completion. Check `(pool identity, reset generation, slot, slab incarnation, lease generation)` before allowing any ownership change. An old completion must never decrement a new lease's pin. Never use a recycled address or slot number as identity by itself.
3. **Counter exhaustion:** use deliberately tiny test counters to reach wrap quickly, plus real-type maximum-value cases. Fail before wrap; do not accept the same generation again. Cover both public A → B → A and private pool reconstruction at a reused address.
4. **Exact lease ownership:** move construction/assignment, moved-from destruction, self-move handling, exception exits, repeated reset and duplicate release messages must release exactly the intended claim once. Test partial grant rollback and cancellation before/after publication. No request slot is reused before acknowledgement proves its previous generation is finished.
5. **Retune/gap races:** inject frequency/rate/format changes and discontinuities at each grant boundary. A successful old result remains wholly old; an unsuccessful result has no usable spans. Hold an old-format lease while filling a complete new-format history at the cap.
6. **Persistent stalls:** retain one maximum snapshot and all live credits while driving many history turnovers. Assert fixed payload/allocation totals, immutable held bytes, continued in-profile ingestion and counted refusal of new work. Stall before taking a granted result as well as after reading it. Never use lease expiry to force reclamation.
7. **Retention boundaries:** test exact 8 MiB useful history, head trimming, unaligned 250 ms requests, earliest/latest retained sample, future endpoints, format widths, one sample too large, incomplete samples and all size/index overflow paths. Reject requests whose span count exceeds the configured bound.
8. **Lifetime and budget:** destroy the facade first, then verify held bytes, release from another thread and attempt a new service under the still-charged global budget. Confirm deferred destruction, no dangling callback, no leaked credit and no second unbudgeted arena. Exercise an unavailable completion mailbox and prove release cannot be silently lost.
9. **Architecture checks:** compile/run contract tests on Windows x64 and Android arm64, and armeabi-v7a if it remains supported. Verify atomic properties and alignment actually used. Run available address/undefined/thread sanitizers in a suitable separate test build; absence of a sanitizer report is not a proof of correctness or progress.

## Failure and promotion gates

**Stop immediately on any correctness or budget failure.** Mixed epochs, stale successful handles, changed leased bytes, unaccounted allocation, incorrect interval coverage, an in-profile append rejection, forced reclamation of a held lease, leaked credits or post-shutdown use-after-free disqualify the candidate regardless of timing. A prototype that holds a writer-shared mutex while verifying/decoding/copying the snapshot has not implemented the central hypothesis.

After the deterministic tests pass, preregister a paired screen against the preserved whole-copy executable and a no-snapshot control. Match useful history, input patterns, request intervals, accepted work and actual consumer byte verification. Preserve source/binary hashes and raw traces; rotate run order. Reuse the current CF32 three-round screen first, with the same 50 ms snapshot deadline, counting that deadline from request submission through grant, not just owner execution. This is a proposed future run, not permission to reinterpret the existing results.

To earn a longer experiment, require all of the following:

- At least 95% of baseline completed requests at the same request/hold settings, with exact bytes and no in-profile append rejection. Rejections, pending requests and queued-but-never-granted requests are reported separately. The hold clock and byte-verification workload must match the comparator.
- At least 25% lower median of per-run producer append p99 values and a lower p99 in at least two of three paired rounds. Use the contemporaneous paired baseline, not the historical 728 microseconds as a fixed target.
- No increase in append calls exceeding the 10 ms input-block interval; separately report wake lateness and completion after scheduled deadlines. Measure copy, owner maintenance and grant/reclamation work together on the producer, so moving work out of the `append` timer cannot manufacture a win.
- Record request-to-grant p50/p95/p99/max, grant-to-verified completion, end-to-end verified completion, busy/expired/not-retained counts, producer copy bytes, consumer-read bytes, CPU time, queue/pin high-water marks and payload/metadata/retired-arena allocation peaks. All accepted requests must satisfy the declared deadline semantics. Faster descriptor publication alone is insufficient.

Passing that screen permits longer isolated runs covering CU8/CF32, 1/4/10 Hz requests, 0/100/500 ms holds, deliberate indefinitely stalled consumers, delayed owner/coordinator scheduling, retunes and gaps. It does not enable the feature in the APK/EXE. Repeat on the actual phone and desktop architectures with thermal/power and scheduling context recorded. Live promotion additionally requires real input-drop instrumentation, exact source provenance, bounded decoder integration and a duplicate-free retrospective-to-live handoff with protocol/frame/PCM regression checks. Scatter/gather ingestion must preserve decoder state across slab boundaries; adding a hidden contiguous payload copy is a new budget and performance experiment.

If completion and producer-tail gates fail again, reject this ownership implementation as a latency improvement for the tested profile. Keep the simplest correct bounded path while investigating measured causes such as verification/cache pressure or owner scheduling. A useful negative experiment is preferable to claiming that changing ownership automatically made the receiver faster.
