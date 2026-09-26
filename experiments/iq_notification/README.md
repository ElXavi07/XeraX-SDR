# Bounded readiness notification: correctness experiment

This is a new, standalone C++17 primitive. It has no source-history ownership,
decoder, device, worker thread or benchmark. Existing sources, measured screens
and application defaults are unchanged. Its purpose is to make a future test of
passive waiting possible without losing a terminal readiness notification.
There is no performance result for this primitive.

## Roles and API

`xerax::experiment::notification::ReadyNotification` permits one producer and
one consumer. The consumer calls `arm()`, then waits with the returned
`Token{domain,generation}`. The producer calls `notify(token)` for that exact
request. A controller may call `close()` concurrently to stop a blocked waiter.
Both role threads and any controller/observer calls must finish and be joined
before the object is destroyed. `close()` does not perform a join.

| Operation | Contract |
| --- | --- |
| `arm()` | Creates one generation when idle; returns `Busy` while occupied, `Closed` after stop, or `CounterExhausted` at the generation limit. |
| `notify(token)` | Sets one sticky ready predicate; repeated notification returns `AlreadyReady` without adding credit. Wrong, stale or future identities return `NotCurrent`. |
| `wait_until(token, deadline)` | Returns `Ready` and consumes the notification slot, or returns a terminal/status result described below. |
| `abandon(token)` | Discards this notification interest only, after any wait has returned. It does not cancel or reclaim the corresponding source request. |
| `close()` | Sticky, idempotent stop. Clears pending readiness and wakes a blocked waiter. |
| `state()` | Returns a synchronized diagnostic value. It is not a reservation or a promise that the observed state will remain current. |
| `accounting()` | Reports the actual fixed object, shared counter, token and state-value sizes. |

`Config.max_generation` and `Config.max_predicate_checks` must be positive.
Their defaults are `UINT64_MAX`. Smaller limits support deterministic exhaustion
tests; there is no reset or rollover operation.

## State and precedence

```text
Idle --arm(g)--> Armed(g) --notify(g)--> Ready(g)
Ready(g) --wait(g)--> Idle
Armed(g) --timeout--> Armed(g)
Armed(g) / Ready(g) --abandon(g), no blocked wait--> Idle
Any --close--> Closed --any later operation--> Closed
```

The mutex establishes the order of concurrent changes. Wait precedence is:

1. Closed.
2. Wrong or no longer armed token.
3. Another blocked wait (`Busy`; it never consumes that waiter's token).
4. Ready, which consumes the slot.
5. Predicate-check budget exhaustion.
6. Deadline expiry (`TimedOut`).

A ready predicate wins over an already expired deadline. Consequently `Ready`
does **not** prove that the notification or subsequent source take met a source
deadline. It says only that this exact generation was ready when inspected under
the mutex. A source coordinator's independent admission/take checks must remain
in place. This wait is cooperative: OS scheduling and mutex acquisition or
reacquisition can delay return past its deadline.

`TimedOut` and `CounterExhausted` retain the armed generation. The consumer may
wait again, or explicitly abandon notification interest and separately complete
source cleanup. Late old-generation notifications cannot become a future
generation's readiness. `abandon()` while a wait is blocked returns `Busy`;
concurrent cancellation is the controller's `close()` operation instead.

The predicate counter advances on each false-ready wait-loop evaluation. This
includes an evaluation that observes deadline expiry. It never wraps; once its
lifetime budget is exhausted, further blocking attempts are rejected. A valid
already-ready token can still be consumed, and close retains highest priority.
This counter is diagnostic/exhaustion evidence, not a timing measurement.

## Synchronization and identity

All predicate reads and changes use the same mutex. A waiter checks readiness
while holding it; the condition-variable wait atomically releases that mutex
and blocks. Each return, timeout or spurious wake goes back through the guarded
predicate. A notification that happens before the consumer begins waiting
leaves readiness stored in the predicate. The CV notification alone is never
treated as a token. See the primary C++ contracts for
[condition-variable waits](https://eel.is/c++draft/thread.condition.condvar) and
[mutex synchronization](https://eel.is/c++draft/thread.mutex.requirements.mutex).

The module has one monotonic atomic domain allocator. Construction reserves a
new nonzero domain by compare/exchange, rejecting exhaustion before increment;
per-object generation allocation similarly rejects overflow. Plain tokens from
a destroyed instance cannot match a reconstructed instance, even if its address
is reused. Tokens neither own nor keep retired notification objects alive.

This identity contract is limited to this module allocator's lifetime. Tokens
must not be exchanged across independently loaded copies, module unload/reload,
or processes. This is not a persistent identifier scheme or an authentication
mechanism. Atomic domain allocation is construction work and is not claimed to
be lock-free on every target.

## Ownership, memory and failure limits

The class never acquires a source lease. A future adapter must arm before
submitting its source request, associate the immutable token with that request,
and signal only its terminal response. `Ready` can mean that an error response
is available; it is not a successful grant. The adapter must still take, inspect,
release and acknowledge source ownership according to its separate protocol.
Notification abandonment or closure must never erase an outstanding source
request or revoke consumer-owned bytes.

The implementation contains one mutex, one condition variable and fixed scalar
state. It has no vector, queue, owning token, explicit dynamic allocation,
callback or spawned thread. `sizeof(ReadyNotification)` accounts its fixed C++
object representation; `accounting().shared_domain_counter_bytes` is one shared
charge per module, not an extra allocation per instance. External Token/State
value objects are reported separately and callers may create their own copies.

These values are **not** process RSS or a proof of zero operating-system/runtime
allocation. Standard mutex/CV implementations may use implementation-specific
resources or internal allocation. Constructor, lock and timed-wait failures may
raise standard-library exceptions. No hard latency, real-time, wait-free or
lock-free guarantee is made. A wait-scope guard restores the `waiting` diagnostic
if a timed-wait exception propagates while the mutex is reacquired. As in the
standard contract, failure to restore the lock postcondition can terminate.

The friend `ReadyNotificationTestAccess` is reserved for independent tests. It
can issue a predicate-neutral CV wake and exercise the production domain-counter
helper with a separate local atomic. It must never reset the real allocator or
mutate a live object's identity. No test callback is present in the production
wait path. `state().waiting` establishes that an observed waiter has released
the shared mutex; an increased predicate-check count acknowledges a spurious
wake was processed without inventing readiness.

## Validation scope

The independent CMake/test target owns strict release-mode checks for token
identity, notify-before-wait, actual thread handoff, spurious wakes, stop/timeout
precedence, counter exhaustion and source-ownership separation. Tests must not
use timing or a CPU reduction as their correctness oracle. Any later comparison
needs a new preregistered profile, including all notification costs and a
matched unchanged polling control; the earlier negative screen stays intact.
