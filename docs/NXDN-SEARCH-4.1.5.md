# XeraX SDR 4.1.5: experimental NXDN scrambler recovery

This release adds actual inference of an unknown **15-bit NXDN voice scrambler seed**, beyond selecting a supplied key. It is an experimental receive feature, switched off by default. It does not recover NXDN DES/AES keys, DMR privacy keys or P25 keys.

## Using it

Start the main receiver in NXDN48 or NXDN96 mode. Open **Receiver tools → Receivers, I/Q lab and scanning → Reception → Start NXDN search**. The Spanish interface calls this **Iniciar búsqueda NXDN**.

The receiver must decode confirmed cipher-1 signaling and valid superframe positions. The display distinguishes waiting, searching, an initial candidate, and a candidate being used. Verify intelligible speech. **Discard candidate and search again** clears the result immediately. Stopping the search immediately prevents its candidate from authorizing audio.

Supplied keys take priority. Search applies only to the main decoder, is not automatically enabled in worker processes, and does not save recovered candidates to key profiles. A new call identity, frequency, source, target, RAN, key ID, format or search generation discards the previous result. DES/AES and unconfirmed classifications do not enter the search. Non-superframe and DCR-specific layouts are not supported by this search implementation.

## Evidence and limits

The solver uses the four high bits of the AMBE pitch parameter. Over a sufficiently stable section of speech, these bits can remain constant even though their actual value is unknown. It solves 32 binary equations for 15 seed bits and four unknown pitch bits using eight distinct frame positions. Inconsistent systems, repeated positions and rank-deficient systems are rejected. A second, non-overlapping eight-frame window must independently produce the same seed within 200 accepted voice frames. The two windows can have different pitch values.

This is statistical inference, **not authentication or proof of intelligible speech**. Random-payload tests do not establish a real-world false-positive rate. Calls may end before two suitable patterns occur. Changing speech, radio errors, missing signaling and incompatible framing may leave the receiver searching indefinitely. No automatic acquisition-time guarantee is made. Stable synthetic test sequences can supply the required 16 voice frames quickly; that is not a measured phone or RF result.

Recovery runs after AMBE channel error correction and before voice synthesis. The channel FEC is not used as proof of a correct scrambler seed: it protects the scrambled payload. The descrambler uses each verified superframe position rather than assuming that every previous frame arrived. A recovered value affects only the current payload path; existing supplied-key material is never overwritten. Vocoder prediction state is reset when the candidate first becomes usable.

## Verification

- Exhaustive independent recurrence tests cover 0–32767 in both full and half-duplex frame-position layouts: 65,536 seed/layout cases. Tests compare recovered plaintext bit for bit, not just a success flag.
- 500,000 deterministic random frames must produce no accepted candidate. Constant clear pitch may identify seed zero, but must never identify a nonzero value. Repeated frame offsets cannot qualify as independent evidence.
- Thirteen call, cipher, key, format and quality boundary cases verify stale results cannot open audio. Disable/re-enable is separately checked.
- A native test exercises actual AMBE FEC, the production recovery hook, exact payload recovery and nonzero finite PCM from MBElib. Its ciphertext is generated from known plaintext, so this is a controlled software test, not a scrambled-radio recording.
- A separate replay applies 64 known synthetic scrambler values to real AMBE speech parameters extracted from the existing public IQ fixtures. NXDN48 recovered all 64 values and exact plaintext, first accepting at observation 31. The short NXDN96 extract recovered **0 of 64**: it did not provide two qualifying windows. Neither sample produced an accepted wrong value. This exposes a real acquisition limitation and must not be summarized as universal NXDN48/96 success. The ciphertext in this test is synthetic, not a scrambled off-air capture.
- Both Android ABIs, bilingual controls and existing receiver regressions are checked during release packaging. Physical phone audio, thermal behavior and reception of a known-key scrambled radio remain unverified.

## Research sources and decisions

- [AOR AR-DV1 addendum](https://www.aorusa.com/support/manuals/AR-DV1_manual_addendum.pdf) documents automatic 15-bit descrambling and reports 1–2 seconds in good conditions. This establishes a commercial capability, not XeraX performance or AOR's algorithm.
- [PROCITEC go2SIGNALS 19.2 release notes](https://procitec.com/file_access/5216/1918/6523/go2SIGNALS_ReleaseNews_19.2_web.pdf) list automatic NXDN scrambler-key recovery. No proprietary code was used.
- [GopherTrunk cryptolab](https://gophertrunk.org/cryptolab.html) provides a generic 15-bit sweep with CRC or known-plaintext checks. Its voice oracle is described as future work in the examined source; its generic CRC path is not a drop-in oracle for NXDN voice. No GopherTrunk implementation was copied.
- [MBElib AMBE parameter decoder](https://github.com/arancormonk/mbelib-neo/blob/main/src/ambe/ambe3600x2450.c) identifies the AMBE pitch bit positions. Reserved silence values alone were insufficient in the public samples, so the implementation does not require them.
- [Pinned DSD-neo source](https://github.com/arancormonk/dsd-neo/tree/8c9c120389401fc2db3ef52869e13d555712e5fb) supplies the actual NXDN frame, FEC, scrambler and vocoder paths used by XeraX. Its supplied-key path remains available.

The next acceptance test needs a recording from a test radio with its scrambler value known to the tester: search without supplying that value, compare the detected value, and compare decoded speech against the supplied-key baseline. Test several radios, both rates, late entry, short calls, noise and frequency error before describing the feature as reliable or measuring its recovery time.
