# NXDN finite-input and voice-path observation, version 2

Registered before generating new inputs or executing a new native observer.
Preserve the failed recovery study at938c5fe, its frozen engine, all216 invocations,
and RC1/RC2/RC3 artifacts. This is an observation experiment with unchanged decoder
policy. Passing it does not improve or retroactively pass the recovery study.

## Hypothesis and boundary

H1: a separately built observer can distinguish fully sampled dibit calls from
partial/empty calls after finite EOF, report final SCCH CRC7 and actual LICH/voice
staging decisions, and preserve the existing receiver's decisions. H0 includes
changed decisions, invented sample provenance, incomplete or incorrect channel
observations, or a missing positive/negative observation control.

Use the actual continuous engine, DSP, frame/channel decoder and vocoder with
48 kHz discriminator input, NXDN48 profile known, filtering/scanning/trunking
disabled and no audio device/file output. Acquisition is fixed off; the previous
matrix already observed the same targeted failures with both settings. No native
decoding algorithm, product source, defaults, settings or installed binary changes.

## Frozen finite matrix

From the completed recovery inputs, copy h0-warm_clean, h0-cold_sync_blank and
h0-warm_drop20 exactly. Add four prefixes of h0-warm_clean, without reshaping or
padding:12360,12361,12380 and12521 samples. They target no LICH input, one partial
LICH sample, one completed LICH dibit then EOF, and a complete LICH followed by
one partial payload sample. Boundaries are source coordinates, not provider reads.

Add two independently checked synthetic SCCH observation controls. Their sequence
is the same h0 C,C,S,S prefix followed by two V frames. V has parity-valid LICH
full0xEF/profile0x77,25 zero SCCH information bits and a CRC7 initialized to all
ones with polynomial x^7+x^3+1. One control transmits that CRC; the other flips its
high bit before convolutional encoding. Append four zero tail bits, encode with
the existing verified K5 polynomial convention, puncture every sixth coded bit,
interleave the60 transmitted bits with the12-by5 mapping, and use144 zero voice
dibits before the normal PN95 whitening. These are known SCCH information/check
fixtures, not independently validated speech or standards-conformance vectors.

Render new controls with the same32-dibit alternating preamble,20 samples/dibit,
centered eight-sample smoothing, and64-dibit +8000 trailer. Validate generated
channel/frame bytes independently before execution. If that validation fails,
do not silently change the declared vector to suit a decoder outcome.

Nine waveforms, chunks37/512 and detailed observation off/on:36 fresh processes,
once each. No rerun of the216-case matrix. The three copied waveforms also have
archived same-option/chunk/observer outcomes for comparison, without rerunning
the old executable. Preserve all build errors and native failures; do not retune
inputs or retry for a favorable outcome.

## Instrumentation contract

Keep the old recorder untouched. New private generated source adds read-only
LICH decision and SCCH final-result hooks. LICH events include rejected outcomes
and the actual applied profile flags. Capture final25 information and7 received
checkword bits after any fallback and before evidence/semantic updates. Recompute
CRC7 independently. Soft-pass/fallback flags are diagnostics, not final acceptance.

Wrappers around real voice/vocoder/audio functions forward each call once.
Record call nesting, entry/exit buffer indices and optional finite/nonzero/peak
statistics of explicitly named internal float/short buffers. Buffer values and
write-count changes are not playback, intelligibility, valid speech or successful
vocoder acceptance. Zero errors can be reset by failure handling. No synthesis
success claim is allowed without an actual observed return/result contract.

Common per-dibit records capture EOF, delivered-coordinate frontiers and
symbolcnt before/after the real getDibitSoft call. Datascope is explicitly zero,
so its display cannot reset symbolcnt. Successful symbol completion requires one
counter increment; returned numeric zero is not a failure indicator. A first EOF
call with positive coordinate advancement is partial, with zero advancement is
empty; all later no-advance calls remain empty. A partial/empty call has no valid
source-backed dibit position even if the decoder returns a value.

With the fixed filter-off/generation path, before EOF the common frontier is
read_start+cache_pos; after a failed empty refill it is the finite input length.
Validate this against the enabled actual-pop trace. Frontier advancement is not
labeled an exact sample-pop count. Detailed observation off installs no sample
or CRC callback; do not disguise an always-on pop ledger as callback-off.

## Measurement gates and limits

Every enabled real-pop index must be unique, ordered, within the delivered input,
and have matching sample bytes. For in-frame20-SPS calls, completed calls require
the full real20-sample interval, partial calls1..19, and empty calls zero. Verify
the actual fixed-profile assumptions rather than ignoring mismatches. EOF and
symbol completion must agree. Never attribute a full frame from partial/empty
calls, even if a returned checkword happens to pass. Retain every actual proof,
historical return, audio-buffer change and final CRC as observed behavior.

Observer-on/off common state/body/per-call records must match. Both chunks must
match common outcomes and exact enabled sample traces. Compare the three anchor
waves with old raw events/traces after projecting only new event/field additions
and replacing invalid old EOF positions by explicitly unavailable new positions;
all original decoder decisions, bodies, CRC6/CRC12 results, counters and real pop
traces remain required equal. Preserve the original EOF-position discrepancies
as a known legacy-recorder failure, not a corrected old result.

The positive SCCH control must return the independent information and received
checkword; the deliberately wrong checkword must be observable as wrong.
Retained drop20 must expose its actual selected voice format and SCCH result,
and internal staging must be measurable rather than forbidden by recorder validity.
All wrapper calls must pair and settings must retain disabled hardware/output.

A pass establishes only this bounded observer's correctness and neutrality.
It does not prove improved recovery, valid voice, RF reception, phone behavior,
audio latency, modern-key recovery or whole-app speed. Product changes require
separate hypotheses, independent legitimate voice/control retention and later
complex-IQ/device tests.
