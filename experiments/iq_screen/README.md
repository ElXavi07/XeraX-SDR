# Schema 4: fully warmed IQ measurement profile

This is a new standalone measurement profile copied from the schema-3 observer at the frozen `78dcd40` checkpoint. It does not modify schema 1/2/3, any history/coordinator core, or an application. It adds the prerequisites for a separately preregistered comparison; it does not establish that any receiver or decoder is faster.

`none`, `whole` and `coordinator` retain the schema-3 producer, request, exact-byte verification, immediate-release, exception and shutdown behavior. `none` is the same whole-copy producer with no requests. Ingress is 3.072 MS/s in 10 ms blocks; requests are 250 ms long at 10 Hz, with a 50 ms soft eligibility deadline. Owner intervals include generation, append/state/publication bookkeeping, at most three coordinator service calls and reclaim. There is no extra service thread. The CSV columns and release/acquire publication identities are unchanged.

There are now **140 fixed prefill blocks for both CU8 and CF32**. This gives each adapter exactly 8 MiB of useful retained history before workers launch. The executable checks the actual quiescent source state after prefill, and reports it along with the independently traceable final prefill publication. The same capacity must still be retained after the run. Setup and prefill remain outside the process CPU measurement window; all prefill work remains visible in the trace. Source data are deterministic opaque IQ-storage bytes, not demodulation waveforms.

## CPU accounting window

`process_cpu` records real process CPU counters from `GetProcessTimes` on Windows or `clock_gettime(CLOCK_PROCESS_CPUTIME_ID)` on Linux/Android. It does **not** use Windows `std::clock`, a wall-time estimate or the sum of sampled worker intervals.

Each CPU API call has steady-clock before/after brackets. The start call completes immediately before worker construction; the end call starts after both workers join. Thus the measured counter interval includes thread launch, the scheduled-start wait, all worker execution, drain and join, and excludes prefill, endpoint-memory inspection, trace serialization and file output. Start/end counter values, their difference and the inner/outer elapsed-wall bounds are retained. Samples failing at either endpoint or regressing invalidate completion. Exceptional post-join recovery stays explicitly marked and cannot produce an eligible measurement.

The CPU counter includes all threads in this process. Its difference may legitimately exceed elapsed wall time. `logical_cpu_count` is `hardware_concurrency()`'s hint, not a cgroup quota, affinity guarantee or count of processors actually used. A declared gross-sanity allowance of **20 ms per reported logical processor** is supplied for the validator; this is not a measured error bound. It must not be turned into a CPU accuracy claim.

Windows FILETIME has 100 ns storage units, but this is **not** a demonstrated CPU-accounting resolution. A short smoke test may report a zero counter difference despite having performed work. POSIX `clock_getres` is reported separately as an API resolution, not empirical calibration. Raw CPU counters remain the primary recorded data. Missing logical-count/resolution information must be treated explicitly by eligibility policy rather than replaced with invented precision.

## Source memory observations and their limits

Quiescent `source_memory_before` and `source_memory_after` observations are bracketed outside the CPU window, with a common 8 MiB useful-retention requirement and zero outstanding ownership after drain.

- Whole-copy endpoints expose the real `CreditHistory::credit_stats()` payload/slot/credit fields and history state. The payload is 8 MiB ring plus one 7 MiB snapshot slot, totaling 15 MiB. The API does not expose its heap metadata; this remains marked opaque.
- Slab endpoints expose the real process-budget payload, arena/control metadata, separate ledger allocation, configured limits and arena count. They also report retained slabs, filling bytes, live claims and snapshot pins. Payload is 256 slabs of 61,440 bytes, totaling 15 MiB, including four scratch slabs.
- Coordinator endpoints report the actual shared reservation ledger and `Mailbox::metadata()`, including actual control allocation requests and the fixed Mailbox/one-Reply reservation. The configured aggregate ledger cap is 16 KiB, separate from the slab's 128 KiB metadata cap.
- `abi` reports the actual object sizes needed to check those equations. Candidate `unreserved_facade_bytes` includes the slab History, slab ProcessBudget and coordinator Budget facades. It excludes Mailbox because the coordinator's fixed reservation already includes it. Whole-copy's field reports its heap CreditHistory facade size.

These are source payload/API reservation observations, **not RSS**. Allocator headers, page granularity, fragmentation, runtime allocations outside C++ source objects, thread stacks, timing/trace buffers and the ingress buffer are excluded. Trace and ingress requested capacities remain disclosed separately. Before/after endpoint equality is not a sampled measurement of arbitrary hidden peak process memory; the core budgets provide their separate bounded-ownership contracts.

## Separate whole-copy allocation calibration

`xerax_iq_memory_calibration --format cu8|cf32` is a separate untimed executable. Its replacement allocation operators are **not linked into `xerax_iq_screen`**. A fixed 64-entry pointer/size table observes successful C++ allocation requests while constructing the selected whole-copy source on the heap, warming it with 140 blocks and taking/verifying a snapshot. Ingress and reporting allocations are outside that scope. It records actual source allocations, heap metadata after subtracting the 15 MiB payload, the real CreditHistory/SnapshotLease sizes, operational allocation count, and full release accounting. It also records the still-owned allocation after History destruction while a snapshot survives, followed by zero live tracked bytes after lease release.

Calibration must complete without operational allocation, overflow, unbalanced tracked frees or outstanding memory. The declared baseline metadata reservation adds one `sizeof(SnapshotLease)` to the observed source heap metadata and must fit 128 KiB. This observation covers C++ allocation requests, not all `malloc` traffic or operating-system memory.

The baseline calibration and candidate API ledgers deliberately disclose different accounting bases: actual heap requests plus one lease-size reservation versus slab allocations plus coordinator fixed reservations. **Do not subtract them to claim memory savings.** The common comparison gates are equal bounded payload, bounded explicitly accounted metadata and returned ownership. A uniform whole-process memory comparison would require additional measurement.

Under ThreadSanitizer, replacement allocation operators can conflict with the sanitizer runtime. The calibrator explicitly reports `available: false` there and cannot authorize a memory gate. Use a normal native calibration with matching source/compiler/binary provenance; an instrumentation-only CI run must report any omitted calibration assertion.

## Build, provenance and eligibility

```text
cmake -S experiments/iq_screen -B build/iq-screen-agent -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build/iq-screen-agent
ctest --test-dir build/iq-screen-agent --output-on-failure

xerax_iq_memory_calibration --format cf32
xerax_iq_screen --variant coordinator --format cf32 --duration-ms 100 --fault none --csv trace.csv
```

CMake `XERAX_WHOLE_SOURCE_DIR` selects the actual whole-copy implementation for **both** executables. Its default is the current source and must never be labeled frozen. The parent runner selects the independently verified `274677a` four-file source directory for frozen baseline/none runs and records source, compiler, binary, calibration and trace hashes. Use matching calibration for whole/none eligibility; a calibration from another selected source or ABI is not interchangeable.

CTest supplies `XERAX_SCREEN_EXE` and `XERAX_MEMORY_CALIBRATION_EXE` to the independent validator/tests in normal and optimized Python modes. A single trace still emits `performance_eligible: false`; an independent `measurement_eligible` result means its declared measurement gates passed, **not** that a speed hypothesis succeeded. A comparative conclusion additionally requires the preregistered paired/rotated runs, matched source intervals and complete failure evidence.

Grant latency can only be bounded using matched, unique acquired/granted/ready service-call brackets and the actual submit/take observations. These are not exact internal linearization timestamps. The validator checks necessary event/tick feasibility, not a full replay or proof of the coordinator state machine. Cross-role tolerance remains a declared clock-feasibility allowance; terminal acknowledgement remains observer-reported. None of these measurements establishes RF sensitivity, protocol decoding quality, intelligibility or application stability on real hardware.

## Fixed comparison driver

`run_screen.py --output NEW_DIRECTORY --frozen-source FOUR_FILE_DIRECTORY --host-context HOST.json`
creates fresh Release/Ninja GNU/Clang builds, runs all correctness tests and the
untimed native calibration, then freezes the manifest before any30-second trial.
The fixed nine-run order and gates are in the preregistration. Input hashes are
checked before/after preparation and around every trial; differing compiler
commands or changed inputs invalidate the whole screen. Failed processes and
partial traces remain on disk. No trial is retried. Existing output directories
are rejected. A valid negative performance finding exits0; a broken experiment
exits1. This driver is an engineering screen, not an application benchmark.

Fifteen independent policy/failure controls run in normal and optimized Python
through CTest. They use synthetic metric fixtures and mocked processes, never
pretend to be actual timing measurements. The driver requires a host JSON with
processor, power_plan, background_activity and process_priority(normal) fields.
