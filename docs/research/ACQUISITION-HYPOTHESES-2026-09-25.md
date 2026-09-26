# Acquisition and confidence experiments — September 25, 2026

Reviewed baseline: XeraX SDR 4.3.1, commit `e174edab8ead3c867d8a82043c14029a3d5238a3`. This note separates inspected defects, measured unit experiments and proposed RF experiments. None of the proposals establishes better sensitivity, faster speech acquisition or encryption-key recovery by itself.

## First experiment: correct NXDN confidence arithmetic before adding more confidence information

**Hypothesis:** eliminating a biased soft Viterbi branch cost and stale block state recovers the minimum weighted-cost codeword more often without changing the hard decoder's trellis, framing, privacy or vocoder. Physical likelihood optimality would additionally require correctly calibrated input confidence.

Two concrete implementation problems were found in [`nxdn_convolution.c`](../../upstream/dsd-neo/src/protocol/nxdn/nxdn_convolution.c):

1. `CNXDNConvolution_decode_soft()` divides a reliability-weighted mismatch cost by 128, then forms the opposing branch as `8 - metric`. Its total opposing cost does not depend on reliability. When both reliabilities are zero, one branch costs zero while its opposite costs eight. An absent observation therefore favors a path. The division also destroys useful resolution and prevents exact uniform-weight equivalence to the hard decoder.
2. `CNXDNConvolution_start()` resets pointers without clearing path metrics. The engine initializes these arrays once, while independent NXDN blocks repeatedly call `start()`. Decoding block B can depend on the unrelated block preceding it.

This affects real input paths: [`nxdn_deperm.c`](../../upstream/dsd-neo/src/protocol/nxdn/nxdn_deperm.c) explicitly represents punctured bits with reliability zero and forwards them to this soft decoder. The existing CRC-gated hard fallback can hide a soft-decoder failure in a broad clean-field smoke test. Existing `test_nxdn_convolution.c` even expects different hard and all-255 soft output for the same input; freezing different outputs does not establish confidence arithmetic correctness.

Independent comparison: [MMDVMHost's decoder and encoder](https://raw.githubusercontent.com/g4klx/MMDVMHost/master/NXDNConvolution.cpp) and [DSDcc's implementation](https://raw.githubusercontent.com/f4exb/dsdcc/master/nxdnconvolution.cpp), inspected September 25, reset both metric arrays at block start. Their encoder equations provide a separate test oracle: the two outputs are `d XOR d3 XOR d4` and `d XOR d1 XOR d2 XOR d4`. They are related codebases, so agreement between them is not two independent conformance implementations.

### Measured before/after experiment

[`checks/nxdn_convolution_reference.cpp`](../../checks/nxdn_convolution_reference.cpp) implements those polynomial equations directly, without using the decoder's branch tables. For noisy eight-bit payloads with four termination bits, its exhaustive oracle checks every payload and all 16 allowed initial histories. It accepts any equal-cost optimum rather than assuming one tie-breaking convention. This independently checks decoder arithmetic, not the full NXDN air interface.

The test was compiled against the unchanged 4.3.1 decoder and the isolated correction using local GCC/G++ with `-O2 -Wall -Wextra -Werror`; separate baseline/candidate objects and outputs were kept under ignored `build/acquisition-agent-tests/`. Results:

| Invariant | Baseline passed | Candidate passed | Meaning |
| --- | ---: | ---: | --- |
| Every clean eight-bit payload, hard and soft | 512/512 | 512/512 | Encoder bit order and termination agree on clean inputs |
| All-255 soft output equals hard output | 138/256 | 256/256 | 118 mismatches despite uniform reliability were eliminated |
| Changing only erased placeholder values changes nothing | 256/256 | 256/256 | Necessary erasure property; does not by itself detect path bias |
| Soft output minimizes independent weighted codeword cost | 8/256 | 256/256 | 248 non-optimal results on the declared short-block corpus were eliminated |
| Block B equals B following unrelated A, hard and soft | 301/512 | 512/512 | 211 previous-block dependencies were eliminated |
| Long uniform-weight blocks equal the hard decoder | 0/32 | 32/32 | Includes 96, 203, 300 and 2400 trellis steps; checks cumulative-cost behavior |
| Midpoint observations: uniform parity and weighted oracle | 30/128 | 128/128 | Exercises all valid observed values 0/1/2 and arbitrary byte reliabilities |

The candidate passed **1952/1952 invariant cases**, versus 1245/1952 for baseline. These are test cases, not an RF error-rate estimate. All-255 parity is valid here because a constant positive scale preserves hard-path rankings and ties. The weighted oracle includes zero, 17, 63, 128 and 255 confidence values, varied separately for each bit, plus a separate midpoint-input set with unrestricted byte weights.

### Full-length controlled known-bit recovery

[`checks/nxdn_convolution_channels.cpp`](../../checks/nxdn_convolution_channels.cpp) adds a separate experiment with **1792 complete convolutional code blocks**. These are not complete over-air NXDN protocol frames: the experiment does not generate CRC-correct messages, sync words, interleaving, I/Q or audio. Original source bits are generated first, independently convolutionally encoded with four zero tail bits, impaired, decoded and compared bit for bit. Expected results never come from the decoder.

Two new deterministic seeds, `0x77AACE01` and `0x123F9917`, produce 64 blocks each per profile. The same 128 source blocks and impairment locations are used in each paired baseline/candidate comparison; no production parameters were tuned on this experiment. SACCH-shaped blocks contain 32 source bits, 72 encoded bits and the 12 punctures reconstructed by `nxdn_depuncture_12_5_rel()`. FACCH-shaped blocks contain 92 source bits, 192 encoded bits and the 48 punctures reconstructed by `nxdn_depuncture_16_9_rel()`. Punctures use placeholder zero with reliability zero. Input state is fully reset before each vector, isolating arithmetic from the independently tested previous-block defect.

Retained correct bits use reliability 255. The low-confidence conditions deliberately mark the known flipped positions with reliability 16; this tests whether the decoder can use supplied confidence, **not whether a real demodulator identifies errors that accurately**. Uniform-confidence flips keep reliability 255. Burst positions are four consecutive surviving coded-bit positions after puncturing, not four adjacent RF symbols. The additional-erasure case removes four such positions with zero reliability.

| Profile | Condition | Exact blocks, baseline → candidate (of 128) | Incorrect source bits, baseline → candidate |
| --- | --- | ---: | ---: |
| SACCH | Clean, unpunctured | 128 → 128 | 0 → 0 |
| SACCH | Clean, punctured | 51 → 128 | 797 → 0 |
| SACCH | Two flips, uniform confidence | 20 → 125 | 1234 → 7 |
| SACCH | Two flips, low confidence | 35 → 128 | 1026 → 0 |
| SACCH | Four-bit burst, uniform confidence | 3 → 19 | 1282 → 292 |
| SACCH | Four-bit burst, low confidence | 16 → 128 | 1203 → 0 |
| SACCH | Four additional erasures | 16 → 128 | 1189 → 0 |
| FACCH | Clean, unpunctured | 128 → 128 | 0 → 0 |
| FACCH | Clean, punctured | 0 → 128 | 4848 → 0 |
| FACCH | Two flips, uniform confidence | 0 → 124 | 5017 → 8 |
| FACCH | Two flips, low confidence | 0 → 128 | 4887 → 0 |
| FACCH | Four-bit burst, uniform confidence | 0 → 1 | 4930 → 558 |
| FACCH | Four-bit burst, low confidence | 0 → 122 | 4906 → 6 |
| FACCH | Four additional erasures | 0 → 127 | 4921 → 1 |

Across these declared conditions, exact recovery rose from **397/1792 to 1542/1792 blocks**; wrong source bits fell from **36,240 to 872** among **111,104 scored source bits**. The candidate still returns incorrect bits on 250 deliberately impaired blocks. All 512 clean unpunctured/punctured candidate blocks recover exactly. The executable's exit gate requires those clean cases to pass; impaired-case counts are reported, including failures, rather than falsely asserting every corrupted block must be recoverable.

Both versions were compiled against separate frozen decoder objects using GCC/G++ `-O2 -Wall -Wextra -Werror`. Machine-readable JSONL output is retained locally in `build/acquisition-agent-tests/channels-baseline.jsonl` and `channels-candidate.jsonl`, including seeds, dimensions, correct/incorrect block counts, wrong-bit counts and the first failing original/decoded payload per condition. Because this exercise calls the soft convolution routine directly and omits production CRC checking and hard fallback, **these baseline block-failure rates are not baseline application failure rates**. The result demonstrates actual known-bit correction under declared code-block conditions; it makes no RF SNR, sensitivity, timing or speech-intelligibility claim.

### Implemented candidate and promotion gate

The candidate uses the full weighted cost `abs(expected0-observed0)*r0 + abs(expected1-observed1)*r1`. With observations clamped to their documented 0..2 domain, its opposing cost is `2*r0 + 2*r1 - cost`. Both costs become neutral at zero reliability; no per-branch integer division is needed. Metric arrays reset at every independent block start. Path accumulators are widened to 32 bits: retaining full weights raises the maximum increment to 1020, so arbitrary 16-bit cumulative storage is not justified.

The independent invariants pass. Integration acceptance also needs NXDN deinterleave/puncture/CRC coverage, M17 reuse of `start()` and the existing hard decoder, and paired replay against the complete 76-case corpus. The completed native replay and M17 stream checks are recorded below, with their coverage limits. Report changed valid payloads, failed CRCs, fallback frequency and voice frames; a changed PCM hash is neither automatically good nor bad for a reception correction. Wrong/noise frames must not gain trusted state merely because their metric is lower. Preserve the six clean known-field gates and ten noise/random-pattern gates; unit results alone do not authorize a reception-quality claim.

The helper uses process-global arrays. Correct arithmetic does **not** make it safe for simultaneous in-process decoder workers. A later multi-channel change must put this state into a per-decoder context or provide equivalent isolation.

### Independent review of native replay and M17 reuse

The [compact review evidence](evidence/acquisition-review-2026-09-25.json) records the exact native binary hashes and per-case findings. The completed native comparison contains 76 paired cases / 152 runs, one measured run per variant. The clean known-field and negative-signal gates pass. Eight impaired NXDN cases change voice-frame totals; the shared frame records explain why raw totals alone are misleading:

| Case | Frames, baseline → candidate | Exactly identical suffix, including frame error fields |
| --- | ---: | ---: |
| NXDN48 added noise 20 | 228 → 244 | 228 |
| NXDN48 added noise 10 | 228 → 244 | 228 |
| NXDN48 added noise 0 | 228 → 216 | 216 |
| NXDN48 carrier offset | 228 → 236 | 228 |
| NXDN48 adjacent interference | 172 → 184 | 172 |
| NXDN48 cochannel interference | 266 → 270 | 266 |
| NXDN48 repeated traffic | 704 → 736 | 228 |
| NXDN96 added noise 20 | 72 → 76 | 72 |

Every record in the shorter output also appears in the longer output in order, with identical AMBE payload and per-frame error fields. The repeated-traffic case is checked as a complete ordered subsequence, not merely its final 228 frames. These are text-record comparisons after removing wall-clock timestamps; without consumed-sample provenance they do not measure acquisition latency or resolve every repeated frame's RF position.

In the NXDN48 added-noise-0 case, candidate output is exactly the baseline's last 216 frames: it omits the first 12. Baseline initially reports RAN 05 before RAN 01; candidate initially reports RAN 01 and assembles `Src=901` earlier in control-log order. This is consistent with changed confirmation timing, but there is insufficient complete payload truth to declare all omitted or added early audio correct or false. Lower error totals from fewer frames do not by themselves prove better reception. Likewise, more errors while decoding additional early frames do not prove worse decoding of the shared frames. Noise labels describe the corpus's added-noise transform, not calibrated RF SNR.

The inspected call chain supports that interpretation. SACCH soft decoding checks CRC-6 and tries the existing hard decoder only if that check fails. FACCH uses CRC-12 with analogous fallback; CAC and FACCH2/UDCH retain their CRC-16/CRC-15 checks. `nxdn_confirm.c` confirms on one stronger check or two consecutive weak-evidence frames, and `nxdn_process_voice_and_mbe()` waits for confirmation before delivering voice. Correcting soft control bits can therefore change when otherwise unchanged AMBE records begin reaching the player. Short CRC collisions remain possible, and choosing a lower weighted cost cannot prove a decoded message correct. No CRC or confirmation gate was relaxed by this patch.

M17 has two shared hard-decoder call sites: stream payload and BERT. The existing `M17_STATE_DISPATCH` test replaces `CNXDNConvolution_start/decode/chainback` with fakes, so its passing result is not numerical validation of this change. `M17_REFERENCE_VECTORS` primarily checks separate algorithms/reference data and likewise is not direct evidence for this shared routine. Meaningful native coverage is `DECODE_IQ_M17` / `DECODE_IQ_M17_AUTO`, plus exact hard-decoder code-block invariants.

An additional real native M17 fixture replay was run against both frozen binaries using `-fz`, fast I/Q replay, frame logging and WAV output. Both exited successfully and recognized `SRC: N0CALL`. All 88 normalized sync/call/error lines matched, including existing LSF/embedded-LSF CRC failures. The complete 79,404-byte WAV files were byte-identical, with 19,840 stereo frames at 8 kHz and 38,610 nonzero channel samples. Their SHA-256 is `197275f696b3b5c1a337b7ad74f9dc38228b03a36d1b7e5ef1a8f429e18d9085`. The frame logger emitted no M17 payload records, so this establishes PCM/log parity on that stream fixture, not payload-log equality or BERT coverage.

**Review decision:** no new correctness blocker was found in the isolated arithmetic/reset change. The exact branch-cost derivation, known-bit experiments and bounded path accumulation support it as a correctness repair. Native replay supports compatibility on this corpus while revealing changed confirmation behavior. It does **not** establish universal RF improvement, faster acquisition, better intelligibility or multi-channel safety. Physical hardware, wider noise false-acceptance testing, calibrated per-bit confidence and M17 BERT integration remain distinct evidence gaps.

### Next confidence experiment, deliberately separate

[`dibit.h`](../../upstream/dsd-neo/include/dsd-neo/core/dibit.h) already provides separate MSB/LSB signed metrics. [`nxdn_frame.c`](../../upstream/dsd-neo/src/protocol/nxdn/nxdn_frame.c) currently retains their minimum as one dibit reliability, then duplicates it into both bits. [`nxdn_voice.c`](../../upstream/dsd-neo/src/protocol/nxdn/nxdn_voice.c) likewise duplicates it in the AMBE map.

After the arithmetic correction has its own result, retain each bit's absolute metric separately through descrambling, deinterleaving and puncturing. Known XOR descrambling changes the hard bit/sign, not the reliability magnitude; maintain the documented MSB/LSB order. Require independent bit-mapping and puncture tests before RF replay. A more detailed but poorly calibrated metric can worsen decoding, so promotion needs held-out noisy recordings and known payload truth. Do not combine this with the arithmetic patch and then attribute all gains to one change.

## Second experiment: a continuously tracked fractional FSK symbol clock

**Hypothesis:** a measured phase-and-rate loop with interpolation retains DMR/NXDN synchronization across clock mismatch and short fades better than occasional whole-sample timing nudges.

The baseline's DMR 100 ppm field miss is a reason to test this, not proof of a timing-loop defect: the corpus's linear resampling also changes waveform quality. [`dsd_symbol.c`](../../upstream/dsd-neo/src/dsp/dsd_symbol.c), `symbol_adjust_timing_index()`, applies its FSK timing adjustment during unsynchronized search, using an earlier crossing index. Its source comments and [upstream issue 444](https://github.com/arancormonk/dsd-neo/issues/444) warn that apparently conservative changes to this nudge can worsen real calls. Those upstream measurements were not reproduced in this study and are not XeraX performance results.

[GNU Radio's Symbol Sync contract](https://raw.githubusercontent.com/gnuradio/gnuradio/main/gr-digital/include/gnuradio/digital/symbol_sync_ff.h) makes the relevant controls explicit: timing-error detector, loop bandwidth/damping, detector gain, maximum period deviation and interpolation. The correct detector gain depends on pulse shape, amplitude and noise; inserting arbitrary familiar Gardner/Mueller–Müller constants is not a justified fix. Matched-filter assumptions must be checked for the actual FM-discriminator waveform.

Build an opt-in lab path before changing defaults. Generate known payloads with an independent pulse-shaped transmitter and fractional resampler; use random start phase, positive/negative 0/10/25/50/100/250 ppm, multiple burst lengths, separate carrier offsets, noise and sample-gap cases. Split development and holdout seeds. Instrument actual consumed sample indices, loop state, first validated frame and recovery after a marked gap. Measure payload block error rate and missed initial voice frames as well as speed. A single short color-code assertion cannot establish clock stability.

Proposed promotion gate: no clean payload regression, no increased validated false acceptance, lower paired block-error count on at least two predeclared mismatch conditions in held-out data, and bounded added CPU/latency under a declared phone/desktop budget. Hardware acceptance must include independent RTL-SDR clocks and a second receiver family. Keep a rollback to the existing path while that evidence is collected.

P25 already has a distinct CQPSK timing path in [`costas.cpp`](../../upstream/dsd-neo/src/dsp/costas.cpp). [OP25's Gardner implementation](https://raw.githubusercontent.com/boatbod/op25/master/op25/gr-op25_repeater/lib/gardner_cc_impl.cc) provides an inspectable interpolation/rate-tracking comparison. Reusing a design is not evidence that identical gains suit FSK, nor that an FSK improvement benefits CQPSK. P25 recovery needs its own C4FM/CQPSK, phase-step, fade and discontinuity experiments.

## Third experiment: validated sync candidates with an honest false-alarm model

**Hypothesis:** bounded near-sync candidates followed by protocol-specific validation can recover damaged sync faster while avoiding spurious channel holds, provided the candidate model matches the actual sliced alphabet.

A concrete documentation hazard exists in [`sync_hamming.c`](../../upstream/dsd-neo/src/dsp/sync_hamming.c): its probability example assumes independent uniform four-valued symbols. In [`dsd_frame_sync.c`](../../upstream/dsd-neo/src/dsp/dsd_frame_sync.c), `frame_sync_symbol_to_dibit()` emits only `1` or `3` when its CQPSK four-level option is false. Ordinary FSK sync search therefore has a binary sign alphabet even though its payload modulation has four levels. The same source currently uses exact DMR sync strings; the Hamming helpers also serve modulation evidence. Do not describe every Hamming score as an accepted frame.

For an ideal balanced independent binary null and a 24-symbol pattern, `P(H <= t) = sum(C(24,k), k=0..t) / 2^24`. At `t=4` that is **0.000771939754486 per window**, versus **3.26107496562e-9** under a uniform four-symbol null. At 4800 symbols/s, the binary expectation is roughly **3.705 raw candidates/s for one pattern**. These are theoretical candidate counts, not a measured end-to-end false-call rate. Filtered noise, biased slicing, overlapping windows, multiple patterns and remaps need empirical treatment. The existing four-symbol table's `t=8` entry also needs correction to approximately `2.02210569924e-5`.

[ETSI TS 102 361-1 V2.6.1](https://www.etsi.org/deliver/etsi_ts/102300_102399/10236101/02.06.01_60/ts_10236101v020601p.pdf), sections 9.1.1 and 10.2/10.3, provides the DMR synchronization and modulation context. It does not justify applying a four-ary random-symbol bound to a receiver that discards symbol magnitude during sync search.

First implement/check alphabet-aware analytical examples and counter instrumentation. Then compare exact search with a strictly bounded soft candidate path on damaged sync plus valid following payload, short noise bursts, random binary/4FSK, analog interference and wrong-rate traffic. Require subsequent protocol evidence appropriate to the field: a candidate string alone must not trigger a trusted trunking retune, audio claim or persistent identity. Include a scan-level penalty for false holds, not only decoder CPU time.

For P25, test a short retained timing/frequency estimate only when tune generation, modulation/rate and input continuity still agree; expire it and retain a cold-acquisition fallback. Measure gap-to-first-validated-unit and voice-start loss using sample-indexed events. The previous mixed P25 equalizer result remains insufficient to enable equalization everywhere. This is a proposed later experiment, not a default change justified by this note.

## Recommended order

Finish integration testing of the isolated NXDN arithmetic/block-reset correction first. Correct the sync model documentation without broadening thresholds. Add sample-indexed acquisition evidence, then test fractional FSK timing and per-bit confidence as separate experiments. Test P25 warm reacquisition and selective equalization on held-out impairment families before enabling either automatically. Each rejected experiment should retain its corpus, parameters and failure evidence so it is not rediscovered as a new promise.
