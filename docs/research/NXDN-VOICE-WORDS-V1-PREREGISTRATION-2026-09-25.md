# Independent NXDN clear voice words: registered first stage

Register before corpus generation, primary-encoder execution or production
decoder probing. Preserve receiver baseline `e8498d298ad1a6f85da93a8b07730ec99f7c1416`,
all prior experiments and released APK/Windows artifacts. This stage builds
measurement foundations; no product behavior or default is changed.

## Hypothesis and limited claim

H1: a separately written arithmetic encoder agrees exactly with a pinned external
NXDN voice channel encoder, and XeraX's actual 72-bit mapping plus production
hard/soft FEC decoding preserves those independently known 49-bit source words.
Single errors in protected A/B fields should preserve the source word. A changed
unprotected C bit must instead appear as the corresponding changed source bit;
silence, nonzero PCM or an error counter cannot prove the original word correct.
Any disagreement fails the applicable stage. Do not tune inputs to decoder output.

This is a clear channel-word test, not voice synthesis, frame acquisition,
control-message processing, RF sensitivity, throughput or encryption recovery.
It does not fix the retained malformed-header audio episode. Full call/air-frame
construction and bounded-history receiver experiments need separate registration
after this foundation passes. The rejected boundary veto remains rejected.

## Primary sources and fixed corpus

Use untouched `NXDNAudio.cpp` and `Golay24128.cpp` from MMDVM-Host commit
`590c531391dfd3146073afbc3956f70d42c62a46`, with required headers and original
notices. Preserve fetched bytes, Git blob identities and SHA-256 hashes before
building. Supply the unused decoder's required population-count utility with its
exact pinned upstream implementation; do not introduce a fake decoder. No XeraX
decoder output, code or lookup table may construct the expected channel words.

The independent Python encoder uses polynomial Golay arithmetic, a generated
A-dependent mask and arithmetic bit placement, with no copied large lookup
tables. Sources share protocol knowledge, so agreement is cross-implementation
evidence, not formal standards certification. No primary decoder is an oracle.

Preserve NXDNClients commit `8950677e9876e577fb87b955cfa93bacd059209d` source,
English index and asset. The `linked` slice is exactly 130 bytes at `[8476:8606]`
of `NXDNGateway/Audio/en_GB.nxdn`, SHA-256
`8f4116e67a4c950a524c8568caf17d550e9b0b0bbdac3f9e3761ce76c0056e41`.
Each consecutive 13-byte unit supplies two MSB-first 49-bit words at offsets
0 and 49. Also extract the two words in that source's declared `SILENCE` unit.
Preserve original padding bits in provenance; normalized encoder input uses
zero padding. Do not infer original PCM or human intelligibility from these bits.

Order the logical word corpus exactly as follows, retaining duplicate values:

1. IDs 0–19: the twenty announcement words, in original order.
2. IDs 20–21: both upstream silence words, in original order.
3. ID 22: all zero; ID 23: all one.
4. IDs 24–72: each of the 49 one-hot source bits, in ascending bit-index order.
5. IDs 73–4168: all 4,096 A values in ascending order, B and C zero.
6. IDs 4169–8264: all 4,096 B values in ascending order, A and C zero.
7. ID 8265: zero padding word to complete the paired external encoder API.

Total: 8,266 words, in 4,133 packed 13-byte input records. The external encoder
must emit exactly 4,133 18-byte records (two 9-byte/72-bit channel words each).
Freeze the source word list, packed input, independently encoded expected bytes,
case metadata, preparer/checker source and native build identities before
executing the external encoder once. Compare every output byte, including the
final padding word. Preserve a failed attempt; do not regenerate a favorable set.

## Native production probe

Only after encoder agreement passes, freeze that output as the probe input.
Use the existing production `dsd_ambe_2450_dibit_map` to populate a 4×24 frame
and call the real linked `mbe_decodeAmbe3600x2450Frame` and
`mbe_decodeAmbe3600x2450SoftFrame`. Soft reliability is fixed at 255 for every
transmitted bit. The exact source/map/library/header/compiler identities and
link map must be retained. Synthesis, playback, key search and radio I/O are
absent from this probe. Do not substitute decoder or FEC stubs.

Execute one fixed batch, with clean and mutated cases in this order:

* All 8,266 clean words, each in hard then soft mode.
* For each base word ID 0–72, independently flip each of its 72 transmitted
  bit positions 0–71, each in hard then soft mode. Every mutation starts from
  the frozen clean word; errors are not accumulated.

This gives `(8266 + 73×72)×2 = 27,044` decoder calls. Record a row for each call:
source ID, mutation position or clean marker, hard/soft identity, actual mutated
input bytes, returned 49 bits, return status and available error/flag fields.
Check input arrays remain unchanged across each const-input decoding call.

The 24 A and 23 B channel positions are protected: require the original source
word for all those single-bit mutations. The 25 C positions are unprotected:
require exactly the corresponding source bit 24–48 to change, rather than
mistaking an apparently successful decoder return for original content. All
clean cases must match the source word. Require a nonnegative decode return for
these valid binary inputs, but record counters rather than inventing a universal
error-count rule. Test the result checker with missing, duplicate, reordered,
altered-input, wrong-output and mislabeled protected/unprotected controls before
native execution. Assertions must remain active with Python optimization.

## Gates, preservation and follow-up

All expected identities and counts must be present exactly once. Every input,
source, linked library and historical release/artifact hash must be unchanged
after execution. Source/layout/checker defects found before execution may be
corrected with retained preflight evidence; no post-outcome threshold changes,
case deletion or native retry for a favorable result. A failing stage remains
published as a failure and blocks claims based on the later stage.

Full air frames are deliberately deferred: static source review found that the
pinned FACCH1 encoder can index beyond its puncture list at the tail, and LICH/
SACCH storage needs explicit initialization before setters. A later external
air-frame oracle must register a minimal bounds guard and deterministic setup,
preserve the original sources and corroborate complete frame bytes independently.
Those deferred changes are not needed or applied in this voice-only encoder.

A pass supplies known source/channel words for future real clear-call retention
tests. It is not an APK/EXE improvement, standards conformance certificate, speech
quality result, timing result, receiver acceptance or a cryptographic claim.
