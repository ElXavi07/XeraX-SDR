# NXDN48 recovery: primary-source review and falsifiable next tests

Reviewed 2026-09-25. Read-only research; no native experiment, product edit or performance run. Local source snapshot: `04c0ed3e4e4689bc5ee483cc432c4dc6c4ea62db`, vendored DSD-neo baseline `8c9c120389401fc2db3ef52869e13d555712e5fb` with XeraX changes. The proposals below are hypotheses, not measured improvements.

**Recommendation:** first characterize the existing decoder with a fixed damaged-FSW and sample insertion/deletion matrix, retaining complete payload truth and negative outcomes. Do not start by smoothing/freezing the current timing correction. Keep matched filtering disabled in this first discriminator-domain profile, then add a separate filter-transition profile with content-position instrumentation. A new timing loop is a later, evidence-dependent candidate.

## Primary evidence and reproducible references

1. **NXDN waveform context.** The NXDN Forum describes FDMA/4-level FSK and the 6.25 kHz mode's 4.8 kbit/s rate. That corresponds to 2,400 dibits/s, not 4,800 symbols/s. At this experiment's 48 kHz discriminator rate, one symbol is 20 samples. [NXDN Forum technical specifications](https://www.nxdn-forum.com/what-is-nxdn/technical-specifications-of-nxdn/). Our independently encoded profile has 192 dibits per frame: 3,840 samples / 80 ms before deliberate sample-count transformations. These are nominal source-domain durations, not software processing latency.

2. **DSD-neo's measured negative timing experiments.** Maintainer PR449 documents five unsuccessful changes to the existing FSK timing nudge, including requiring crossing agreement, freezing after lock and widening correction bands. The analysis preserves decoded-frame counts and uses rotated paired replay order; lower raw error totals alone are not an improvement. This is reported evidence on the maintainer's captures, not independently reproduced here. [PR449](https://github.com/arancormonk/dsd-neo/pull/449), merge `2c82bc800c005a5ec63547ca6187e14a5afda91e`. The motivating issue's own per-frame correlation estimate was noisy enough to worsen a previously good sampling grid. [Issue444](https://github.com/arancormonk/dsd-neo/issues/444).

3. **The later diagnosis was the filter transition.** PR454 compensates the matched filter's change in content position by priming, consuming delayed outputs, or handing raw history back. It identifies 67 samples of delay for its 135-tap NXDN48 filter at 20 SPS. It also reports that a separately tried closed timing loop was not merged: its result was near the measured noise floor. Thus PR449's closing recommendation is not evidence that a new loop will now win. [PR454](https://github.com/arancormonk/dsd-neo/pull/454), merge `512b1655789e49d324e8a3c53bc7a1e362559475`. The seam correction is already present in XeraX; it is not a feature we should claim to newly add.

4. **GNU Radio defines the loop's prerequisites.** `symbol_sync_ff` separates timing-error detector, interpolator, loop bandwidth/damping, TED gain and average-period deviation limits. Its documentation requires suitable pulse shapes for non-CPM detectors and appropriate amplitude normalization for decision-directed detectors. TED gain depends on amplitude, pulse shape and noise. A stock parameter set is not an NXDN performance guarantee. [GNU Radio API3.10.9.1](https://www.gnuradio.org/doc/doxygen/classgr_1_1digital_1_1symbol__sync__ff.html), [pinned header](https://github.com/gnuradio/gnuradio/blob/e0711ad64f293161f9d1ce52b4817e070b604bc0/gr-digital/include/gnuradio/digital/symbol_sync_ff.h). Tag `v3.10.9.1` resolves through annotated tag `c366b5bfc77b5028515a1fe883ea2cbff5a9b1cc` to commit `e0711ad64f293161f9d1ce52b4817e070b604bc0`. This is the documentation version actually inspected, not a claim it is the latest GNU Radio release.

5. **liquid-dsp offers another concrete timing structure.** Its synchronizer uses matched/derivative filter banks, a filtered timing error and rate/phase adjustment. This supports an experimental design with observable phase/rate state; it does not prove that its assumptions match NXDN discriminator pulses. [Documentation](https://liquidsdr.org/doc/symsync/), [source at `d61cf506d427439f2ce38bf556362ad7a7aa8fa0`](https://github.com/jgaeddert/liquid-dsp/blob/d61cf506d427439f2ce38bf556362ad7a7aa8fa0/src/filter/src/symsync.proto.c). Git blob `84a074cf9d981bf52be035f1b79f1f8a91ed3c89`,18,197 bytes, fetched from the repository Contents API.

6. **OP25 provides an FSK reference implementation, not an NXDN benchmark here.** The inspected FSK4 demodulator uses fractional interpolation, symbol-error feedback and separate spread/frequency adaptation. Those coupled loops should be evaluated together rather than copying one constant. [Source at `71abcd0ead32f86f51615ea6cc8a6a4dba4c949a`](https://github.com/boatbod/op25/blob/71abcd0ead32f86f51615ea6cc8a6a4dba4c949a/op25/gr-op25/lib/fsk4_demod_ff_impl.cc), Git blob `77bb1e6199d1181928dcb49986922f7d19513784`,25,759 bytes. The inspected boatbod `rx_sync.cc` did not supply an NXDN recovery implementation; do not advertise a comparison against its NXDN decoding. No SDRTrunk NXDN support/performance assertion is made without an inspected implementation.

## What XeraX currently does

Local `dsd_frame_sync.c:1645–1745` accepts a fixed set of five positive and five inverted 10-sign patterns; it is not an arbitrary Hamming-distance search over the full 20-bit FSW. The optional fast path only admits the first **canonical positive** NXDN48 waveform match while unconfirmed, with normal frame validation afterwards. Do not conflate this with accepting every damaged sync or with confirmed payload recovery. The profile guards also protect other protocols; any candidate that widens matching must preserve those guards.

In `dsd_symbol.c:570–622`, the 20-SPS correction changes one sample according to two crossing-index bands. `symbol_adjust_timing_index` does nothing while `have_sync != 0`. The matched-filter seam at lines1974–2077 compensates delay changes, clears the obsolete crossing and resets its history on stream-generation changes. The RTL cache rejects obsolete generations. Therefore a repeated or missing input sample within one generation is different from an explicit retune/reset boundary.

RC3 `nxdn_frame.c` now opens and closes evidence even when LICH rejects early. `nxdn_confirm.c` distinguishes current-frame evidence from sticky transmission confirmation. Historical return1 must not count as a recovered frame. A CRC pass also is not cryptographic authentication.

Reviewed raw SHA-256:

| File | SHA-256 |
| --- | --- |
| `src/dsp/dsd_frame_sync.c` | `c17a7c46599d5a46fa82c4cecc143fd8f365677862898a8d035240b98af2667d` |
| `src/dsp/dsd_symbol.c` | `40da0a486400ed7f827edf601a8dab7b80f1f1ebb984ee2fcef9b365881cf4af` |
| `src/protocol/nxdn/nxdn_frame.c` | `a2c0d15efd6258c1469df2ebbb7dea05400f9e0ab74fba653c1e20125f04919a` |
| `src/protocol/nxdn/nxdn_confirm.c` | `e204f0c709e3e919cf8689fffecd2f2fa043360a07979a44334b470a12afee7b` |

## Three testable mechanisms

### 1. Reacquisition after damaged FSW, without carrying false proof

**Question:** after a valid confirmed frame, can the current matcher return to the next true frame when one subsequent FSW is damaged, and does its optional first-canonical mode alter this outcome? This initial experiment needs no decoder change. The zero-damage counterpart establishes which starts were already decodable.

Freeze a multi-frame extension of the existing benign control vector with independent SACCH/FACCH truth. Corrupt one chosen FSW dibit's sign in the encoded dibits before waveform rendering, preserving the frame body and later frame boundaries. Explicitly enumerate which mutations remain in the implementation's tolerated sign-pattern set; do not label those as a rejected-FSW control. Keep the known extra payload sync-like window at position170. Include a complete-FSW erasure control as a separately named synthetic operation, not an RF fade.

Record every sync candidate/accepted frame, not just true ones, through enough subsequent intact frames for recovery or explicit censoring. A recovered frame must have the correct transformed true boundary, fully supplied input, current proof and exact independently expected channel bits. Preserve all failed FEC/LICH/false-window events. Pair fast-off/on without retuning the corruption positions after seeing results.

**Falsifiers:** false current proof on a known non-boundary; historical confirmation counted as recovery; post-damage payload mismatch; a declared recovery advantage obtained by dropping difficult cases or reducing the counted true-frame population. If both modes recover equally, there is no speed gain to claim.

**Possible later candidate, only if the baseline exposes a gap:** one-frame, boundary-predicted retry derived solely from a previous validated frame, with bounded candidate count and normal LICH/full CRC validation. Prediction must never come from test truth, extend scanner hold on its own, or synthesize voice before normal evidence gates. A candidate that just accepts more syncs has not demonstrated better decoding.

### 2. Discriminator sample-slip recovery and filter-seam continuity

**Question:** which phase/count discontinuities can the existing between-frame correction recover from, and are apparent losses actually filter-transition bookkeeping? Start with matched filtering off and unchanged timing constants.

For the first bounded matrix, use separately declared deletion and duplication of1,2,5,10 and20 discriminator samples. Choose fixed locations before a true FSW, inside its interval, and inside a frame body after earlier valid confirmation. A20-sample change is a whole nominal symbol; a1-sample change is1/20symbol. Include no-op and identical-reader chunk sizes1,37,512 as invariance controls. Keep one fault per stream before combining faults.

Maintain an explicit transformed-index→canonical-index map. Deleted samples have no delivered index; duplicated samples map to the same canonical sample with an explicit duplication flag. The decoder's actual pop indices are in the **transformed delivered stream**, not the original waveform. Derive every later boundary from that mapping; do not use the old `floor((consumed_end-640)/3840)` formula unchanged after a count-changing operation. Unknown hardware gaps must not be filled and labelled captured data.

Then add a **separate** matched-filter-enabled profile. Existing `MATCHED_FILTER_SEAM` and `SYMBOL_MATCHED_FILTER_SEAM` tests are references for priming, longer/shorter delay and hand-back. Extend observation of decoded content lineage before interpreting frame latency: successful raw-cache pop highwater measures available input, while hand-back may decode older content and catch-up consumes samples without emitting corresponding symbols. A single fixed group-delay subtraction is insufficient at switches.

**Falsifiers:** a no-op transform changes results; reader chunk boundaries change the transformed waveform or truth; stale-generation samples enter the new stream; failure is hidden by EOF padding; an apparent recovery gain disappears when compared at matching true-frame identities. Separate stream-generation resets from unannounced sample slips so the tested recovery policy is explicit.

### 3. A bounded fractional timing loop, only after the recovery map justifies it

**Hypothesis:** an explicitly instrumented interpolator plus measured timing-error loop can improve a specific reproducible slip/drift failure without sacrificing intact frames or increasing false current proof. The primary sources establish feasibility, not expected superiority; the maintainer's previous near-noise-floor loop result lowers confidence in a quick win.

Use one fixed architecture and a preregistered small parameter grid calibrated on separate training waveforms. Observe fractional phase, average sample period, timing-error residual and clamp events. Test isolated phase steps separately from continuous sample-clock offset, with held-out pulse shapes and frame payloads. Respect the pulse-shape/normalization requirements of the chosen TED. Do not plug the existing flat/ramped discriminator fixture into a detector and infer RF suitability merely because the clean control passes.

The promotion gate needs more fully correct frames or shorter recovery to the same frame identities, unchanged clean/negative behavior, bounded memory and separately measured CPU cost. A lower error total because fewer frames were produced is failure. This candidate should stay standalone until real complex-IQ replays with independent payload truth confirm the benefit. No GPU or external AI service is required for this first low-rate loop experiment.

## Measurement contract to preserve

- **Domains:** discriminator-array edits are post-demodulation tests. They do not exercise RF filtering, AGC, carrier offset estimation, multipath, adjacent-channel interference, clipping or driver loss. A sample deletion is a transport/count discontinuity; a fractional resampler models a specified clock offset; AWGN in complex IQ is another distinct experiment. Name each accurately.
- **Truth:** freeze generator, transformations, streams, hashes and expected frame/channel bits before running the receiver. Use wrong-CRC, wrong-LICH, fixed random/zero, polarity and existing extra-sync controls. Do not repair a failing vector to suit the decoder.
- **Positions:** capture actual delivered-pop indices and transformed/canonical mapping. Keep provider-read frontier, delivered-pop frontier and decoded-content positions distinct. Cached read-ahead is not consumed evidence. Check observer-enabled/disabled parity.
- **Recovery:** report source samples from the declared corruption end to the first later fully correct current-proof frame, plus missed true-frame count and success/censor counts. Also report the matched no-fault baseline by the same source frame. Source duration converted with48kHz is not CPU wall time, audio latency, or time-to-intelligible-speech.
- **Failure handling:** input exhaustion invalidates fully supplied-frame claims; preserve emitted results and mark truncation. A timeout/no recovery remains in the denominator. Keep false accepts visible even if subsequent CRC rejects them.
- **Comparison:** correctness first, fixed paired inputs and no retry-until-success. If wall/CPU measurements are later added, use unchanged instrumented builds, equivalent work and rotated ordering; the existing replay tools are a starting reference, not a replacement for payload truth.

No encryption or key-recovery hypothesis is part of these tests. The deliverable here is a bounded recovery map and a decision about whether further timing work has a demonstrated target.
