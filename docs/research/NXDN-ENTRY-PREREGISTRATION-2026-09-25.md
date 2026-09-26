# NXDN48 mid-frame entry: registered recovery sub-study

Registered before the new observer is built or run. Frozen application source:
`50a8b152066e2b8d40a371ddad44b951e5671ef5` (RC2). Published RC2 validation bundle:
49,453,396 bytes, SHA-256
`b46a6433dbf802bca231f70149c0d65d6c6884ac75a0b7ecd58ede7981dd4446`.
Keep every released APK/EXE and its default setting unchanged.

## Hypothesis and single new input dimension

The optional first-canonical-sync policy can improve cold acquisition after
entry partway through an ongoing clear control transmission, without losing
correct frames the default policy recovers. This sub-study changes only the
absolute position where input delivery starts. It does not simulate a warmed
receiver, lost frames in an ongoing decoder, RF noise, altered payloads, slips,
overlapping channels or original complex I/Q. Those remain separate gates.

Reuse the frozen encoder, its three vectors, four-frame streams, waveform
shapes, real frame/FEC/CRC path, side-effect sinks and observation functions.
The entire 16,640-sample waveform remains in its original coordinate system;
do not crop or rebase it. Positive entry offsets are exactly:

`0, 7, 19, 640, 641, 719, 839, 840, 999, 1240, 1599, 1600, 2440, 2559, 2560,
3199, 3200, 4000, 4479, 4480`.

These span the original preamble, first sync, control body and next frame
boundary. Use ramps 8 and 14 and chunks 1, 37 and 512: 120 positive cases.
Keep the previous 36 CRC/LICH/history/nonprotocol controls at their original
offset zero. Retain all three direct block controls. The total remains 156
waveform cases per executable; 102 positives use 17 held-out offsets.

## Observer and evidence contract

Add a separate observer that includes the unchanged frame observer with its
old main renamed. A small wrapper sets the public runtime option for each sync
call. Build default-off and option-on executables from identical sources and
the ordinary private test DSP archive. Do not use the research shortcut macro.
The `enabled` argument of the inherited `run_case` still controls observation
callbacks only: both inner runs use the same outer receiver policy.

Keep the inspector bytes frozen at SHA-256
`a26e47b64f09db1810d4d0dbb0c2c8d7e110b1abc248eecf0a634618ab514bc4`.
An explicitly recorded adapter replaces only its allowed MATRIX coordinates;
all existing exact-bit, independently recomputed CRC, nominal source-frame,
truncation, observation-transparency, event partition and sample lineage checks
remain intact. The 156-case invariants therefore remain valid. Do not reuse the
old first-sync promotion policy, which assumes every receiver starts in the
preamble and fixes the expected first source-frame identity.

Before native launch, preserve the observer/adapter/comparer bytes, recorded
source inputs and both binaries. Run default-off first, option-on second, once
each. Use the existing finite input/search/frame bounds and subprocess timeout.
No retry with changed parameters is allowed to rescue a negative result. Native
or evidence failures are reported separately from receiver-quality failures.

## Gates fixed before execution

1. Both runs must pass the unmodified inspector measurement and direct-block
   contracts. Each outer policy's observed/unobserved runs must agree.
2. All 18 positive anchor cases at offsets 0/7/19, all 36 original controls,
   their raw sample traces and all three direct blocks must match the frozen
   RC2 evidence exactly for their respective outer policy.
3. All 52 coordinate groups must remain invariant across chunks after removing
   provider cache positions; raw sample-pop traces must also match.
4. The option must preserve every exact, complete, currently validated source
   frame recovered by the default policy. Its corresponding end frontier may
   not be later by more than one symbol (20 samples). Report every difference.
5. The option must retain the inspector receiver-quality gate, including zero
   false current-frame proof, no truncated-source success, no unexpected voice
   dispatch and no exact channel corruption. Old confirmation is not new proof.
6. For at least one held-out entry offset, all six ramp/chunk cases must gain
   at least 3,360 samples (70 ms) in first complete valid-frame availability.
   Improvement in the three anchor offsets alone does not pass this gate.

Report total frames, source identities, first-frame frontiers and all extra
invalid frame calls/body consumption/fallback checks. Report failures and
censored outcomes, not only average latency. Sample time is at 48 kHz in the
supplied discriminator stream; it is not CPU time or audio latency.

Passing qualifies a subsequent damaged-sync/slip and held-out-payload study.
It does not justify enabling the option by default. Physical phone, RF and
listening acceptance remain pending. This is clear control traffic; no
encryption-key recovery is involved.
