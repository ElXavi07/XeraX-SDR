# Complete NXDN control-frame qualification: fixed baseline screen

Registered before native decoder execution. Source baseline:
`0eb809538aa8e964fc8d0776e07579a832e112c6`. Preserved baseline archive SHA-256:
`f8973507faf9b9ef722e2175d815a49e7fe2fc31158ad3f734c56853d6b08702`.
The completed uncoded acquisition experiment, binaries and raw evidence remain
frozen. This is an extension in a separate experiment directory, not a change to
application defaults or a presumed acquisition optimization.

## Hypotheses and independent inputs

1. Independently encoded benign NXDN control channels survive the actual
   deinterleaving, depuncturing, convolutional decoding and final CRC checks.
   Deliberately wrong check bits encoded with otherwise valid channel coding
   produce failed final CRC checks, not fabricated valid traffic.
2. A finite complete control burst reaches at least one correctly validated
   frame through the real cold synchronization and frame-handler path for every
   declared positive case. A failed result is preserved, not fixed by selecting
   more convenient payloads or preloading synchronization history.
3. Test-only consumption and CRC observers do not change the captured ordinary
   decoder outcomes. Historical confirmation cannot count as current-frame proof.

The independent Python encoder fixes the full FSW 0xCDF59, LICH 0x41/full0x83,
RAN23 non-superframe SACCH, and two identical IDLE FACCH1 payloads. CRC6 is0x12
and CRC12 is0x830 for the fixed information fields. CRC, K5 encoding, puncturing,
interleaving and whitening are checked against pinned MMDVM-Host
`590c531391dfd3146073afbc3956f70d42c62a46`. Original reference files and an explicit
audit-only puncture-list sentinel fix are retained; no receiver output defines
expected data. The reference compile is corroboration, not a standards certificate.

Fixed numeric-dibit SHA-256:

- valid: `f9a9ddcf3005ff69815ac6edef66afbd9d2188bb17d327fcdb98c26f49d5c7ef`
- wrong checks: `14a140e5706e58ecd9b5d72ab96e6a5c1edbbc8f3f4072a019d0c5f174c6a7c9`
- wrong LICH: `94f5a65aea462e1a4b046a3b32b47b7c2cf0cc61d19967c22490c358e11243ed`

The independent sign-pattern oracle finds an extra positive sync-like window at
dibit170 in each frame, besides the true boundary at0. Preserve it. This is known
before native execution and may expose false synchronization; it is not grounds
to regenerate the payload.

## Fixed matrix

48,000 supplied discriminator samples/s,20samples/symbol, original level mapping
(+8000,+24000,-8000,-24000), centered boxcar widths8and14. Each vector has32
alternating outer preamble dibits, four192-dibit frames and32trailing positive
guard dibits:16,640samples. No cosine/matched filter or original-IQ frontend.

Positive matrix: all-valid frames,2shapes ×20starting offsets ×readchunks1,37,512
=120cases. Each pairs an observer-disabled run with an observer-enabled run.
Continue through the finite input with at most16accepted sync/frame invocations;
do not stop at the first convenient valid frame.

Six negative/control scenarios use both shapes,offset0and all three chunks:
36additional paired cases. Scenarios: all-wrong CRCs; all-wrong LICH; valid,valid,
wrong-CRC,wrong-LICH sequence in shared state; one true FSW followed by positive
constant guard; zero discriminator input; fixed xorshift32 nonprotocol dibits
(seed0x413288FB, shifts13/17/5, take top two bits). The latter replaces the entire
832-dibit stream. Enumerate its sign windows without tuning the seed. Record all
sync attempts, CRC outcomes and completed-frame return values, including failures.

Separate direct block controls feed the three frozen encoded channel sets through
the real channel decoder without synchronization. These isolate channel coding
from acquisition. They must not count toward cold-acquisition success.

## Observations and gates

Record sync return, cache/provider positions, consumed frontier, actual nxdn_frame
return, historical confirmation, content-dispatch observations, unexpected voice
requests, and final SACCH/FACCH CRC values/information bits. Record both FACCH
halves before duplicate suppression; record post-fallback verdicts. Store raw pop
indices. Observers only copy evidence and cannot alter decoder state.

Measurement contract: complete fixed matrix, bounded artifacts, strict domains,
in-range ordered sample deliveries, exact disabled/enabled common outcomes,
correct event-to-frame association, and exact direct-block control results.
Keep measurement correctness separate from receiver performance/quality gates.

Receiver gate: every positive case has at least one true-boundary completed frame
with all three correct CRCs and exact original information bits, and no false
current-frame proof. A true sync frontier must be within one symbol (±20samples)
of a known true FSW end. Negative frames must not create current-frame proof;
the valid frame in the mixed control is an intentional exception. Bad LICH must
not reuse a preceding frame's proof. Extra accepted syncs and off-boundary CRC
events remain visible. Report cross-chunk differences separately, never hide them
by averaging. A gate failure is a valid research outcome and forbids promotion.

Before native execution, source review added explicit EOF censoring: record
whether input ended during each frame body. Preserve any resulting decoder
output, but never count a truncated body as a fully supplied successful frame.
A current-proof return under truncation fails the receiver gate with that
specific qualification, not a fabricated RF false-positive rate.

All delays use generated landmarks in the **discriminator_samples** domain.
Channel CRC checks happen after the complete body is read; do not pretend the
earlier SACCH position means earlier execution. Original-IQ latency, authenticated
decryption, PCM timing, RF/noise performance and whole-app speed remain null.
Voice and semantic application routing are outside this no-voice control study;
any substituted side-effect sinks must be listed explicitly. Preserve failed
builds/results and publish measured limitations before selecting a candidate.

## Recorder amendment after the first native run, before the second

The first full156-case execution is retained at
`build/nxdn-frames-first-20260925`. All45 frozen inputs, including the original
schema1 observer, validator and binary, were copied and hash-verified before any
edits at `build/nxdn-frames-first-input-snapshot-20260925`.

The first recorder rejected any accepted sync other than positive28 before
recording its value. All six random controls stopped at supplied frontier2680,
with two infrastructure errors each and no EOF; the measurement gate therefore
failed. The original record does not prove which unsupported value was returned.
The actual matcher supports both positive28 and inverted29, making omission of
negative-polarity observations a harness defect, not an input-quality failure.

Schema2 records both polarities through the real frame handler; its native
diagnostic preserves any remaining unsupported value. Generated true-frame
evidence requires positive28 as well as the existing landmark, original bits
and checks. Negative29 can never establish truth for these positive vectors.
No waveform, seed, matrix, receiver implementation, EOF qualification or quality
threshold changes. Keep bounds32searches/16frames and run the full matrix once
after this repair. Compare all150 nonrandom cases with the first run to verify
unchanged observations. Preserve both results rather than replacing the failed
first run or treating this recorder repair as a decoder improvement.
