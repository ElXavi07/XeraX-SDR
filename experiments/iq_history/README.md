# Bounded IQ history experiment

This standalone C++17 prototype stores original CU8 or CF32 **bytes** without
conversion. It is engineering groundwork for the [raw-history hypothesis](../../docs/research/MULTICHANNEL-HYPOTHESES-2026-09-25.md).
It is not connected to the live receiver, APK or EXE defaults, and does not yet
recover voice, synchronize a decoder, or improve RF reception.

There are now two standalone variants. `History` preserves the original owned-
vector API used for the initial timings. `CreditHistory` adds preallocated,
move-only snapshot leases with explicit count/byte credits. It has separate
contract tests and has **not** been benchmarked.

## Build and run

From the repository root:

```powershell
cmake -S experiments/iq_history -B build/iq-history-agent -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build/iq-history-agent
ctest --test-dir build/iq-history-agent --output-on-failure
```

The baseline library/executable targets are `xerax_iq_history` and
`xerax_iq_history_test`. The bounded-credit targets are `xerax_iq_credit_history`
and `xerax_iq_credit_history_test`. Both contract tests run through CTest. No
engine, GUI or shared build configuration is modified.

## Baseline contract

- Construct one `History` per receiver with a positive byte capacity. The ring
  allocates exactly that many payload bytes once. Usable capacity rounds down to
  a whole complex sample. Metadata and object/mutex overhead are additional.
- Call `begin_epoch` with stream ID, epoch, sample rate, center frequency and
  bytes per complex sample: 2 for CU8 or 8 for CF32. This prototype leaves byte
  order and numeric interpretation unchanged; any future capture exporter must
  describe the source's endianness separately.
- The first append may begin at any valid absolute complex-sample index.
  Subsequent appends must be exactly contiguous. Oversized appends retain the
  newest whole-sample suffix and return `Truncated`; they never enlarge storage.
- Snapshot requests specify the full metadata and half-open source interval
  `[first_sample, first_sample + count)`. Success returns that exact interval and
  an owned byte copy. Overwritten, future, stale-epoch and missing intervals are
  errors with an empty payload. Zero-sized requests are rejected explicitly.
- A missing/reordered/overlapping append clears retained history and requires a
  new epoch. The rejected block is not accepted. The caller must explicitly
  advance the epoch and retry data known to belong to the new continuous span.
  The ring never fills missing samples or treats an unknown gap as measured time.
- Retune, rate and format changes require a new epoch. An unannounced metadata
  change on append invalidates history; it cannot combine old and new settings.
  Same-stream epochs must increase monotonically. A different stream ID passed
  to `begin_epoch` explicitly replaces the source. Wrong/stale append identities
  are rejected without deleting the current epoch. A failed snapshot never
  modifies the ring.
- Addition/multiplication overflow and partial samples are rejected before
  copying. Endpoints use `uint64_t`; an interval whose exclusive endpoint cannot
  fit is rejected, even if its first sample index would fit.

## Threading and memory limits

Append, begin/reset, state and snapshot operations are serialized by one mutex;
each completed operation is consistent with one stream/epoch. Append allocates
no payload memory after construction. Snapshot allocates its owned result and
copies while holding the mutex, so a large snapshot **can delay ingestion**.
There is no disk/network I/O under the lock, and no claim of lock-free or hard
real-time behavior. Caller-provided append bytes must remain valid and unchanged
for the duration of the call. The object must outlive all caller threads.

The fixed capacity bounds retained ring bytes. Each snapshot is individually
bounded by that capacity; callers can retain multiple owned snapshots, so a
future live service must additionally limit outstanding snapshot count/bytes.
The prototype intentionally does not pretend that the ring's capacity is a
whole-application memory cap. Old snapshot copies retain their original epoch
and metadata even after the ring resets; consumers must not relabel them live.

## Bounded-credit variant

`CreditHistory` wraps a private baseline ring and an independently owned snapshot
pool. `CreditConfig` specifies ring bytes, bytes per snapshot slot, maximum
simultaneous snapshots and total payload budget. Construction validates
`ring_bytes + slot_bytes * slot_count <= payload_budget` with overflow-safe
arithmetic before allocating payload storage. Every slot is preallocated once.
Descriptor, mutex and allocator overhead is additional to the payload budget;
this is not a whole-process resident-memory limit.

```cpp
using namespace xerax::experiment;
CreditHistory history({8 * 1024 * 1024, 7 * 1024 * 1024, 1, 15 * 1024 * 1024});
Stream stream{73, 1, 3072000, 451100000, 8};
history.begin_epoch(stream);
// Append contiguous CF32 source bytes, then request an exact retained interval:
auto lease = history.snapshot(stream, first_sample, sample_count);
if (lease) {
    // lease.data() / lease.size() are immutable bytes for lease.info()'s epoch.
}
// Reset/destruction releases the slot; moving the lease transfers its ownership.
```

The snippet assumes `first_sample` and `sample_count` describe previously
appended data. It illustrates ownership rather than a complete receiver.

- `Busy` means all snapshot credits are occupied. Capacity checks do not wait
  for another consumer to release a slot and never allocate fallback payload.
  The short pool mutex itself can still block; this is not a nonblocking API.
  `Busy` takes precedence over validating the requested interval while full.
- `OutputTooSmall` means the request exceeds one slot. It returns no data and
  immediately releases its credit. All other interval/epoch/metadata failures
  likewise release credits without publishing partial or stale bytes.
- `SnapshotLease` cannot be copied. Move construction transfers one credit;
  move assignment first releases the destination's old credit. `reset()` is
  idempotent, and exception unwinding also returns the credit.
- A lease holds shared ownership of the pool, without pointers or release
  callbacks into `CreditHistory`. It remains readable after its service is
  destroyed; the pool is freed after its last owner is gone. Do not destroy a
  service while other threads are calling service methods. Leases are separate
  objects; concurrently moving/resetting the same lease is not supported.
- A retune or gap changes the ring, never the contents/identity of an outstanding
  historical lease. Callers must honor its original metadata. The returned
  const data pointer becomes invalid when its lease is reset, moved or destroyed.
- `credit_stats()` reports preallocated payload, outstanding count and reserved
  bytes. Each outstanding lease reserves its full slot size even when its result
  is shorter. The cap applies per service/pool; applications creating multiple
  services must also budget their aggregate storage and surviving old pools.

The baseline gained the additive `snapshot_into()` method, which copies to
caller-provided storage without allocating and leaves it untouched on error.
`CreditHistory` uses it to avoid a temporary owned-vector allocation. The original
`snapshot()` API is unchanged, so the bounded-credit variant is optional.
Whole-snapshot copying still holds the ring mutex. No producer-latency reduction
has been measured or claimed.

## Verification and timing

Tests cover both formats, 7,000 append/model comparisons with wraparound and
oversized blocks, exact subranges, arithmetic bounds, missing/reordered input,
retune/rate/format changes, stale epochs, independent receivers, owned-copy
isolation and concurrent append/snapshot across an epoch transition.

The additional credit tests cover budget validation/overflow, exhaustion,
release and address reuse, move construction/assignment/self-move, exception
cleanup, destruction of a service with a surviving lease, failed-request credit
return, 1,600 exact-copy parity steps against the original API, and concurrent
held snapshots across 99 producer retunes. Local GNU C++17 builds treat warnings
as errors. Source was checked for portable types/includes; local MSVC is not
available, so MSVC `/W4 /WX` validation belongs to CI.

Optional timing mode:

```powershell
build/iq-history-agent/xerax_iq_history_test.exe --benchmark
```

This prints two JSON lines for isolated CU8/CF32 ring copies using 10 ms input
blocks at 3.072 MS/s and 250 ms snapshots. It includes mutex/copy and snapshot
allocation costs. It does not include drivers, DSP, vocoder, audio playback,
competing receivers or phone thermals, and is not a whole-radio speed result.
Run repeated isolated trials without other build/test workloads before using
the numbers for a decision; the mode itself supplies no acceptance verdict.

Before live integration, add backend sample provenance, explicit retune/drop
events, an outstanding-snapshot budget, measured maximum producer blocking and
independent decoder state for replay. A spare-budget replay scheduler and a
duplicate-free replay/live handoff are separate work. Missing or out-of-band
RF data cannot be recovered by this storage layer.

## Initial measurements — 2026-09-25

These measurements describe the original `History` owned-vector prototype,
before the bounded-credit variant was added. They are not timings of
`CreditHistory`, its leases or the additive caller-buffer API.

Five sequential isolated trials ran on Windows 10 Home 19045, Intel Core
i5-1038NG7 (4 cores / 8 logical processors), using MinGW GNU C++ 16.1.0,
`-O3 -DNDEBUG`. Engine builds were deferred during the timing window. Every
trial ran CU8 then CF32 with a 16 MiB ring, 50 append warmups, 2,000 measured
appends and 100 measured snapshots. The executable SHA-256 was
`26365333c4a05d50e078ef235b608e27f0d9da7bac53caa79e77e8b37c7a698d`.

| Operation at 3.072 MS/s | Median of five batch means | Range of batch means |
| --- | ---: | ---: |
| Append 10 ms CU8, 61,440 bytes | 4.882 microseconds | 4.541–5.561 microseconds |
| Append 10 ms CF32, 245,760 bytes | 20.089 microseconds | 18.565–25.609 microseconds |
| Copy 250 ms CU8 snapshot, 1,536,000 bytes | 0.593 milliseconds | 0.527–0.675 milliseconds |
| Copy 250 ms CF32 snapshot, 6,144,000 bytes | 2.505 milliseconds | 2.161–2.705 milliseconds |

These are elapsed batch totals divided by operation count, **not** individual
operation latency distributions, p95 values, maximum lock times or producer
blocking bounds. Snapshot batches include allocation, copying, checksum
accounting and destruction of each owned result. Appends and snapshots ran
sequentially, not concurrently, and input bytes were reused. Fixed format order
and warm/cache effects limit cross-format comparisons. No Android, RTL hardware,
radio decoding, thermal-load or audio improvement is established.

Raw trial outputs and the calculated summary are local build evidence:
`build/iq-history-agent/timing-20260925.jsonl` and
`build/iq-history-agent/timing-summary-20260925.json`. The measured averages make
a bounded-copy service worth testing, but do not justify placing the current
whole-snapshot critical section on a live producer path.

## Next concrete experiment: short copies after bounded credits

The first variant below is now implemented and contract-tested separately,
without new timing claims. The second remains a proposal. Keep the mutex-based
design and compare them in future controlled load tests:

1. The implemented `CreditHistory` preallocates a small snapshot pool with explicit
   byte/count credits. A request with no free slot returns `Busy`; it does not
   allocate payload or wait for free credits. It returns a move-only lease whose destruction releases the credit,
   including cancellation/error paths. The lease must own a safe reference to
   pool state so that destroying the service first cannot create a dangling
   release callback. Ring and pool payload are included in its configured
   budget; live integration must also budget descriptors/allocator overhead.
   A ring cap alone does not bound snapshot memory.
2. Copy a leased snapshot in 64 KiB chunks, then compare 256 KiB chunks. Between
   chunks release the ring mutex. Revalidate the original metadata/epoch and
   interval on each chunk; if it expires or changes, discard the entire result
   and release its lease. Never publish partially copied data. Snapshot work
   should use `try_lock` and a deadline, abandoning a request under contention
   instead of repeatedly blocking live ingestion.

The first variant isolates allocator cost; the second bounds work inside a
snapshot critical section. It does **not** prove a wall-clock latency bound:
ordinary mutexes do not promise fairness, and Windows/Android scheduling can
preempt a thread while it holds a lock. Oversized append operations also need
bounded chunking at the future source-service boundary; the current primitive
deliberately permits a copy as large as the ring.

For a first 3.072 MS/s phone budget experiment, an 8 MiB ring and one 7 MiB
preallocated snapshot slot fit the 250 ms CF32 request while using 15 MiB of
payload storage; leave room for measured object/allocator overhead. This is a
proposal, not a measured phone configuration. Multiple callers holding leases
must cause `Busy`, never additional allocations.

Drive a paced producer with 10 ms blocks for 60 seconds while requesting
snapshots at 1/4/10 Hz and retaining each lease for 0/100/500 ms. Measure each
append's latency and missed producer deadlines, snapshot completion/expiration,
lease count/bytes, and p50/p95/p99/max under this deliberate concurrent load.
Include retunes and overwrite races halfway through a copy, abandoned requests,
consumer exceptions and service destruction with outstanding leases. The
release gate is exact bytes/epoch, no leaked credits or unbounded memory, no
new producer drops, and a repeatable reduction in producer tail delay relative
to the current whole-copy mutex implementation. Do not replace it with a more
complex lock-free structure until this simpler experiment identifies a need.
