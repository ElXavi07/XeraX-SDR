# Bounded readiness notification: contract and proposed experiment

25 September 2026. New work after the [rejected warmed-history screen](IQ-WARMED-SCREEN-2026-09-25.md).
No notification performance result exists yet. Existing cores, schema-4 inputs,
results and application packages remain frozen. Starting revision: 54ca2b0.
The source snapshot build/iq-notification-baseline-54ca2b0.zip has SHA-256
be736fde99f58f5defa67afb50af7afa171d765e4cea9193c6e4c1028e351f1f.

## Question and scope

The previous candidate used 11.9% more median process CPU than whole-copy while
completing every request. Yield-polling is one plausible contributor, not an
established cause. Test a single readiness notification against the unchanged
polling coordinator, keeping source data, deadlines, owner cadence, core phases,
verification and full owner accounting identical. Do not compare against a
historical CPU value or label this a faster radio decoder.

First establish a standalone notification contract and independent concurrency
controls. Then validate its binding to the actual mailbox before extending the
observer. A primitive check does not establish a safe whole-pipeline handoff.

## Primitive contract

One producer, one consumer and one preallocated notification object. Consumer
arm reserves at most one generation; producer notify must name that generation.
The ready predicate and checked wait share a mutex. Notification is sticky until
consumed, so signal-before-wait is valid. Timeout keeps the reservation; explicit
abandon discards notification interest only and never revokes a source lease.
A sticky close wakes waiters and prevents reuse. Roles stop and join before
object destruction. No operation is claimed lock-free or hard real-time.

Tokens contain a domain and generation. A monotonic module-local domain counter
rejects overflow and separates reconstructed objects; sharing tokens between
processes or independently loaded module copies is outside this contract.
Generations reject overflow rather than wrap. Closed takes precedence over token
identity, readiness and timeout. A ready matching token may beat an already
expired wait deadline; radio-request eligibility remains a separate core check.
All state and token sizes, plus the one module counter, must be reported. Opaque
standard-library mutex/condition-variable resources are not magically included
in sizeof(object) or a process-RSS claim.

The C++ condition-variable contract releases the mutex atomically with blocking,
allows spurious wakeups and requires a predicate recheck and safe destruction.
[C++ primary specification](https://eel.is/c++draft/thread.condition.condvar).
Release/acquire operations can publish prior writes only under the specified
synchronizes-with relationship; unrelated wall timestamps do not supply it.
[C++ atomic ordering](https://eel.is/c++draft/atomics.order).
Windows WaitOnAddress also requires value rechecks and permits early wakes;
it is a possible later platform adapter, not the selected portable primitive.
[Microsoft API contract](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitonaddress).

## Independent correctness gates

Force notification before waiting and while waiting using explicit handshakes,
not sleeps as proof. Exercise spurious notifications, expired and future wait
deadlines, close-before-wait and close-during-wait, duplicate notifications,
foreign/stale/future generations, abandon, counter exhaustion and joined
reconstruction at the same address. Runtime checks must remain enabled under
NDEBUG. Preserve failed runs. Windows/Linux, ASan/UBSan and TSan are required;
TSan counts only after the existing three deliberate-race controls pass.
Compile Android arm64-v8a and armeabi-v7a; label device runtime pending.

## Binding to the real mailbox

The consumer must arm before making Pending visible. An admitted request must
have an immutable token mapping that the owner obtains through real published
state. Capture that mapping while servicing Pending-to-Acquired, before a client
can consume Ready and reuse a request slot; do not read a mutable latest-token
value after publishing Ready. Notify only for the matching terminal Ready
transition. Error replies still require core take/drain. A notification timeout
cannot silently abandon a pending core request or reset its ownership credit.
Close/failure wakeups must not pretend that an unfinished reply is Ready.
Test these relationships against the actual coordinator and exact source bytes
before claiming integration complete. Notifications never carry IQ pointers.

## Measurement prerequisites and proposed gates

Use a new observer extension and keep schema 4 unchanged. Record arm, matched
notify, wait and cleanup operations with identities and brackets; include owner
notification work in the complete producer interval. Charge token storage and
notification object/runtime accounting explicitly. A sidecar trace must be
bounded and hashed with the source trace, and validate every normal/error path.
Freeze all sources, binaries, compiler options, inputs and run order beforehand.

Proposed six-run screen: three sequential pairs in polling/notification,
notification/polling, polling/notification order. Each run lasts 30 seconds after
140 prefill blocks with the same CF32 byte workload and 300 scheduled requests.
Both variants use identical observer instrumentation except the stated waiting
mechanism. No competing experiment/build work runs during timing. Preserve each
attempt; never retry a negative performance result until it passes.

Require at least 10% lower median process CPU and lower CPU in at least 2/3 pairs;
at least 95% absolute and paired eligible verified completions in every round;
no more than 5% producer-p99 regression per paired round; no more than 1 ms increase
in request-to-take p99 upper bound per round; no added producer work above 10 ms;
and all existing byte, ownership, memory and source-identity checks. These gates
must be frozen in a tested runner before any performance run. Passing permits a
longer study only, not application-default promotion or a whole-decoder claim.

## Status

Primitive and bounded real-mailbox composition checks now pass. Persistent
observer integration, CPU comparison and phone/RF tests remain pending.


## Verified correctness checkpoint

Implementation revision `81e19e07505c08e13d4116fac04fcbe0eb7a8f05` adds the
standalone C++17 primitive and two independent contract executables. It does not
change existing slab/coordinator cores or any application. Normal and error
readiness remain separate from successful source ownership.

The primitive suite passes 12 groups, 2,890 explicit checks and 2,256 independent
source bytes. The separate composition suite passes four groups, 1,811 checks
and 4,374,528 exact bytes. All checks remain active with NDEBUG. Composition
uses actual CU8/CF32LE/CF32BE storage and coordinator replies, cancellation,
deadline equality, source errors, close and retained ownership. Across 128
concurrent generations, take and byte verification occur before joining the
producer; thread-join cannot provide the missing publication ordering. A held
core lease still rejects new admission after the notification has been consumed
or closed. Error/timeout notification never erases an outstanding core request.

These tests use immutable token capture published through thread construction
and explicit handshakes. They do not implement the persistent observer's future
per-request token map, trace extension or waiting-policy comparison. Reusing the
primitive is not sufficient evidence that that later integration is correct.
Standard-library lock/wait exceptions are not fault-injected. Lifetime remains
join-before-destruction, and safety timeouts do not imply bounded runtime latency.

Both [PR CI](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36129200071)
and [push CI](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36129195680)
pass Windows/MSVC, Linux, ASan/UBSan and TSan. Each TSan job first diagnoses all
three predetermined deliberate control races. Existing receiver/NXDN,
coordinator, observer and benchmark workflows pass. Third-party Macroscope
review remains skipped at its configured cost limit, not a new review pass.

Fixed object representations differ by ABI: local GNU Windows 64 bytes,
Linux 136 bytes, MSVC Windows 200 bytes, plus one 8-byte module domain counter.
These are representation sizes, not measured OS allocations or RSS. Both test
executables cross-compile for Android arm64-v8a and armeabi-v7a, with ELF identity
checks; device execution remains unavailable.

[Machine-readable evidence](evidence/iq-notification-contract-2026-09-25.json)
and [raw archive](evidence/iq-notification-contract-2026-09-25-raw.zip) preserve
sources, binaries, source-baseline archive, strict local build/test output,
Android targets and full CI/control logs. The archive has 46 entries, 494,148 bytes,
SHA-256 `716f0c503a9956e9f7702d3693ee02fe17e3e34741d9c7e7956bc9ee1e081bc3`.
Every entry was reopened and byte-verified. These executables are research
contract tools, not Android APKs or a Windows installer.

No notification CPU/latency trial has run, so performance remains null/pending.
The prior measured rejection stays frozen. Next work is a separately versioned,
bounded notification trace and persistent mapping to source requests, followed
by independent sidecar-corruption/error controls and a frozen six-run comparison.
No released package, user setting or production default changes at this checkpoint.
