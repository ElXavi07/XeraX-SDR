# First canonical NXDN48 sync: bounded candidate A

Registered before either new native execution. Starting repository:
`ef39e4993c2467e40a4782ae4beae335fe72a5dd`. The previous schema2 baseline is frozen
in its published raw archive and a new 45-input snapshot. The source archive
SHA-256 is `c34a50815c22ed8ccfe7ed27aaa37d33bda36a18041acd2fab4f750c2a33a729`.
Baseline observer binary SHA-256:
`1f85bf616001a265537fde440b1e0c87d0c66c76ced835634e5bc369f0ffd2a8`.

## Hypothesis and sole receiver change

In the current positive four-frame test, every case first validates source frame1
about160ms after the first nominal FSW. Hypothesis: provisional acceptance of the
first **canonical positive ten-symbol sign pattern** can validate source frame0
at least70ms earlier, while preserving all previously recovered frames and all
negative rejection gates. This is not a full20-bit amplitude-sensitive matcher.

Only a separate private DSP archive defines both `DSD_NEO_TEST_HOOKS` and
`XERAX_FIRST_CANONICAL_NXDN48`. After the existing profile/suppression guards,
level blend and offset assignment, set the candidate sync as `lastsynctype` when
NXDN48 is enabled, actual profile is2400/4, state is not confirmed, polarity is
positive28 and the sign string is exactly3131331131. The existing acceptance
branch then performs its unchanged warm-start and real frame/LICH/FEC/CRC path.
Ordinary builds do not compile this branch or the candidate identity symbol.
Pre-run source review clarified that the shared profile helper treats symbol
files as profile-active without an actual waveform profile. Explicitly exclude
SYMBOL_BIN/FLT inputs from the candidate. This does not change any registered
matrix input; all use the supplied RTL discriminator waveform path.

No other tolerated patterns receive provisional acceptance. Inverted polarity,
NXDN96, shared P25/dPMR guards, calibration, FEC, CRC, confirmation criteria and
input handling stay as they are. Invalid preliminary candidates may consume
data or change calibration; count those costs rather than treating an extra
sync as useful work. Do not add rollback, cadence heuristics or another change
to rescue a failing result in this experiment.

[Pinned MMDVM-Host](https://github.com/g4klx/MMDVMHost/blob/590c531391dfd3146073afbc3956f70d42c62a46/NXDNControl.cpp#L141) validates LICH,
SACCH and FACCH in its control path, but relies on modem-supplied frames. It
supports treating a sync match as provisional, not a claim that this cold
sign-pattern acquisition policy is safe or equivalent to that implementation.

## Fixed execution and comparison

Reuse unchanged schema2 observer, independent vectors, inspector and runner from
`experiments/nxdn_frames`. The same120 positive and36 negative/control cases,
three direct controls, two waveform shapes, starting offsets, three chunks,
finite832-dibit stream, EOF censoring and search/frame bounds apply. No RF noise,
original IQ, new seeds or payload tuning are added to this first ablation.

Build fresh baseline and candidate executables in one separate build directory;
only the private candidate archive has the additional definition. Preserve
compiler/link commands, macro identity/archive checks and distinct binary hashes.
The runner cannot independently prove source-to-binary correspondence; that is a
separate linkage audit. Run each executable exactly once, baseline first. Stop
before candidate execution if fresh baseline measurement/receiver gates fail.
Do not retry a failed quality result with changed input or parameters.

The fresh baseline must match all156 previous baseline case rows and sample
traces and all three direct observations exactly. The candidate must preserve
measurement/receiver gates and independent direct blocks; all52 groups must
remain invariant across read sizes. Compare source-frame identities, not merely
total numbers of checks. All120 positive cases must keep correctly validated
source frames1/2/3 and gain a verified source frame0. Their first complete CRC
frontier must be more than70ms earlier in every paired case. Report all cases,
not an average that can hide a regression.

Wrong CRC, wrong LICH, one-FSW guard, zero, fixed random and mixed-history controls
cannot gain false current proof. Mixed source frames0/1 are valid and may prove;
2/3 may not. An accepted first sync in the one-FSW control is not itself a
failure; any current proof on its constant guard is. Source truncation remains
explicit and cannot count as success. Additional rejected frame calls/body
consumption and fallback counts are diagnostics, not CPU measurements.

## Interpretation and next gates

Report separate evidence validity and candidate-promotion gates. A valid negative
experiment is retained and published. A passing result only justifies the next
controlled study: entry mid-payload, missing/damaged sync, slips, independent
payloads/negative seeds and impaired IQ, followed by full-engine/mixed-protocol
and hardware regression. It does **not** promote this candidate into APK/EXE
defaults or establish original-IQ latency, whole-app speed or RF superiority.

The inherited semantic/voice/privacy/file/alias sinks, uncounted DSP substitutes,
and bypassed full dispatcher/profile feedback remain explicit. This is clear
control-frame work and neither tests nor recovers encryption keys. Preserve
existing settings, release artifacts and completed research archives.
