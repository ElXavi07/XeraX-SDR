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

Primitive implementation and independent tests are in progress. Mailbox binding,
observer instrumentation, CPU comparison and phone/RF tests have not run.
