# Bounded snapshot coordinator experiment — 25 September 2026

Status: local and remote correctness/sanitizer checks pass for this bounded scope.
This is a standalone continuation of
the [immutable storage contracts](IQ-OWNERSHIP-CONTRACT-2026-09-25.md), with no
new APK/EXE integration or comparative speed result.

## Falsifiable hypothesis and baseline

A single owner and a single coordinator can transfer one exact immutable
snapshot through a fixed-capacity mailbox, retaining its credit through pending,
unclaimed and held states, while preserving source bytes, cancellation and
shutdown semantics without making the sample owner wait for a reader.

This is a correctness and ownership hypothesis. It does not assert a bounded
wall-clock completion time, wait-free execution, reduced RF drops or improved
digital-radio decoding. A stalled participant may indefinitely delay mailbox
reuse. Safe retained samples are preferable to reclaiming a pointer still in use.

The starting code is `7cf69916832945d1e0878cc63c499d4236e23a92`. Its slab core
and observation sources are frozen locally in
`build/iq-coordinator-baseline-7cf6991.zip`, SHA-256
`592656cef152a52a6951a09b377468f4576d1111ad58698b12f1612d72512ff9`.
The earlier 25-trial copy screen and its negative result remain unchanged.

## Evidence informing the design

C++ release/acquire synchronization can make initialized request/reply data
visible across threads when the acquire observes the matching release. It does
not make unrelated non-atomic accesses safe or establish a scheduling deadline.
The experiment must protect both descriptor publication and slot reuse, not
merely mark a ready flag atomic. This is an application of the
[C++ ordering rules](https://eel.is/c++draft/atomics.order) and
[data-race rules](https://eel.is/c++draft/intro.races), not a claim that those
rules prove this implementation correct.

The distinction between removing an object from discovery and reclaiming it
after readers finish is also explicit in the Linux kernel's
[RCU explanation](https://www.kernel.org/doc/html/latest/RCU/whatisRCU.html).
Here, a small explicit lease and acknowledgement protocol is proposed; this is
not an implementation of Linux RCU and imports none of its progress guarantees.

Supplied monotonic logical ticks permit repeatable deadline boundary tests.
They are not observations of physical publication time. The
[C++ timing requirements](https://eel.is/c++draft/thread.req.timing) describe
implementation/resource delays; a preempted thread can exceed a desired
deadline even when its last check was timely. Future speed tests still need
actual publication, selection, wake and complete producer-work observations.

## Required rejection and promotion gates

Reject this candidate on any changed leased byte, mixed provenance, duplicate
ownership, slot reuse before acknowledgement, leaked request credit, implicit
timeout revocation, post-shutdown mailbox access, uncontrolled allocation, or
successful stale ticket. Test cancellation and closure before acquisition,
after pinning, after reply publication, and after a consumer takes ownership.

Use independent source-index-derived bytes and exact metadata/interval checks;
pause at documented owner phases rather than using sleeps to hope for a race.
Model exploration is complementary: it checks the declared abstract transition
system and injected broken rules, not the C++ memory model or compiler output.
Cross-thread executable tests and sanitizer checks remain separate requirements.

[ThreadSanitizer](https://clang.llvm.org/docs/ThreadSanitizer.html) instruments
supported targets to detect data races. Its overhead precludes treating its
execution time as a performance result, and a clean run is not a proof that
every interleaving or architecture is safe. Address/undefined-behavior checks
test different failure classes; neither substitutes for race detection.

Only after these correctness gates pass may a new matched baseline/candidate
timing experiment begin. The declared completion, producer-tail and deadline
gates in the [proposal](IQ-HISTORY-NEXT-HYPOTHESIS-2026-09-25.md) still apply.
Real phone/RF, retrospective-to-live decoder handoff and multichannel integration
are later gates, not prerequisites for these independent software experiments.

## Local candidate results

The independent C++ suite passes all 15 groups, with 5,063 assertions and
14,777,814 exact source-oracle bytes. It checks all three formats, handoff-phase
cancellation/close, tick regression and equality, error precedence, stale and
reconstructed-domain tickets, one-credit reuse, reply moves/lifetime, source
gaps/retunes and a 250 ms queued snapshot held while new history is filled.
A two-thread 64-request sequence alternates cancellation and successful takes.
There are no sleeps or wall-clock acceptance thresholds in these tests.

The local Windows GNU C++ 16.1 Release build reports 704 bytes of per-instance
coordinator metadata: 368 allocated control bytes, a 56-byte mailbox and one
280-byte admitted reply. C++ allocation calls are observed around normal
operations; this is not interception of arbitrary C allocation or whole-process
RSS. Retained weak tickets can prolong control allocations across restarts:
aggregate retired-domain admission is **not implemented**. The separate 8 KiB
per-instance cap must not be described as a global memory cap.

Both `arm64-v8a` and `armeabi-v7a` library/contract-executable builds compile
with NDK 28.2.13676358 and API 29; ELF headers identify the intended 64-/32-bit
targets. Neither executable has run on a phone. The sample storage core is
unchanged from the frozen baseline.

The abstract two-request model explores 289 states and 547 transitions, reaching
33 fully released terminal states without an ownership violation. Three model
test groups also check request bounds 1–3 and reject three deliberately broken
rules with counterexample traces. Private in-call steps, weak-memory ordering,
ticket-domain allocation and scheduler fairness are not modelled. The model
does not establish implementation conformance; executable tests are separate.

Local logs/caches are `build/iq-coordinator-root`,
`build/iq-coordinator-final-{build,tests}.log`,
`build/iq-coordinator-abstract-model.json` and the two
`build/iq-coordinator-android-*` build/log sets. These are functional checks,
not isolated timing trials. Remote Windows/Linux and sanitizer results will be
recorded below after the pushed candidate runs.

## Remote verification and preserved evidence

At code commit `294547d8a901c6b3b9bd4cf63ab1750e4ccd99c9`, all four
[coordinator CI jobs](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36117578901)
pass: Windows/MSVC and Linux contracts, Linux address/undefined-behavior checks
and the separate ThreadSanitizer build. The deliberate standalone race produced
the required data-race diagnostic and exit status; the coordinator contract
then passed without a reported race. This supports working instrumentation for
these exercised paths, not proof of all interleavings. Existing receiver and
benchmark framework jobs also pass at this code revision.

The first remote attempt found two test-build issues: an integer-to-byte fill
warning under MSVC and conflicting allocation operators under TSan. The byte
value is now explicitly typed. TSan uses its own operators; only the allocation
counter/assertions are omitted in that build. All ownership/byte operations stay
enabled. Ordinary and address/undefined builds retain allocation probing.
Successful remote CTest output records pass/fail rather than individual stdout
totals; the 5,063 assertion total above is the captured local ordinary build.

The [machine-readable record](evidence/iq-coordinator-contract-2026-09-25.json)
contains source/binary hashes and CI identities. The
[37-entry raw archive](evidence/iq-coordinator-contract-2026-09-25-raw.zip)
preserves source, local logs, model witnesses, Android compile evidence, initial
remote failures and final CI logs including the intentional race diagnostic.
Its SHA-256 is
`f0630094ca1f2cca93d4c216d7440bcae752af376cd321dff9971c0444f416c5`.
The archive is frozen at the code checkpoint; it does not replace earlier
ownership/copy-screen evidence or published applications.

Next: add aggregate admission/reclamation accounting for retired ticket domains,
then instrument real source publication, request selection and complete producer
maintenance. Specify the adapter's service frequency and charge every owner
phase to the comparison; the split test phases are not free work. Only then
can a matched controlled timing screen establish or reject a latency advantage.
