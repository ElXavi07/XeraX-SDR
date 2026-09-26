# Multichannel reception: three falsifiable experiments

Research date: 2026-09-25. Source inspected: XeraX SDR `e174eda` (4.3.1 merged). This document proposes experiments; it does not report new receiver performance measurements or a released multichannel implementation. All numerical acceptance limits below are proposed engineering budgets, not measured guarantees.

Follow-up: a separate raw-history storage prototype was subsequently built and tested; its isolated copy measurements appear below and in its [README](../../experiments/iq_history/README.md). These are storage measurements, not receiver performance results.

## Recommendation

Build sample-domain continuity and acquisition observability first, then a bounded raw-IQ history prototype. They enable a concrete new capability: recover the beginning of a transmission that was captured but recognized late. Develop shared float channelization after these measurements exist. Choose CPU/SIMD or GPU from the measured channel-count/latency crossover, not the presence of a graphics adapter.

The smallest useful production addition is a versioned receiver-event record with explicit sample domain, epoch and loss provenance, plus a nonblocking bounded collector. A benchmark-only first increment can validate that schema and recovery metrics against annotated capture timelines before the events are connected to live DSP. Do not call that first increment an acquisition-speed improvement.

## What the current code already does

| Existing component | Verified behavior | Consequence for the experiments |
| --- | --- | --- |
| `src/platform/channel_bank.cpp`, `include/dsd-neo/platform/channel_bank.h` | Four extra lanes share immutable CU8 capture blocks. Each lane independently mixes and cascades 47-tap half-band filters, then rounds/clamps the result back to CU8 and sends it over a loopback RTL-TCP stream. The socket implementation is compiled for Android/Linux; Windows returns failure. The worker rate is fixed at 192 kS/s; input/output ratio must be a power of two, up to 64 for filter creation. | This is shared capture storage with separate channel extraction, not a shared polyphase filter bank. Windows worker portability and a float input interface are prerequisites to a broad replacement. |
| The same channel bank | A lane has a 1 MiB queued-byte limit and stops on overflow. Blocks have center/rate metadata, but no sample-index range or continuity epoch. A source-center change is rejected by a running lane. | A stalled voice lane must not block control reception. A future restart requires an explicit discontinuity and state reset; silently resuming filtered samples would contaminate timing/filter state. |
| `include/dsd-neo/runtime/input_ring.h` | SPSC float ring, reserve/commit operations, producer-drop count and discard generations. Counts use different units across interfaces: float elements, source bytes and complex sample pairs. | Reuse the existing ring discipline. Define units at every boundary before calculating delay or exporting a loss count. |
| `include/dsd-neo/io/iq_capture.h`, `iq_replay.h`, `iq_types.h` | Capture/replay already stores formats, rate, center, limits, aggregate drops and byte-offset RETUNE/MUTE/RESET events. Writer queue size and flush interval are bounded/configurable. | Extend this timeline rather than create an unrelated capture format. Aggregate loss totals alone cannot locate a missing interval. |
| `src/io/radio/rtl_perf.cpp` | Optional ingest/demod/output timing and queue snapshots exist. | Reuse for cost attribution; snapshots are not individual frame acquisition timestamps. |
| `src/runtime/worker_pool.cpp` | An environment-gated two-thread pool parallelizes intra-block tasks. | It is separate from persistent per-channel decoding. Measure nested parallelism to avoid oversubscription. |
| `benchmarks/xerax_bench/runner.py` | Existing frame/hash/PCM evidence, impairment cases and repeated variants. `first_sync_sample`, `first_valid_frame_sample` and `first_pcm_sample` remain null. | Acquisition and recovery claims are not currently measured. Null must remain null when provenance is unavailable. |

These paths are relative to `upstream/dsd-neo` except the benchmark path. The release's exact-output soft-metric optimization is useful evidence of disciplined change, but does not establish any of the new hypotheses here.

## H1 — A continuity-aware trace will make recovery faults measurable

**Hypothesis.** Many apparent decoder delays can be separated into missing input, queued input, late synchronization, late valid framing, and missing PCM. A bounded event trace will distinguish these cases at substantially less cost than verbose per-symbol logs, allowing subsequent optimizations to target the actual delay.

**Prototype.** Represent a record with a schema version, stream ID, epoch, stage/domain, sample index, event kind, optional protocol/slot/frame identity, and explicit index quality (`exact`, `bounded`, `unknown`). Store source-ingest, first sync candidate, validated frame, first PCM, lock loss, retune/reset and known/unknown input gaps. Never imply that a sync candidate is a validated protocol message. Keep measured wall-clock queue delay separate from signal-domain latency.

Use `uint64` complex-sample indices for the capture domain. Do not divide a demodulator output count by the original input rate. Every rate-changing stage needs an explicit rational mapping and accumulated filter delay; adaptive resampling/timing recovery may require a bounded interval rather than a fabricated exact input index. A retune or rate change creates a new epoch. If the backend cannot know how many samples were lost, record an unknown-duration gap instead of inventing a hardware timestamp. The SigMF specification distinguishes file indices from original-stream indices and provides `core:global_index` for represented discontinuities; that is a suitable export target once actual provenance is known. [SigMF specification](https://sigmf.org/#global_index)

**Controlled experiment.** Use the existing clean DMR/NXDN/P25 captures with known prefixes, then inject 1/5/20/100 ms omissions and corruption separately at acquisition, frame boundary and mid-call. Add retune and rate-change boundaries. Vary producer chunk sizes and queue pressure without changing the underlying sample sequence. Run telemetry off/on against the same frozen binary inputs.

**Measurements and proposed gates.**

- All deterministic test events map to the expected domain and epoch; indices never silently cross a discontinuity. Exact/unknown gap cases remain distinguishable.
- Report signal-to-first-valid-frame, valid-frame-to-first-PCM, and post-gap reacquisition independently. Censored/no-recovery cases are failures or explicit missing outcomes, not zero-millisecond success. Report median and p95 only over their stated population alongside recovery fraction.
- Use a preallocated 4,096-record ring, e.g. at most 64 bytes per event (256 KiB), and a dropped-event counter. Production must never wait for a trace consumer or allocate once per symbol. Drain/file export occurs outside the hot path.
- On identical IQ, trace off/on preserves decoded payloads/PCM, adds no capture drops, and adds no more than 2% median processing time in repeated isolated throughput trials. The percentage is an initial budget, not a result.
- Deliberately saturate the collector. Overflow must be visible and invalidate completeness-dependent latency claims; it must not stall decoding.

**Falsification.** Reject the implementation if clocks/indices are ambiguous, if logging changes reception results, or if its cost exceeds the budget. Even a rejected trace remains informative if the report states which stage cannot yet provide timing provenance.

## H2 — Bounded raw-IQ history can recover captured call beginnings

**Hypothesis.** A short pre-demodulation history lets an independent worker replay a newly recognized in-band signal from before detection, recovering synchronization or call context that the live worker started too late to observe. It cannot recover an RF channel outside the captured passband, samples never delivered by hardware, clipped front-end information, or unknown encryption material.

**Prototype.** Start with an offline ring/extraction model driven by existing capture data. Preserve source format and append sample-range descriptors containing epoch, center, rate and gap provenance. Next place a preallocated history ring at a backend boundary where that metadata is available. Keep a bounded snapshot budget: a slow reader must not pin unlimited old blocks. A snapshot either returns its declared contiguous interval or an explicit partial/gapped/expired result.

Use single ownership of live samples, immutable replay spans and a separate decoder state per replay attempt. A rate/retune discontinuity must split the snapshot and reset relevant DSP state. Copying CF32 samples from the existing demod input could provide a first experiment, but it is not necessarily equivalent to retaining the original device samples; label its stage and scaling accurately.

**Memory calculations.** Payload memory is `rate * seconds * bytes_per_complex_sample`. These values omit descriptors, alignment and any pinned replay snapshot copies.

| Input and format | 250 ms history | 500 ms history |
| --- | ---: | ---: |
| 2.4 MS/s CU8 (2 bytes) | 1.20 MB | 2.40 MB |
| 3.072 MS/s CU8 | 1.536 MB | 3.072 MB |
| 3.072 MS/s CF32 (8 bytes) | 6.144 MB | 12.288 MB |
| 10 MS/s CS16 (4 bytes) | 10.00 MB | 20.00 MB |
| 20 MS/s CF32 | 40.00 MB | 80.00 MB |

MB here means 1,000,000 bytes. Proposed total history-plus-snapshot caps are 16 MiB on phones and 64 MiB on desktop, adjustable downward. Derive allowable duration from the actual format/rate and cap; never promise a fixed duration at every hardware rate. For example, 500 ms of 20 MS/s CF32 alone exceeds the desktop cap.

**Controlled experiment.** Artificially delay recognition by 20/50/100/250 ms, with and without an overlapping *frequency-separated* call inside one passband. Compare late-start-only decoding against replay beginning before the known signal start, with the same decoder and no new RF algorithm. Keep a separate set of real captures whose first useful sync or call context lies in the retained interval. Include near-edge channels, overwritten spans, callback sizes larger than remaining ring space, exact/unknown gaps, and rapid retunes.

**Measurements and proposed gates.**

- Exact recovered bytes and metadata intervals are the initial gate. Never return stale data under a new epoch. Every extra recovered validated frame must match the reference full-capture decode and its call identity; no duplicate frames may be delivered at the replay/live handoff.
- For delayed-detection cases in which the needed samples are retained, improve recovered initial valid-frame count without losing any baseline live control frames. A successful extraction alone is not evidence that first audio is faster.
- Track signal-to-first-valid-frame and signal-to-audible-PCM separately. Retrospective audio may be more complete but intentionally delayed. The interface must make that delay apparent.
- Live processing always has priority. Limit to one recovery job initially and cap its backlog/deadline. If a replay worker processes at `R` times real time while receiving new samples, catch-up time for a history `H` is `H/(R-1)` when `R>1`. Thus 250 ms of history at 4x speed needs about 83 ms to catch up, excluding scheduling/startup. At `R<=1`, it cannot catch up.
- Proposed live-path overhead gate: no new producer drops, no more than 5% extra median CPU time, stable allocation after warmup, and p95 live queue age below the declared 20 ms budget in a 60-minute load test. Export/snapshot jobs must cancel under memory or live-queue pressure.

**Falsification.** If full-capture reference decode cannot recover the target frames, history cannot solve that case. If late recognition is rare relative to RF damage, or live interference/thermal cost outweighs recovered frames, leave history optional and retain the negative result. Test on S25/Pixel hardware before choosing a phone default.

### H2 storage prototype: actual first measurements

The standalone `experiments/iq_history` C++17 prototype now implements a fixed-capacity CU8/CF32 byte ring, exact interval snapshots, stream/epoch metadata, and rejection of missing/stale/overwritten data. It is not connected to live decoding. Its contract test passed an initial run and 20 repeated runs, including 7,000 append/model comparisons per run, format changes and concurrent snapshot/append across an epoch change.

Five isolated Release trials on an Intel i5-1038NG7 / Windows 10 19045 machine with GNU C++ 16.1.0 measured 10 ms appends and 250 ms snapshots at 3.072 MS/s. Median **batch-mean** append costs were 4.882 microseconds for CU8 and 20.089 microseconds for CF32. Snapshot costs, including owned-vector allocation/copy/destruction, were 0.593 milliseconds and 2.505 milliseconds respectively. Append batch-mean ranges were 4.541–5.561 and 18.565–25.609 microseconds; snapshot ranges were 0.527–0.675 and 2.161–2.705 milliseconds. All five runs used the same order, CU8 then CF32; appends and snapshots were not concurrent.

These results show the storage-copy experiment is inexpensive enough on this host to justify further study. They do not measure individual latency tails, maximum mutex holding time, a live producer's blocking, phone performance or recovered speech. The prototype allocates/copies a full snapshot under its mutex and allows callers to retain multiple owned copies, so ring capacity is not a whole-service memory bound.

The next bounded experiment is a preallocated snapshot-credit pool, followed by chunked 64/256 KiB copies that release the mutex and revalidate epoch/retained range between chunks. Use explicit `Busy`/expired results and never deliver a partial snapshot. Measure paced-producer tail latency and outstanding bytes while slow consumers hold credits. This avoids speculative lock-free complexity while testing the two actual remaining risks: unbounded retained snapshot copies and producer interference. Detailed workload, ownership and acceptance criteria are in the [prototype README](../../experiments/iq_history/README.md#next-concrete-experiment-short-copies-after-bounded-credits).

**Subsequent bounded-credit implementation:** `CreditHistory` now exists as a separate optional variant. It preallocates a count/byte-limited snapshot pool, returns `Busy` when occupied and produces move-only leases whose pool ownership survives destruction of the history service. Failure paths return credits, and leased bytes keep their original epoch across retunes. The baseline API remains available; an additive caller-buffer method avoids a temporary snapshot allocation in the new variant. Contract tests cover 1,600 baseline/lease parity steps, budget overflow, exhaustion/reuse, moves, service destruction and concurrent held leases across 99 retunes. Whole-snapshot copying still holds the mutex; chunked copying and paced-producer latency measurements remain pending. The five published timing trials above apply only to the earlier owned-vector prototype, not this bounded-credit variant. See the [current ownership and test contract](../../experiments/iq_history/README.md#bounded-credit-variant).

## H3 — A hybrid float channelizer can beat repeated CU8 extraction at sufficient load

**Hypothesis.** Keeping extracted channels as floats and sharing channelization across many active frequencies reduces redundant filtering, requantization and per-channel transport cost. For sparse use, independent digital downconverters may remain cheaper. A measured crossover should choose the strategy.

GNU Radio provides an oversampled polyphase channelizer with explicit channel mapping and rational output-rate constraints. Its documentation is a useful reference implementation contract, not a measured result for XeraX. [GNU Radio channelizer API](https://www.gnuradio.org/doc/doxygen/classgr_1_1filter_1_1pfb__channelizer__ccf.html)

SDRTrunk's inspected channelizer divides a complex stream into 2x-oversampled subchannels, arranges contiguous sample/filter arrays, and applies an IFFT. It also documents the filter-design requirement for reconstructing channels near subchannel boundaries. Those design choices justify a prototype; they do not imply its Java implementation should simply be copied into XeraX or that a polyphase bank wins at one active channel. [Pinned SDRTrunk channelizer source](https://github.com/DSheirer/sdrtrunk/blob/80360029efb008dca993938d1e34ad4a7a8c15bd/src/main/java/io/github/dsheirer/dsp/filter/channelizer/ComplexPolyphaseChannelizerM2.java)

**Prototype order.** First implement/test a reusable native float-channel input with independent decoder/call state and explicit gap handling. Compare the current CU8 loopback lane against float DDC with the same filter response. Then compare independent float DDCs against a shared oversampled PFB. Only then evaluate a GPU implementation of the already-validated bank. Keep control-channel workers resident; avoid startup per grant. A higher-priority control queue and bounded voice queues prevent busy voice traffic from starving new grants.

One initial design point is 3.072 MS/s with 32 coarse bins and 2x oversampling, producing 192 kS/s per bin before fine mixing/channel filtering. This matches the current worker-rate shape but still requires measured alias rejection and per-channel frequency adjustment. A 64-bin/96 kS/s design is another candidate after the input abstraction accepts that rate. Other hardware rates require a different bank/resampler; they must not be mislabeled 3.072 MS/s. Test arbitrary channel placement, especially halfway between bins and near the usable passband edges.

**Controlled experiment.** Sweep 1/2/4/8/16/32 simultaneous channels at 2.4/3.072/10/20 MS/s where the backend can deliver them. Use deterministic simultaneous DMR/NXDN/P25 traffic with independently known payloads and then legal real captures. Include 20/40 dB stronger adjacent interferers, high grant rates and intentionally overloaded voice workers. Separate these cases from same-frequency collisions and simulcast.

**Proposed gates.**

- In-band passband amplitude/phase error and adjacent-channel rejection must meet a declared filter specification across channel placements. Suggested first laboratory target: no more than 0.2 dB ripple and at least 60 dB stopband attenuation for the declared transition band. These are design goals; actual RF front-end dynamic range may dominate.
- Clean decoded payloads remain equal. Impaired-signal acceptance is based on validated frame recovery, false-valid events and reference payload errors, not prettier constellations. A float path that changes rounding is not automatically a reception improvement.
- Record per-channel CPU, total CPU, peak memory, allocation rate, queue-age p50/p95/p99, missed control grants, lost audio and power/thermal behavior. Use 60-minute sustained runs and cold/warm starts. Retain the simpler DDC below the measured crossover; require at least 15% repeatable total receiver CPU reduction at the intended load before enabling the PFB automatically.
- Initial producer-block budget: 10 ms or less of signal time. At 3.072 MS/s, that is 30,720 complex samples: 61,440 CU8 bytes or 245,760 CF32 bytes. A bank/group delay and transport delay must fit the total latency budget; a large FFT batch is not free latency.

**CPU/SIMD/GPU subexperiment.** Start with generic/scalar and runtime-selected NEON/SSE/AVX kernels; use architecture-specific implementations only when present, with generic fallback and correctness checks. VOLK demonstrates runtime selection of optimized kernels and a profiling/QA approach suitable as a design reference. Its website lists v3.3.0 released February 2026; the separately published generated API docs identify an older version, so pin the actual dependency before adopting it. [VOLK project](https://www.libvolk.org/), [VOLK runtime-dispatch documentation](https://www.libvolk.org/doxygen/)

For GPU trials, report the full `upload + launch + processing + download + synchronization + queueing` time, not just kernel execution. Try resident filter state and 1/2/5/10 ms batches across the channel-count sweep. GPU queue buildup must trigger a measured CPU fallback rather than silently accumulate latency. NVIDIA explicitly emphasizes realistic profiling, reducing transfers, and batching small transfers; that supports testing a bank workload, not promising acceleration of a single low-rate vocoder or cryptographic key search. [CUDA best-practices guide](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/index.html)

Require at least 20% end-to-end throughput or energy improvement in the intended workload, no regression in p95 first-frame latency beyond the declared 20 ms additional budget, no extra control loss, and numeric/decoded-output conformance. Integrated/discrete GPUs and ARM phones need separate results. Failure to cross over is a valid reason to ship CPU-only decoding.

## Overlap: distinguish three different problems

1. **Simultaneous different frequencies inside one captured passband:** channelization plus independent state is directly applicable. Outside the passband, additional hardware or retuning is required; no software history can recover an uncaptured frequency.
2. **Same-frequency independent transmitters:** a channelizer cannot separate them. Successive interference cancellation would need reliable reconstruction, channel/clock estimates and robust residual checks; a decoding mistake can amplify interference. Keep this as later controlled-lab research, with synthetic known signals and strict false-frame gates, not a near-term product promise.
3. **Simulcast of the same signal:** the relevant experiments are multipath/equalization, timing/carrier recovery and possibly aligned receiver diversity. It must have its own channel model and holdout recordings; additive white noise tests do not establish simulcast performance.

No proposal here changes the authorized-key rule or makes modern encryption intrinsically easier to decrypt. Protocol/call state must be isolated across channels, slots, epochs and replay jobs, including privacy algorithm, key ID and message indicator/IV where applicable.

## Build sequence and stopping rules

1. **Build now:** receiver-event schema and continuity-aware benchmark validation, then narrow opt-in native events with proven sample-domain mappings. Preserve null/unknown results where mapping is absent. This unlocks honest acquisition/recovery metrics on both APK and EXE builds.
2. **Next bounded prototype:** raw-history extraction with format-aware memory cap, gaps and expiration tests; replay one delayed in-band call in the lab. Integrate live history only after overhead and correctness gates pass.
3. **Larger architecture change:** cross-platform persistent float workers, then hybrid DDC/PFB and optional GPU crossover experiments. This requires staged implementation rather than a simultaneous rewrite.

Use the existing frozen release binary and corpus as the regression baseline. Partition development/holdout recordings by capture session/site, rotate timed variant order, run speed trials without concurrent compilers/receivers, preserve raw outputs and publish failed hypotheses as well as successful ones. No unmeasured claim of being the fastest decoder follows from this research.
