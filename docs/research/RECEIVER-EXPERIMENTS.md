# Receiver architecture: hypotheses worth testing

This document is an engineering proposal informed by inspected source and primary documentation. It is not a list of implemented features or established speedups. Start with the [measured baseline](INITIAL-RESULTS.md), keep one hypothesis per change and use the [milestone gates](ENGINEERING-ROADMAP.md).

## 1. Establish where time and information are lost

Instrument the receiver stages independently: input/transport, channelization, acquisition, demodulation, framing, FEC, call state, vocoder and output. Report sampled CPU cost, allocation/queue pressure, drops and deadlines. Every observation needs receiver ID, tune generation, sample index, rate and channel identity. A text-log timestamp and whole-process timer cannot determine acquisition delay.

Define signal-onset → first hypothesis, onset → first validated protocol message, grant → first accepted voice frame, and accepted voice → first queued PCM separately. Keep a radio sample clock and a monotonic host clock; account for resampling/filter delay. On retune or a transport gap, emit a discontinuity and invalidate state by generation. A lost timestamp is unknown, not zero latency.

Use prerecorded onset markers and controlled bitstreams to test those definitions before tuning DSP. This instrumentation is the immediate next production-code milestone because it determines whether a faster synchronization algorithm actually delivers earlier correct speech.

## 2. Spend acquisition work where it is productive

Use wideband occupancy to prioritize candidates, then cheap rate/modulation evidence, bounded synchronization hypotheses and protocol validation. Keep explicit unknown/noise output. A known site/channel plan may prioritize a decoder but must not prevent discovery of a changed protocol. Preserve recently successful timing/frequency estimates per channel with an expiry and a fallback hunt.

Compare the scheduler to exhaustive mode cycling on the same bursts, including short calls, wrong prior labels, strong analog interferers and unknown digital modulations. Score missed bursts and false **validated** events, not just classifier accuracy. Occupancy-only detection cannot distinguish DMR, NXDN and P25 reliably enough to trust grants or play voice.

Speculative acquisition can run two or three demodulation hypotheses on the same short I/Q window, then retain the chain with consistent protocol evidence. Bound its CPU budget, cancel losing hypotheses and prevent duplicate call events. This is a proposed optimization, not a claim that trying more settings always improves reception.

## 3. Preserve confidence instead of repeatedly hard-slicing

The current XeraX [`nxdn_frame.c`](../../upstream/dsd-neo/src/protocol/nxdn/nxdn_frame.c) stores one reliability value per dibit and duplicates it for both bits. [`nxdn_voice.c`](../../upstream/dsd-neo/src/protocol/nxdn/nxdn_voice.c) does the same for the voice mapping. The demapper already has richer information in [`dsd_dibit.c`](../../upstream/dsd-neo/src/core/frames/dsd_dibit.c). This is a concrete information-loss candidate, not evidence of a measured bug fix.

Experiment with separate, calibrated bit reliabilities through deinterleaving, puncturing and FEC. Test bit ordering, sign convention, descrambler changes and erasure representation independently; a numerically large but wrong confidence can make soft decoding worse. Compare existing hard/scalar-soft/per-bit-soft paths with identical known codewords and then held-out RF. Preserve clean decoded bits, bound false acceptance, and report FEC block failures and recovered payloads. Never compare incompatible error counters as if they were BER.

## 4. Timing recovery before broad automatic equalization

The initial corpus exposes a DMR field miss with an imposed 100 ppm sample-clock change. Investigate the timing loop, interpolation and filter chain with positive and negative clock offsets, burst lengths, frequency error and sample gaps varied independently. First validate the synthetic resampler against an independently generated reference; linear interpolation itself changes the signal.

GNU Radio documents [symbol synchronization](https://wiki.gnuradio.org/index.php/Symbol_Sync) and [polyphase clock synchronization](https://wiki.gnuradio.org/index.php/Polyphase_Clock_Sync) as explicit stages. They provide comparison designs, not proof that replacing XeraX's loop will improve it. Test fixed versus acquisition/tracking bandwidth, bounded timing hypotheses and rate-specific matched filters.

For P25 CQPSK/LSM, sweep delayed replicas, amplitude and phase; a single echo condition is not a simulcast qualification. Compare the existing equalizer off/on, training strategy and adaptation reset rules. The first A/B experiment improves one marginal counter while losing a clean accepted unit. Require selective activation with hysteresis, sufficient evidence and rollback before any default change.

## 5. One input, multiple persistent channels

Compare an oversampled polyphase filter bank against independent frequency-translate/filter/decimate chains over a grid of sample rates, active-channel counts and occupancy. SDRTrunk's [channelizer implementation](https://github.com/DSheirer/sdrtrunk/blob/80360029efb008dca993938d1e34ad4a7a8c15bd/src/main/java/io/github/dsheirer/dsp/filter/channelizer/ComplexPolyphaseChannelizerM2.java) and GNU Radio's [channelizer description](https://wiki.gnuradio.org/index.php/Polyphase_Channelizer) are relevant references. Oversampling and transition bandwidth matter for channels near bin boundaries.

Share the input and expensive front-end work, then isolate timing, FEC, privacy and call state per channel/slot. Keep the control channel persistent while voice workers start/stop; prioritize control and active speech over spectrum rendering and retrospective experiments. Test grants during queue saturation, worker reuse, slot collisions and cancellation after retunes. A pool of subprocess replays is a useful load baseline but does not implement this architecture.

A single tuner can receive only the captured passband. For a 20 MHz scan range and narrower input bandwidth, use scheduled retuning with measured blind intervals, a genuinely wider receiver, or multiple receivers. No software feature can retrospectively recover samples that were never captured.

## 6. Recover call beginnings with bounded raw-I/Q history

Store a short ring before demodulation and a timeline of tuning, sample rate and losses. When a grant or protocol hypothesis arrives, a worker can replay the available prehistory and catch up under a strict deadline. Compare missed initial voice frames with and without prehistory; test wraparound, stream changes and duplicate suppression.

Memory is predictable: sample rate × seconds × bytes per complex sample. For example, 2.4 million samples/s × 2 seconds × 2 bytes/CU8 is 9.6 MB of raw data; CF32 would be 38.4 MB, before overhead. Pick budgets appropriate to the phone/desktop. Use [SigMF](https://sigmf.org/) for portable recording metadata while retaining XeraX-specific timeline/provenance separately.

## 7. SIMD and GPU: optimize a measured workload

Start with profiles and structure-of-arrays/contiguous batches where warranted. Benchmark existing scalar, SSE/AVX and NEON paths with actual runtime dispatch and numeric parity. [VOLK](https://github.com/gnuradio/volk) demonstrates CPU kernel selection/profiling ideas. SIMD support in a compiler or dependency is not proof that a particular decoder path uses it efficiently.

GPU candidates are wideband FFT/channelizer work, many independent filters and large batches of inference or replay—not automatically every tiny FEC block. Measure transfer, launch, synchronization and batching delay as part of the result. [NVIDIA's best-practices guide](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/) discusses these costs; [VkFFT](https://github.com/DTolm/VkFFT) is a possible cross-vendor FFT backend.

Test integrated GPUs with shared memory and discrete/external GPUs separately. Batch growth can improve throughput while worsening first-audio latency. Choose a backend based on measured workload/capability and preserve a tested CPU fallback. Include sustained power/thermal tests on phones. GPU detection currently present in XeraX is not a GPU radio decoder.

## 8. Local learning that can be independently checked

[TorchSig](https://github.com/TorchDSP/torchsig) offers signal-generation/impairment and learning workflows. It is useful for research infrastructure, not a ready DMR/NXDN/P25 decoder. [Sionna PHY](https://nvlabs.github.io/sionna/phy/) provides differentiable communication simulations; its [real-time neural-receiver example](https://nvlabs.github.io/sionna/rk/tutorials/neural_receiver/index.html) targets 5G and is evidence of a method, not transferable narrowband-radio performance.

First experiment: a small local model proposes occupancy/modulation/rate candidates. Later experiment: predict calibrated bit confidence or equalizer settings. Standard FEC and protocol validation remain the arbiter. Split training/validation/test by transmitter, receiver, site and recording session; reserve unseen radios and channel conditions. Measure calibration, unknown rejection, power and latency against simpler DSP baselines. No cloud language model belongs in the per-symbol deadline, and generated speech must never substitute for recovered radio audio.

## 9. Protocol state deserves the same attention as DSP

DMR Tier II requires both-slot and direct/base/mobile scenarios. Tier III, Capacity Plus, Connect Plus, Capacity Max and XPT need separate state-machine evidence. Test rest/control-channel changes, correct LCN/LSN mapping, late entry, short grants, busy-site churn and contradictory messages. A known color code is only a minimal smoke test.

NXDN48 and NXDN96 need independent timing/filter curves. Type C and Type D require different trunking event sequences and channel maps. P25 needs C4FM and CQPSK/LSM, Phase 1 and Phase 2, network context, ESS and voice/control transitions. The protocol distinctions and reviewed coverage are in the [platform comparison](PLATFORM-COMPARISON-2026.md) and [privacy analysis](PRIVACY-AND-CONFORMANCE.md).

Build deterministic control/voice scenario generators with known original bits. Pair their outputs with an independent encoder or vetted reference capture; two tests using the same encoder bug are not conformance evidence. Add frame-level mutation/fuzz cases and preserve parser bounds/state invariants. Encrypted lab cases add authorized reference material, missing/wrong-key negatives and state loss; no unknown-key recovery assumption is needed.

## 10. Decide by outcome

For each change publish the hypothesis, exact revision/build, corpus hashes and stage, declared tuning budget, paired results, holdout results, failures and decision. Compare reference tools only after input qualification; their different frame/audio counters are not interchangeable truth. A rejected optimization is still useful evidence.

The first priorities are acquisition instrumentation, clean-input reference qualification, clock-recovery experiments and per-bit confidence, followed by persistent multi-channel workers. New hardware integrations, learning and GPU compute follow those foundations. This order targets missed calls and unstable decoding before adding more unmeasured feature claims.
