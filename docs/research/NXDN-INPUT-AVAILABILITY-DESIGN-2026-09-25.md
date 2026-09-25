# Proposed next candidate: explicit NXDN input availability

2026-09-25. Read-only engineering review after checker freeze `2a5af57`; no production/source edits, builds, or receiver executions were performed. This is an implementation design for a separately registered candidate, not an achieved fix. The parent reports that the completed boundary matrix observed four synthesis calls in each prefix, including four unavailable words at 6159 and three at 6160/6161, while the complete early word survived. Those results motivate a per-word guard. The independent results audit remains separate. Do not combine the candidate with acquisition/retention policy changes: the reported bad-LICH follow-on loss is another problem.

## Recommended change

Add an explicit availability result to symbol acquisition and a checked soft-dibit reader. Store availability in the local NXDN frame context, then pass a four-bit permitted-slot mask to voice processing. A slot is permitted only when all its 36 input dibits are available. Check the mask before entering `processMbeFrame[Soft]`, copying its audio buffer, or calling either synthesized-audio function. Do not invoke the vocoder to produce a substitute for missing input.

Do not use any of these shortcuts:

- The global exit flag or current EOF at synthesis: all 182 body reads precede voice processing, so later EOF must not erase a complete earlier slot.
- `symbolcnt` before/after `getDibitSoft`: `use_symbol` can call `print_datascope`, which resets that counter; it also wraps by design. Existing replay EOF paths can increment it without a supplied symbol record.
- Reliability zero as an absence marker: zero is a valid low-confidence *supplied* symbol; 255 also cannot prove availability.
- Returned zero samples/dibits, decoder success, good-looking PCM, or current confirmation: they are not a read-success contract.
- One persistent `last_read_ok` global/state flag whose meaning is overwritten by the next read: use an output result for the particular call and a frame-local copy.

## Exact acquisition and caller seams

### 1. Symbol acquisition: preserve old entrypoints

Files: `upstream/dsd-neo/src/dsp/dsd_symbol.c` and `include/dsd-neo/dsp/symbol.h`.

Suggested new API: `int dsd_get_symbol_checked(dsd_opts*, dsd_state*, int have_sync, float* out_symbol)`, returning 1 only for an available complete logical symbol and 0 for a failed/incomplete read. Always initialize the output; unavailable is never inferred from its numerical value. Retain `float getSymbol(...)` with its current legacy return and side-effect behavior for every existing caller. A shared internal implementation may expose availability through an optional local output argument; do not make all other protocols opt into the new policy as an accidental refactor.

Success points are explicit: successful RTL symbol-rate fast-path delivery; successful completion of the live symbol span; or a successfully read symbol replay record. `symbol_process_live_samples` already returns 0 if a sample, matched-filter catch-up, or shutdown path fails. A partial live span therefore returns unavailable even if some real samples were consumed. The fast path must publish available only after `RTL_SYMBOL_CACHE_READY` and its ordinary generation checks.

Replay needs an explicit distinction that the current helpers do not provide. `symbol_process_symbol_bin_input` returns 1 both for a real record and error/EOF fallback values; `symbol_process_symbol_flt_input` likewise returns 1 after a short read. `symbol_apply_replay_overrides` discards those returns, and `getSymbol` commits afterward. Add a separate record-success result, without changing existing format detection, legacy level mapping, captured soft reliability/LLRs, scaling, pacing, cleanup, or loop behavior:

- Legacy binary: available only after a successful byte read, including dibit zero.
- DSDNSYM2: available only after a complete valid ten-byte record, not a header-only file, a short record, or a malformed header.
- Debug looping: a successful reread after the existing single reopen attempt is available; empty/unopenable looping files are unavailable. Do not add infinite retry.
- Float symbols: available after one complete float, including `0.0f`; 0..3 leftover bytes are unavailable. Do not turn this availability change into a new float-value/signal-quality validator.
- EOF-to-live-frontend fallback: a placeholder returned by the *transition* is unavailable; a subsequent successfully acquired frontend symbol can be available. Preserve the legacy fallback lifecycle.

The compatibility implementation should deliberately retain legacy `getSymbol` behavior, including legacy EOF bookkeeping tested today, while the new checked result makes absence explicit. If preserving that behavior requires leaving a legacy commit counter increment on a replay failure, do so and document it: the new availability bit must not depend on that counter. Avoid a second read to discover availability.

### 2. Checked dibit: capture success before datascope processing

Files: `src/core/frames/dsd_dibit.c` and `include/dsd-neo/core/dibit.h`.

Suggested API: `int dsd_get_dibit_soft_checked(dsd_opts*, dsd_state*, int* out_dibit, dsd_dibit_soft_t* out_soft)`, returning 1/0 availability separately from the dibit. Initialize both outputs on entry. On success use the existing digitization, inversion, ring insertion, binary replay replacement, soft metrics, and capture logic exactly once. On failure return unavailable without treating a placeholder as a new dibit, recording it as captured input, or importing stale previous soft metrics. Do not cast a sentinel -1 into the NXDN dibit array.

Keep `getDibitSoft`, `get_dibit_and_analog_signal`, `getDibitAndSoftSymbol` and their existing callers unchanged in policy. Refactor shared work narrowly enough to preserve normal successful dibit/capture/datascope behavior. The availability value must be local before `use_symbol` invokes datascope; neither its reset nor rollover changes the successful-read result. Do not change the public `dsd_dibit_soft_t` layout or reinterpret its reliability field.

### 3. NXDN local frame contract

File: `src/protocol/nxdn/nxdn_frame.c`.

Add `uint8_t dbuf_available[182]` to `nxdn_frame_ctx`; the existing context zero-initialization gives unavailable by default. Each LICH/body read stores the checked API's result beside the returned dibit and reliability. An incomplete LICH must not be parsed as valid parity/profile. It reaches the existing END accounting with no fresh evidence; preserve sticky-confirmation versus current-proof semantics.

Keep the sequence of logical body reads and ordinary successful dispatch stable for the first candidate, so the observer can compare call lineage without a second unrelated optimization. Unavailable array cells may be internally initialized to deterministic values for memory safety, but those are *not supplied samples* and no guarded channel/word may consume them. The validity map stays in this stack-local frame; there is no cross-frame state to clear in `noCarrier`, init-state, retune or call cleanup.

Compute allowed voice slots from the actual LICH selector, intersected with:

| Slot | Required body dibits, inclusive |
|---|---|
| 0 | 38..73 |
| 1 | 74..109 |
| 2 | 110..145 |
| 3 | 146..181 |

Voice selector 1 permits slots 0/1, selector 2 permits 2/3, selector 3 permits all four; selector 0 permits none. One unavailable dibit rejects its word. Complete earlier slots remain permitted after a later failed read. Do not infer positions from the mask or compact surviving slots: the original slot index is required by mapping, recorder identity, and protocol state.

Prevent confirmation/call metadata from unavailable *control* blocks too. This is a bounded application of the same map, not a new error-correction algorithm. The current unpacking arrays use these exact dibit ranges:

| Control payload | Required body dibits |
|---|---|
| SACCH / SCCH / SACCH2 | 8..37 |
| FACCH first / PICH-TCH first | 38..109 |
| FACCH second / PICH-TCH second | 110..181 |
| CAC (300 bits) | 8..157 |
| FACCH2 / UDCH (348 bits) | 8..181 |
| FACCH3 / UDCH2 (288 bits) | 38..181 |

Gate each selected `nxdn_deperm_*` invocation on its own complete range, retaining existing ordering and all normal CRC semantics. Otherwise a partial block can still manufacture confirmation independently of the new voice guard. A complete SACCH remains eligible even when later voice runs out. For the initial conventional clear replay candidate the active prefix's SACCH is already complete; add direct unit controls for the other ranges instead of claiming that the three active prefixes exercise them.

### 4. Voice entry and side effects

Files: `src/protocol/nxdn/nxdn_voice.c` and `include/dsd-neo/protocol/nxdn/nxdn_voice.h`.

Suggested additive entrypoint: `nxdn_voice_masked(..., uint8_t available_slots)`. Keep `nxdn_voice(...)` as a compatibility wrapper supplying mask `0x0f` for callers that already own a complete buffer. The current production frame handler is the sole production caller found; direct mapping tests and a routing-test stub also call/define the original function. Update the frame handler to use the explicit masked entrypoint. Keep the mapping and hard/soft codec APIs unchanged.

In the existing slot loop, skip an unavailable slot *before* mutating `nxdn_search_voice_index`, constructing its vocoder matrix, calling either MBE entrypoint, copying `audio_out_temp_buf` into `f_l`, or calling `playSynthesizedVoiceMS/FM`. Do not clear/reset the global vocoder merely because a later slot is missing. Do not replay a stale 160-sample audio buffer for a skipped word. A fully supplied permitted slot follows the exact old code path, once.

At `nxdn_process_voice_and_mbe`, zero permitted slots should also avoid opening an MBE file or updating the last-voice activity timestamp solely because LICH claimed voice. Keep file-close/idle behavior explicit and test it. No changes are needed to `mbe_process_nxdn` or mbelib: its FEC, transformations, synthesis and result flags should only receive real permitted words.

There is no `processNXDNVoice` symbol in this source tree. The actual chain is `nxdn_frame -> nxdn_process_voice_and_mbe -> nxdn_voice -> processMbeFrame[Soft] -> processMbeFrameInternal -> mbe_process_nxdn`. The guard must precede the MBE entrypoint: it marks media activity before decoding, and ordinary post-audio work follows even some decoder failure paths.

## Compatibility limits and failure modes

- Explicit availability means a complete logical unit was delivered by the selected input adapter. It is not an RF confidence score or proof that its samples came from one uninterrupted over-the-air transmission.
- Existing RTL generation handling restarts partial symbols, but a frame can still span a retune or different source epochs unless separately guarded. Do not advertise this EOF candidate as a full gap/retune recovery fix. Preserve matched-filter seam and cache-generation tests and require no successful-path regression.
- A matched-filter hand-back is an intentional source-history sample, not absent input. Do not require a new hardware/cache pop for every available sample. Staged PCM resampler tail samples are likewise deliberately delivered; distinguish them from an adapter returning failure.
- Keep existing NXDN48/96 and positive/inverted symbol mappings. The body map is in dibits, so no hard-coded 20-sample decision belongs in production gating. Other timing rates must use acquisition success, not the experiment's sample counts.
- The first empirical candidate is clear conventional routing. Authorized-privacy keystream advancement, serial gaps followed by continued encrypted input, trunk retunes, and acquisition policy are not automatically solved by skipping a slot. Do not synthesize missing words simply to advance such state, or claim coverage without separately registered tests.
- A new checked-reader and masked-voice API bypass the old observer's `--wrap=getDibitSoft`/`--wrap=nxdn_voice` seams. The new candidate harness must wrap the **actual new entrypoints** once, preserve existing body-call/source-pop telemetry, and optionally expose explicit availability. Validate linkage; do not let absent old hooks masquerade as no processing.

## Bounded verification plan before any native comparison

Add contract tests, retaining existing suites and their original assertions:

1. Checked symbol acquisition: complete zero-valued symbol, EOF before first sample, partial span, exact boundary, repeated EOF, RTL symbol-rate success/failure; SPS 20 and 10. Assert availability independently of `symbolcnt`, including rollover. Validate ordinary values/reliability remain exact.
2. Legacy/soft binary and float replay: last complete record then EOF; header-only/truncated/unsupported soft record; missing/null file; debug wrap after one valid record; empty-loop bound; zero float and 1/2/3-byte short float. Compare original APIs' successful values, cleanup and tested EOF bookkeeping with baseline. Do not weaken old `DSP_SYMBOL_REPLAY` expectations.
3. Dibit/datascope: force the actual datascope refresh reset during a valid read and show checked availability remains true; false read must not create captured/stale-soft data. Retain `DIBIT_SYMBOL_BIN_SOFT` and `DIBIT_RTL_FSK_RELIABILITY`.
4. Frame routing: incomplete LICH; each selected control range with its first/last dibit unavailable; complete SACCH plus truncated later voice; rejected-LICH sticky return 1; no stale availability on the next frame. The weak/strong confirmation unit suite remains unchanged.
5. Voice mapping: selectors 0/1/2/3 crossed with masks 0..15, both hard and soft inputs, integer/float audio paths. Exact matrices, original slot numbers, reliability and call counts; no copied/replayed output for skipped slots; all-ones mask equals the old API. Existing `NXDN_VOICE_MAPPING` and `NXDN_FRAME_ROUTING` stay relevant.

Useful current regression targets also include `SYMBOL_MATCHED_FILTER_SEAM`, `RTL_SYMBOL_CACHE_GENERATION`, the frame-sync NXDN phase fixture, and init/no-carrier/retune lifecycle tests. Build the normal radio and radio-less symbol branches. Tests must run meaningfully in the chosen release configuration; avoid new assertions whose side effects disappear under NDEBUG.

## Small once-only candidate replay matrix

Register source diff, new observer seams/checker, fixed candidate identities and gates before running it. Retain the completed baseline executable, all raw baseline traces and the new frozen input corpus as cached comparisons; do not rerun them selectively.

- Core matrix: the exact four active-boundary waves, chunks 37/512 and detail off/on, **16 new candidate identities**. Require actual header/V0 exposure, zero unavailable-slot FEC/synthesis, exact retention of the supplied early slot, and common/detail/chunk consistency. Separately retain the bad-LICH 20-word requirement; this guard does not claim to repair its existing loss. Do not hide that aggregate result.
- Clean retention anchor: unchanged full cold nine-frame waveform, fast=1, two chunks/two detail modes, **four new candidate identities** against the four archived cold-fast records. All 24 occurrences, control state and trailer must survive.
- Before any broader promotion, add a separately frozen bounded preservation set for the prior off-phase recovery and malformed-header/SCCH controls. Compare source positions, CRC/LICH decisions and complete supplied routes against their preserved observations; no improvement is claimed for those independent defects. Do not run old executables or old matrices again just to manufacture a new baseline.

Expected policy-only difference is suppression of work sourced from unavailable input, plus no false metadata proof from incomplete control ranges. Wall-clock speed, RF sensitivity, intelligible speech, speaker playback and product readiness are outside this comparison. If the checked API loses the complete slot at 6160/6161, changes clean 24-word routing, damages replay/datascope, or hides a real callback, reject the candidate.

## Read source anchors

`dsd_symbol.c`: sample adapters and `symbol_take_sample` (1694), RTL fast path (1748 onward), binary/float replay helpers (1856/1923), live-span completion (2035), replay overrides/commit/getSymbol (2133 onward). `dsd_dibit.c`: `print_datascope` resets `symbolcnt` (163 onward); `get_dibit_and_analog_signal` and `getDibitSoft` (1012/1047). `nxdn_frame.c`: local context, control unpack ranges (317 onward), control dispatch (511), voice dispatch (554), body collection/end-frame (608 onward). `nxdn_voice.c`: selector and 36-dibit slot loop. `dsd_mbe.c`: real NXDN FEC/synthesis (872 onward), media marking before decoder dispatch (1959 onward). Headers and existing tests named above were inspected directly. No external protocol assumption is required for these implementation seams.
