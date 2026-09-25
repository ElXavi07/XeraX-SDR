# Shared coordinator retirement budget — 25 September 2026

Status: local correctness and Android compile checks pass; remote checks pending.
This extends the
[coordinator checkpoint](IQ-COORDINATOR-CONTRACT-2026-09-25.md); it is not linked
to the released receiver and makes no decoding-speed claim.

## Hypothesis and frozen starting point

Requiring one shared reservation ledger for related mailboxes can bound their
aggregate control allocations across repeated restarts, including allocations
kept alive solely by old weak request identities. Admission must fail before
exceeding the declared cap, and capacity must return only after the allocator
actually frees the old storage. Caller-held source bytes and stale-ticket
rejection must retain their existing behavior.

Reject this candidate for premature refund, a reservation race, leaked charge,
unaccounted ledger/control allocation, stale successful identity, failed
constructor without rollback, or a release that touches a destroyed facade.
Holding a ticket indefinitely may legitimately prevent another construction;
the system must report bounded refusal rather than evict the identity unsafely.

The starting commit is `41d978e38545a62f26a221d9e818604cdf87cc7a`. Its sources
are frozen locally in `build/iq-retirement-baseline-41d978e.zip`, SHA-256
`4904f9c6c6b7e197d3d807c86492e3eec4a3d11a5a7838288f8542d72a0b14ce`.
Earlier archives, sample storage, released defaults and user settings stay
unchanged. There is no active timing experiment to resume.

## Design basis and scope

`allocate_shared` uses a rebound allocator whose requested type may include
bookkeeping beyond the object itself. The standard recommends at most one
allocation; the experiment must measure the actual request and explicitly
reject unsupported allocation patterns rather than assume object size equals
allocated size. Constructor exceptions also need reservation rollback. These
requirements follow from the [shared creation specification](https://eel.is/c++draft/util.smartptr.shared.create)
and [allocator requirements](https://eel.is/c++draft/allocator.requirements).

[Weak ownership](https://eel.is/c++draft/util.smartptr.weak) is useful for
identity without retaining a live receiver object. In this implementation it
can retain the shared allocation after that object's lifetime ends. Accounting
therefore follows allocator deallocation, not merely the object's destructor.
The allocator's ledger ownership must survive the original budget facade.

The proposed aggregate cap includes the ledger's own allocator request,
control allocator requests, and a conservative fixed mailbox/one-reply
reservation per admitted control. Current/high-water values describe
**reservations**, including construction in progress. They are not whole-process
RSS or actual operating-system allocation peaks. Arbitrarily retained caller
handle objects, thread stacks, allocator headers/pages and the separate slab
payload budget remain distinct categories. Independent explicitly created
ledgers impose independent caps; there is no implicit process-wide singleton.

Budget admission/refund uses a control-path mutex. Streaming handoff methods
must not add a ledger lock or allocation. Final release of a retired domain
can deallocate and lock the ledger, so it is still not a real-time guarantee.
No timing promotion follows merely from passing these ownership checks.

## Independent verification plan

Keep the previous 15 handoff groups and add exact-boundary admission, repeated
restarts with weak-only identities, concurrent constructors, stalled frees,
budget/facade-first destruction, valid held replies, old-ticket rejection and
injected allocation failure with rollback. Observe reservations before the
physical delete returns to detect refunds that happen too early. Allocation
fault injection/probes are separate from TSan's own operators; every omitted
allocation assertion must be reported rather than counted as a successful check.

A separate abstract resource model explores admission, construction failure,
strong/weak ownership, object retirement and actual deallocation boundaries.
It uses integer units, not ABI byte sizes. The two-attempt/one-domain-cap model
visits 65 states and 172 transitions; the three-attempt/two-domain-cap model
visits 1,356 states and 6,845 transitions. Neither exceeds its cap. Deliberately
split admission, early retirement refund and ledger destruction each yield a
counterexample. Three model test groups pass in normal and optimized Python.
This checks the declared resource lifecycle, not C++ weak-memory behavior,
allocator conformance, executable parity or scheduling fairness.

Windows/Linux contracts, address/undefined checks, working ThreadSanitizer
instrumentation and Android cross-compilation will be recorded from actual
results. Physical phone/RF execution remains pending. Real publication/selection
timestamps and complete producer-work accounting are still required before a
matched latency screen.

## Local results and cost

Strict Windows GNU C++ 16.1 Release CTest passes all 22 groups, with 5,434
assertions and 14,801,814 exact oracle bytes. The preserved 15 handoff groups
still contribute exactly 5,063 assertions and 14,777,814 bytes. The seven new
groups add 371 assertions and 24,000 bytes, plus independent allocation and
lifetime observations. No implementation defect was observed in these cases;
absence of a failing test is not proof of general correctness.

Independent allocation hooks measure 104 bytes for the shared ledger and
392 bytes per control allocation on this ABI. The fixed mailbox/reply category
is 336 bytes, yielding a 728-byte per-domain reservation and an exact 832-byte
one-domain aggregate cap. The preceding per-instance prototype reserved 704
bytes without an aggregate ledger. The new mechanism costs 24 more bytes per
domain plus a shared 104-byte ledger on this ABI; it establishes bounded
retirement admission, not a general reduction in memory use.

Checks exercise a three-retired-domain cap, alias retention until the last weak
ticket, replacement admission after release, two-of-three concurrent constructor
admission, held successful replies alongside retired weak identities, all
facades gone before release, and a deliberately paused physical delete. Targeted
allocation failures restore current charges while preserving the reservation
high-water mark. One byte below the exact cap rejects the allocation before
physical overcommit. Allocation/runtime overhead outside the declared categories
is not represented by those reservation totals.

Both Android library/test-executable targets compile with NDK 28.2.13676358,
API 29 and static libc++. ELF inspection confirms AArch64 and 32-bit ARM;
neither binary has executed on a phone. Six abstract model test groups pass in
both normal and optimized Python. Local logs are `build/iq-retirement-*.log`
and `build/iq-retirement-model.json`; the standalone cache is
`build/iq-retirement-root` with separate caches for each Android ABI.

TSan cannot coexist with the independent replacement allocation operators.
Its build therefore reports unavailable allocator-calibration, delete-pause and
allocation-fault sections separately from omitted operational allocation
assertions. Remaining ownership, ledger and byte checks stay enabled. Ordinary
and address/undefined builds provide the omitted allocation evidence.
