# Clear NXDN48 receiver routing: registered finite experiment

Commit this registration before creating the new waveform corpus, building its
recorder, or invoking any receiver case. Freeze product/source baseline
`289a82f8fd9c0495b64bf948fd45413bc63261c4`. Earlier matrices, failed candidates,
original inputs, release artifacts and user settings remain unchanged. This
stage observes the existing receiver; it does not implement a decoder policy.

## Hypotheses and source truth

H1: after the explicitly fixed acquisition primer, the real continuous receiver
routes every one of the 24 registered transmitted voice-word occurrences into
the real FEC decoder and, unchanged for clear traffic, into its synthesis API.
Require original frame/slot ownership, exact returned 49 bits, correct control
transitions and no duplicate, stolen, header or trailer word credit.

H2: detailed callbacks and provider chunk sizes do not change common receiver,
FEC, synthesis-input or call-state observations. The common wrappers remain
enabled in both modes; this tests detailed-callback neutrality, not equivalence
to an entirely uninstrumented program.

H3: an independently exposed single unconfirmed weak frame, a parity-rejected
source frame, and zero input cannot acquire valid voice credit or produce
unexpected voice/synthesis calls. Any such call fails the corresponding gate,
even when faithfully recorded. Treat actual deviations as measured
quality failures, never as a reason to modify the corpus or discard a case.

H4: a synthesis call must not consume a voice interval containing unavailable
samples at finite EOF. A complete early voice interval inside an incomplete
frame can have source-backed bits; it cannot certify the whole frame. Keep
H4 separate from clean retention and observation integrity. If the baseline
violates it, record the failure and do not substitute silence in the recorder.

Use the independently verified AIR v1 corpus without re-encoding clean frames:

| Item | SHA-256 |
|---|---|
| AIR input manifest | `17061018477b6451207758d6e0390b3ef623e88099f565bfc3416f1168127067` |
| Sole AIR result report | `867264df1b1f05eaa5db49d30e7287def90c3a32ebb3d9dcd47a0e2feb296f6f` |
| Primary raw48/air48 output | `bedb3ae824c357e68e8d2883b808b357e228e74c7ce253acf0a41cf257234c0b` |
| AIR publication index | `97b56f7d5ad4b4348b05daaa3915ebbcc926ff2a8c7bc40dc5220437fcb1016d` |
| AIR source/output archive | `08947807e6320512828a3cc988727c159175c25a56cd0a74fec38e3001766dd0` |
| Original announcement slice | `8f4116e67a4c950a524c8568caf17d550e9b0b0bbdac3f9e3761ce76c0056e41` |
| Earlier agreed voice channels | `05ed6f2d7c548e6b6e94e81bb12534afde0c2e13301791a8f1d4d2778dd6eed3` |

These twenty distinct 49-bit words supply 24 occurrences: source words 2, 3,
4 and 5 each occur twice. Reconstruct them from the first 98 bits of each
original 13-byte source pair. Identity is assigned by source position and slot,
never by matching decoded bits. Every control field retains AIR v1's RAN 1,
source 901, group 1201 and clear cipher. No key, key search or privacy operation
belongs to this experiment. The second SACCH cycle remains incomplete.

## Fixed waveform and execution matrix

The source frame IDs are AIR v1 IDs 0..8: header H, V0..V4, FACCH-first F1,
FACCH-second F2, and trailer T. Convert each of its immutable 48 air bytes to
192 dibits, MSB first. Use levels `(8000,24000,-8000,-24000)` at 20 samples per
dibit. Prefix 32 alternating dibits `(1,3)*16` (640 samples), append 1,280 samples
of level 8000, then apply one centered eight-sample average with endpoint
clamping: output i averages source indices `i-4` through `i+3`. Store little-
endian float32. This is a finite 48 kHz discriminator fixture, not complex I/Q
or an RF transmitter model.

| Configuration | Waveform/transform | Public fast option |
|---|---|---:|
| primed | H primer, then scored H,V0,V1,V2,V3,V4,F1,F2,T | 0 |
| cold_default | H,V0,V1,V2,V3,V4,F1,F2,T | 0 |
| cold_fast | Same exact cold bytes | 1 |
| single_weak | V0 alone | 1 |
| bad_lich | Primed sequence; flip only V0 full-frame bit 34 before shaping | 0 |
| zero | All-zero float samples, same length as primed | 0 |
| prefix_9999 | First 9,999 samples of the already shaped primed parent | 0 |
| prefix_10000 | First 10,000 samples of that same parent | 0 |
| prefix_10001 | First 10,001 samples of that same parent | 0 |

Bit 34 is the LICH parity bit; bit 35 is its unchanged spacer. Do not reshape
a prefix. In the primed sequence V0 starts at sample 8,320; slot 0 ends at the
nominal frontier 10,000. Use actual observed finite delivery to establish
ownership, not an assumption that nominal sample phase was reached.

There are eight distinct waveforms and nine option configurations. Each runs
with provider chunks 37 and 512 and detailed observation off/on, in a fresh
process: exactly **36 native invocations**, one per fixed identity. Native
timeout is 60 seconds per invocation. Continue through distinct registered
cases after a failed invocation, retaining it; never retry a native identity
or re-run older matrices for this study.

## Real receiver and bounded observation

Use the real engine live loop, synchronization, dispatch, NXDN framing/FEC,
no-carrier reset, vocoder, audio processing and an unstarted real radio context.
Private source copies may add observation hooks only. Hash-bind the established
observation-v2 recorder contract and source inputs; do not edit frozen historical
files. The rejected boundary veto and private first-sync prototype must not be
linked. Only the existing public fast option varies in the matrix.

Fixed profile: 48 kHz discriminator, 2,400 symbols/s, 20 samples/symbol,
filter off, datascope zero, NXDN48 only, one stream generation, scanner/trunking
off and no hardware start/tune or audio/file output. Do not inject confirmed
state, change keys/cipher, override decoder output, pad EOF, seed vocoder RNG
or synthesize substitute frames. PCM values are descriptive, not a neutrality
or original-speech truth gate. Preserve actual negative returns and flags.

GNU link wrappers forward original pointers once to the actual hard/soft
`mbe_decodeAmbe3600x2450Frame` / `mbe_decodeAmbe3600x2450SoftFrame` and
`mbe_processAmbe2450Dataf`. Verify object/archive symbol ownership, relocations,
link maps and runtime dependencies before execution. Record nested calls and
depth so a decoder's internal fallback cannot create a second routed word.
The normal source path supplies reliability and principally exercises soft FEC;
zero hard calls are valid. Do not force an artificial hard route.

Common observations in both modes include route begin/end, actual slot and
voice selector, real decode return plus 49 returned bits, actual 49 synthesis
input bits and valid statuses, input mutation checks and call-state snapshots.
Never read uninitialized predecode result fields or undefined outputs after a
negative return; emit unavailable/null. Read named fields only, never padding.
Keep caller state unchanged. Observe synthesis separately from decoding.

Detailed mode adds existing sample/CRC/LICH diagnostics and the real dewhitened
36 dibits and reliability per slot plus the actual 4x24 mbelib input matrix.
Independent matrix placement is generated arithmetically from channel position,
not copied from a decoder output. The unused 24 cells must remain zero. Preserve
the optional SCCH diagnostics if encountered but do not invent SCCH source truth.

At frame/control/route boundaries record a read-only, zero-initialized call
snapshot: present/absent, epoch, phase, protocol/kind, source/target/policy target,
crypto/algorithm/key ID, audio permission, media-active and end reason. Omit
wall-clock values from comparisons. A media-active flag precedes FEC in this
path, and successful staging or nonzero PCM cannot certify accepted speech.

## Attribution, control transitions and independent gates

Preserve each body call's before/after delivery frontier, EOF state and symbol
counter. A complete call has one real symbol commit and 20 real samples in this
fixed profile. Partial and empty EOF calls have unavailable source positions.
Detailed pop traces must partition actual delivery exactly, without using
provider refill coordinates as delivered samples.

All slot decodes occur after the body is read, so the current vocoder cursor
cannot identify a word. Use parent body-call intervals and actual slot 0..3,
with slot's body offsets `38+36*slot` through `73+36*slot`. Require unique
contiguous source ownership with every delivered end position strictly within
one symbol of its nominal source position (`-20 < deviation < 20`). Reject
ambiguous attribution. Require the canonical source LICH/location and exact
known transmitted/returned bits before granting source credit.

Scored pure-voice frames each route slots 0..3; F1 routes slots 2,3 only and F2
slots 0,1 only. Header/trailer contain no voice. The primer is explicitly
unscored acquisition input; the scored header must actually be dispatched and
strongly proven. Failure to expose it fails the primary gate, without extending
the sequence or picking a later favorable repetition. Cold cases report all
observed losses/nonexposure descriptively; they do not inherit an all-24 claim.
Every source-owned word that is routed must still match its unique occurrence.

Independently validate actual SACCH CRC6/FACCH CRC12 information and checkwords.
Final CRC callbacks precede confirmation updates; test subsequent route/frame
state rather than demanding updated confirmation inside that callback itself.
Header SACCH carries RAN 1, but live last-RAN may retain its initial value until
the next valid SACCH processed after confirmation: SACCH precedes the header's
strong FACCH. Do not impose premature live-RAN equality. Require source/group
and clear call classification from real VCALL publication, and live RAN 1 at
that next eligible confirmed SACCH. Identical repeated FACCH halves are
duplicate-suppressed for element routing; two CRC passes do not mean two calls.
Require real trailer termination of the known epoch with TERMINATOR; sticky
confirmation need not reset there. Actual no-carrier reset is a separate event.

Freeze a strict event schema and independently test its checker before the
sole matrix. Required evidence counterexamples include wrong source identity
with equal repeated bits, swapped/stolen/duplicate/missing slots, changed
synthesis input after correct FEC, negative decode with nonzero staged PCM,
ERASURE/REPEAT/MUTE flags credited as speech, unavailable EOF intervals credited
as source, forged CRC proof, unconfirmed voice, reordered events and missing or
mismatched observer/chunk cases. These check the evidence gates, not RF behavior.

Report measurement integrity, H1 clean routing, H3 negative restrictions and
H4 finite voice safety separately. Aggregate progression requires all four and
H2 neutrality, with complete registered identities and preserved source/input/
binary/earlier-artifact hashes. A faithfully measured receiver failure can pass
measurement but must fail the applicable quality gate. Do not relax a gate
after seeing an outcome. Product promotion remains false even if every gate
passes: actual hardware, independent impaired complex I/Q, speech intelligibility
and application-level acceptance remain separate work.
