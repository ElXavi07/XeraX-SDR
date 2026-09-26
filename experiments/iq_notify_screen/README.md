# Schema 5: bounded readiness-wait observer

This standalone observer copies the frozen schema-4 producer, source checks,
CPU accounting and immediate-release workload, then adds a separately recorded
waiting policy. It does not alter previous observers, the notification primitive,
the history/coordinator cores, old results or application defaults. No speed or
CPU improvement has been established by this observer's correctness checks.

Only `--variant coordinator` is accepted. `--wait-mode poll` retains the original
source-stage/yield loop; `--wait-mode notify` waits on the tested readiness
primitive. Both modes use the same executable, source implementation, input
pattern, source selection, deadlines, verification, traces and worker cadence.
Both record a wait operation. The polling loop additionally counts its source
stage loads and yields; that counter overhead is declared observer work, so
historical schema-4 timing values cannot substitute for a new polling control.

## Fixed source workload and deadline meaning

The source still uses 3.072 MS/s, 10 ms producer blocks, 140 fixed prefill blocks,
exactly 8 MiB useful retained history, one 250 ms request every 100 ms and the
existing 50 ms soft source eligibility checks. Every obtained byte and source
metadata field is verified, even when a grant is late. There is no separate
service thread: the owner performs at most three coordinator phases per owner
iteration and reclaims within the same complete producer interval.

Notification wait has a separate **2-second safety timeout**. It is not a new
source deadline or a scheduling guarantee. A notification means a terminal core
response is available, including an error response. The consumer must still
call the actual mailbox take and obey its supplied-tick/deadline result.
Notification Ready cannot make an expired core grant valid or release its lease.

The process CPU counter still brackets worker launch through both joins, including
normal final drain. Prefill, endpoint-memory introspection and output serialization
remain outside that window. No-reader/whole-copy configurations are intentionally
not runnable here; the copied support types are retained to keep the base source
event implementation directly comparable.

## Persistent request-to-token binding

In notification mode, the consumer first arms one generation. It writes that
immutable `Token` and source event identity into a preallocated slot indexed by
request ID, then release-publishes the request ID before calling core submit.
Each request slot is written at most once. There is no token ring reuse.

When owner service returns the actual `Acquired` transition, it acquire-loads
the published request ID and copies that slot into owner-local binding storage.
It captures this mapping **before** the corresponding Granted/Ready transitions.
The single consumer cannot submit another request while its current request is
Pending. Therefore a later rejected submission cannot retarget this captured
binding. The owner notifies only the captured token when that same sequential
core transition reaches Ready; it never rereads a mutable latest-token value
after making Ready visible. Bind and notify work, including sidecar construction,
is charged inside the containing complete owner interval.

Successful arm followed by rejected core admission explicitly abandons only the
notification interest. The source admission result remains the real core result.
Failed arm records a run failure, closes the core and attempts the actual submit,
which returns Closed; no readiness or grant is invented to finish the trace.

## Stop and exceptional cleanup

The owner closes the notification on failure before its bounded source drain,
and again at normal owner termination. The client closes it at shutdown. Closing
is idempotent and sticky. Every close is recorded by its calling role.

A closed/timed-out notification wait records failure and closes the source
mailbox explicitly. It retains the original pending ticket. The existing
exception-only source-stage polling drain is then recorded as `cleanup_poll`,
until the real response is Ready or the owner has ended. It takes and drains the
actual terminal reply and records normal source post-check/outcome rows. It does
not drop requests, manufacture samples or reset source ownership. Such runs are
measurement-ineligible. Clean notification requests use no source-stage polling
loop while waiting.

The bounded owner drain retains its 1,000-iteration limit. If recovery cannot
complete, joined-main emergency cleanup remains explicitly failed/ineligible.
A failure-only `close/postjoin` operation handles a notifier left open by a
thread-launch or cleanup failure; it runs after callers are joined. No destructor
is allowed to race a waiter. Standard-library mutex/wait failures are not injected
by this profile. An unrecoverable exception can leave a partial trace; that is
failed evidence, not a structurally complete measurement.

## Output schema and timing limits

Required outputs are `--csv PATH` and `--sidecar PATH`. Base CSV columns are
unchanged from schema 4. The JSON summary declares `schema_version: 5` and
`base_projection_schema_version: 4`. The independent validator projects only
that summary version when applying frozen schema-4 source checks; counts,
identities, timestamps and failures are not normalized or rewritten.

The separate sidecar columns are:

```text
kind,phase,role,id,request_id,event_id,token_domain,token_generation,
parent_owner_id,parent_service_id,base_row_id,before_ns,after_ns,status,
deadline_ns,stage_loads,yield_calls
```

IDs are contiguous within each role. Domain/generation values are unsigned
identities; times are signed nanosecond offsets from the same origin as the base
trace. Missing fields are blank, not invented zeros. Operations are arm,
map_publish, bind, notify, wait, abandon and close. Producer bind/notify rows name
their actual containing owner row and acquired/ready service row. The operation
follows its referenced service call; it is not falsely placed inside that call.
Consumer wait rows refer to their base request row. No IQ pointers are recorded.

The immutable mapping store/load is inside map_publish/bind before/after brackets.
Notify and CV wait also have call brackets. A consumer may wake and finish waiting
before the producer records notify's after-stamp. Such overlap is valid; neither
post-stamp is an exact publication instant. The existing declared cross-role
clock tolerance is preserved. Sidecar observations establish necessary ordering
and identity consistency, not a full C++ memory-model proof.

`stage_loads` and `yield_calls` count operations inside the recorded wait loop and
its final status inspection. A one-shot Ready assertion after waiting, owner
service state reads and fault-injection handshakes are outside these counters.
The summary separates normal and exceptional-cleanup totals. Clean notify wait
rows report zero loop loads/yields, not a claim that the whole program performs
no source-state reads.

## Bounded accounting

Both modes preallocate producer/consumer sidecar vectors and a request mapping
vector before the CPU window. Capacity depends only on bounded requested duration
and request count. Vectors never grow in worker operations; overflow records a
dropped event and fails the run. Trace output occurs only after workers join.
All arm, map, binding, notification, wait, abandonment and close observations
remain in memory until persisted. Base and sidecar write/flush/close failures
are reported separately and prevent successful completion.

`notification_accounting` exposes actual object storage, active notifier size,
one module-domain counter, token and mapping sizes, both binding values, vector
and Trace object representations, allocated capacities and sidecar row size.
`mapping_reserved_bytes` and `sidecar_reserved_bytes` derive from actual vector
capacities. The optional notifier's storage already contains the active object:
do not add those two values together. The global domain counter is one module
charge, not one allocation per request. Poll mode has inactive notifier storage
and an unused preallocated map; these costs remain disclosed.

The source budget observations remain distinct and unchanged. Additional
observer/object storage is not silently inserted into the core's original budget
claim. Standard-library synchronization resources, allocator overhead, page
rounding, stacks and unrelated runtime allocations remain opaque/excluded.
`sizeof` and vector requested bytes are not RSS or a proof of zero hidden
runtime allocation. No memory-saving claim follows from these mixed scopes.

## Build and validation

```text
cmake -S experiments/iq_notify_screen -B build/iq-notify-screen-agent -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build/iq-notify-screen-agent
ctest --test-dir build/iq-notify-screen-agent --output-on-failure

xerax_iq_notify_screen --wait-mode notify --format cf32 --duration-ms 200 --fault none --csv source.csv --sidecar notification.csv
```

CTest supplies `XERAX_NOTIFY_SCREEN_EXE` to independent `test_inspect_notify`
tests in ordinary and optimized Python. The existing eight bounded fault controls
are retained: none, append, byte, publication-pause, producer-exception,
consumer-exception, pending-shutdown and held-shutdown. A paired performance
conclusion additionally requires a new frozen source/build/validator manifest,
predetermined runs, no concurrent build workloads and the preregistered CPU,
completion and producer/grant latency gates. This observer's short checks cannot
establish a speed improvement, RF quality or readiness for application defaults.
