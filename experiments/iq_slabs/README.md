# Immutable IQ slabs: synchronous ownership experiment

This is the first **correctness-only**, standalone increment of the [immutable slab proposal](../../docs/research/IQ-HISTORY-NEXT-HYPOTHESIS-2026-09-25.md). It is not linked into XeraX SDR, and it has no performance result. It does not detect protocols, recover voice, decrypt traffic, or implement a retrospective-to-live handoff.

One owner calls `History` methods synchronously. A grant immediately returns a move-only `Lease`; the caller may transfer that lease to another thread using its own synchronization. Only lease release/destruction may run concurrently with the owner. There is no cross-thread request queue, coordinator, request deadline, cancellation handshake, live delivery queue, or worker shutdown/join implementation in this increment.

## Fixed payload and metadata profile

| Quantity | Bound |
| --- | ---: |
| Source slab size | 61,440 bytes |
| Reusable source slabs | 252 |
| Permanently reserved ingress scratch | 4 slabs / 245,760 bytes |
| Total allocated payload | 256 slabs / 15,728,640 bytes / 15 MiB |
| Useful published history after warmup | Exactly 8,388,608 bytes / 8 MiB |
| Physical history references | At most 138 slabs |
| Maximum append | 245,760 bytes, whole complex samples |
| Snapshot | One lease; at most 101 slabs, 6,144,000 requested bytes, and 250 ms at the declared rate |
| Live leases | At most eight leases and **eight physical slab claims in total**, across all epochs |
| Arena/control-block plus process ledger metadata allocation | At most 131,072 bytes per admitted profile |

History references and lease pins may overlap. Admission charges every lease's physical slab claims even when two live leases overlap the same bytes. The worst case remains bounded when the old snapshot, live leases and current history refer to disjoint epochs. Four new producer slabs are available within the reservation proof; ingress never allocates a fallback or waits for a lease to expire.

`ProcessBudget` is an explicit shared process ledger. Pass the **same ledger** to all receiver services and restarts; its payload and metadata limits may reject construction. A service's arena and its allocator token retain the ledger after both `History` and the original `ProcessBudget` facade are destroyed. Payload stays charged until the arena actually frees it, and shared-control metadata stays charged through its deallocation. Pool identifiers increase within that ledger and never intentionally wrap. Independently constructed ledgers are deliberately separate ownership domains and limits; their requests are not interchangeable.

`BudgetStats.metadata_bytes` records actual arena/shared-control allocator-request bytes. `budget_control_bytes` separately records the fixed ledger/shared-control allocation; their sum must fit the configured metadata limit. `State.metadata_bytes` includes the arena and the ledger control allocation. Constructor checks use actual allocator request sizes, and a static ABI-size check protects the profile before construction. Allocator headers/page overhead, caller stack, facade/lease handle objects, external driver buffers and the caller's input buffer are not represented as allocated arena metadata or whole-process RSS. Returned descriptors themselves are fixed arrays inside the arena, not per-request allocations. Platform RSS and those external categories still need separate measurement before any application memory claim.

The initial append path **copies input into the reserved scratch and then into packed source slabs**. This makes input aliasing safe and uses the declared scratch, but it is two ingress copies. It does not yet implement the proposal's desired single-copy ingress adapter and cannot be presented as such in a future comparison.

## Data and lifetime contract

- Samples are opaque CU8, CF32 little-endian, or CF32 big-endian bytes. There is no numeric conversion. Every interval index counts a complete complex sample.
- Short callbacks accumulate into one unpublished filling slab. Only full slabs advance the published frontier. `accepted_end_sample` includes filling input; `end_sample` and retention describe the published interval. Requests cannot access unsealed bytes.
- `seal_tail()` publishes one final short slab and **closes that epoch to further append**. A new epoch is required before more input. This admits the 138-slab closure edge while preventing arbitrary callback fragmentation from defeating the slab budget.
- When enough published input exists, the oldest exposed span is trimmed to preserve exactly 8 MiB. That is a useful-byte limit, not 136 or 137 whole slabs masquerading as the same retention.
- A request must match the current stream, metadata, private reset generation and pool identity, and name an exactly retained interval. There is no nearest-range substitution, missing-sample fill, or implicit epoch join. Pool identities are scoped to the shared ledger.
- `Lease::span()` exposes read-only borrowed views **only through an admitted lease**. It is unavailable on temporary leases. A view must not be retained or read after its lease is moved, reset or destroyed. It is still ordinary C++ borrowed-pointer lifetime discipline, not a language-enforced borrow checker.
- Already granted bytes and their metadata stay immutable through history eviction, retune, gaps and service destruction. Lease pins, not elapsed time, govern reuse.
- A lease owns one preallocated completion state. Reset publishes completion with release ordering; the sole owner observes it with acquire ordering, removes pins and only then reuses the record. A completion cannot be dropped by a full queue. No public arbitrary-handle release API exists, so move ownership prevents duplicate or stale completion injection. New grants use increasing record generations.
- Owner methods automatically reclaim completed leases; explicit `reclaim()` is also available. Stats show owner-acknowledged claims, so a completed-but-unacknowledged lease is still counted until reclamation.
- A lease's final release may destroy/deallocate the whole arena and touch the budget mutex if its service has already gone. That path is safe but **not a real-time guarantee**; deferred destruction on a control thread is future work.

All normal append/grant/reclaim operations use fixed arrays, bounded scans and existing shared ownership. They allocate no heap storage. Arena allocation, budget locking and destruction are control-path operations. This says nothing about OS scheduling, atomic lock freedom on a specific ABI, cache latency, or final-deallocation latency.

## Rejections and generations

Stale public IDs or pool/reset generations return `EpochMismatch` without damaging current history. A request metadata mismatch also leaves history intact. An append with changed same-epoch metadata returns `MetadataMismatch`; noncontiguous/reordered input returns `Discontinuity`. Both append failures purge current history/filling state and require an explicit new epoch; further append/grant/seal calls return `Discontinuity` until then. Before the first epoch they instead return `NoEpoch`. Old leases remain valid historical data.

Zero/incomplete-sample input, arithmetic overflow, oversize input, exhausted counters and unavailable producer storage are checked before accepting an append prefix. Closed epochs reject append. A held snapshot returns `Busy` on another otherwise valid snapshot; live admission separately checks its aggregate eight-slab cap. There is no timeout-based pin revocation.

`CounterLimits` allows deliberately small reset, slab-incarnation and lease-generation maxima in contract tests. Operations fail before the configured maximum would be exceeded. Different counters can exhaust independently; exhausted record/slab identities are never silently wrapped. New source IDs may replace public identities A → B → A, while the internal generation still changes. Reconstructing a service under the same ledger changes the pool identity even if its local generation starts at one.

## Build and correctness checks

The test source is maintained independently from the library implementation. Build only the standalone cache:

```text
cmake -S experiments/iq_slabs -B build/iq-slabs-agent -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build/iq-slabs-agent
ctest --test-dir build/iq-slabs-agent --output-on-failure
```

GNU/Clang builds enable `-Wall -Wextra -Wpedantic -Werror`; MSVC builds use `/W4 /WX`. The tests compare exact source-index-derived bytes, metadata and intervals against an independent retention model, exercise owner/lease lifetime and bounded admission, and observe heap allocations around operational paths. Test results and ABI-specific sizes should be reported from the actual run; neither CMake configuration nor this document is evidence of an Android/MSVC/sanitizer pass.

The 25 September 2026 local Windows x64 GNU 16.1.0 Release build passed **15 independent contract groups, zero failures**, through this standalone CMake/CTest target. One captured run reported 23,042 assertions and 49,909,846 exact oracle/model bytes checked. These two totals vary because the concurrent reader makes a scheduler-dependent number of verification passes; pass/fail is based on correctness and bounded ownership, not an iteration-speed threshold. The suite covers exact 8 MiB/138-slab closure retention, CU8/CF32LE/CF32BE bytes, partial callbacks, stalled old-epoch leases, live physical credits, stale requests, counter exhaustion, service-first destruction, shared-budget admission, cross-thread completion overlapping owner retunes/reclaim, and operational allocation checks.

On that ABI, the tracked arena/shared-control allocation was **48,056 bytes** and the process-ledger/shared-control allocation **96 bytes**, for **48,152 bytes of accounted metadata**. Reported handle/object sizes were `Stream=40`, `Request=72`, `Span=40`, `Lease=120`, and `State=168` bytes; those caller-owned handle/stack objects are separate from the allocated arena metadata as described above. The payload allocation was exactly 15,728,640 bytes. These are allocation/type-size observations, not a throughput, resident-memory, Android, MSVC or sanitizer result.

Before timing, the next increment must add the missing bounded request/coordinator and shutdown contracts, preserve exact accepted work and measure producer copy **plus** maintenance/grant/reclaim work. Async publication, queued-but-unclaimed grants, cancellation/deadline races, external stale-completion injection, and real driver buffers are explicitly unimplemented. No new timing run or production promotion is authorized by this README.
