# NXDN missing-input guard: measured candidate result

The isolated candidate prevents processing unavailable NXDN voice slots in the
registered finite-input cases while retaining fully received words. All **20 new
Windows receiver processes** exit zero. Measurement, explicit availability,
source-bit routing, complete-input baseline agreement and preservation pass.
The targeted guard passes; aggregate progression and product promotion remain
false because the separate post-rejection recovery defect is unchanged.

This implements the [input-availability design](NXDN-INPUT-AVAILABILITY-DESIGN-2026-09-25.md)
under the [fixed preregistration](NXDN-AVAILABILITY-V1-PREREGISTRATION-2026-09-25.md).
Registration commit is `76e175aef1b8f30431c07cb3d4a50d431b858c02`; candidate,
observer, independent checker and runner were committed at
`0551423572dc056b6e8d6f10f114e7a77bece193` before any receiver invocation.
Input samples were copied byte for byte. Previous receiver binaries and matrices
were neither rebuilt nor rerun; comparisons use archived baseline observations.

## What changed

Private checked symbol/dibit APIs report whether a read actually supplied a
symbol. A local 182-entry map records availability through the NXDN frame.
LICH and control blocks require complete input before interpretation. Each voice
slot needs all 36 dibits before FEC, media activation or audio copying. A complete
early slot remains usable when a later read reaches EOF. Existing public APIs
and successful replay paths remain available; no synchronization policy,
convolutional decoder, vocoder algorithm or key operation was changed.

The candidate lives entirely under `experiments/nxdn_availability_v1`. Seven
private source/header changes, original Git identities and full normalized diffs
are retained. Checked-reader and masked-voice seams were observed directly;
the executable links the actual production soft FEC and synthesis functions.
Dedicated unit tests using spies are separate from this real receiver executable.

## Measured before and after

These are per-invocation counts, identical at chunk sizes 37 and 512 and with
detailed observation disabled/enabled. Every row has four candidate invocations.
The source is clear conventional NXDN48 discriminator data at 48 kHz, not RF or
independently impaired complex I/Q. Playback is disabled.

| Input | Cached baseline FEC/synthesis | Candidate FEC/synthesis | Candidate exact source occurrences |
|---|---:|---:|---:|
| Active prefix, 6,159 samples | 4 / 4 | **0 / 0** | 0 complete words available |
| Active prefix, 6,160 samples | 4 / 4 | **1 / 1** | 1 / 1 complete early word |
| Active prefix, 6,161 samples | 4 / 4 | **1 / 1** | 1 / 1 complete early word |
| Exposed bad LICH followed by clean traffic | 12 / 12 | 12 / 12 | **12 / 20 expected later words** |
| Full cold clean sequence | 24 / 24 | 24 / 24 | 24 / 24 |

Across the three prefixes, the guard removes all **40 previously observed
unavailable-slot synthesis calls**. It preserves the eight fully received early
word occurrences across those invocations. The zero-complete-word frame no
longer marks media active or advances its audio indices. Complete earlier SACCH
input stays eligible even when subsequent voice input is unavailable.

Across all 20 candidate processes, every one of the **152 real soft-FEC and
synthesis-input occurrences** matches its known 49-bit source word. No unavailable
slot enters either operation. There are 144 synthesis results with flags 0x03
and eight with 0x23 (ERASURE on source word 19); none uses REPEAT or MUTE.
Exact source bits and FEC status do not establish intelligible speech.

The clean sequence retains the known clear header/call epoch, five pure voice
frames, both FACCH half-steal layouts and the actual trailer. Common measured
complete-input outcomes match their cached baselines after removing the three
additive availability telemetry fields and the frozen checker's descriptive
observation fields. This includes source delivery, bits, control
metadata and call state, not merely equal totals. Common outcomes and sample-pop
traces agree between both chunk sizes and observation modes.
Optional PCM content is excluded from these comparisons; equal output waveforms
or listening quality are not established.

The bad LICH is still actually exposed and rejected without target voice or
fresh evidence. Recovery still loses V1/V2 and eight later clean words before
resuming correctly. Its 12-word result is a preserved failure, not a successful
recovery claim. This guard makes no synchronization-policy change.

## Validation and reproducibility

All **eight local Windows native unit contracts** pass in Release with their
assertions active. They cover finite input at SPS10/20; binary, soft-binary and
float replay; invalid/short records and replay loops; radio/no-radio acquisition;
actual datascope resets; control-range completeness; and 256 combinations of
voice availability masks, selectors and hard/soft paths. Unit spies establish
call boundaries and unchanged state, not speech quality.

All **44 Python framework tests** pass normally and under optimization locally
and in Windows/Linux CI. The same CI workflow also builds and runs exactly eight
native contracts on Linux in Release and with ASan/UBSan, with explicit JUnit
name/count verification. All four jobs pass on both
[push](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36203868209) and
[PR](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36203871241). CI never
executes the 20-case receiver matrix or historical receiver cases.

The independent build audit passes 520 checks, including configured source and
header identities, reversible observation, actual object/archive ownership,
resolved checked-reader/masked-voice/FEC/synthesis calls, distinct radio/no-radio
objects and four runtime DLLs. Build, link, auditor and descriptive-summary
preflight failures remain archived with their corrections. No receiver identity
was retried. The evidence validator binds native pass claims to all eight actual
saved JUnit cases and retains failed preflight auditor versions.

Preservation covers 365 frozen files, 2,338 original identities, 365 copied
identities, 485 audited dependency paths and 1,979 protected historical identities.
These groups overlap. All 486 report-listed files remain unchanged. The earlier
failed primer, off-phase recovery and malformed-header PCM evidence is preserved.

The [publication index](evidence/nxdn-availability-v1-2026-09-25.json) and
[raw evidence archive](evidence/nxdn-availability-v1-2026-09-25-raw.zip) contain
every attempt, copied baseline, actual events/pop traces, frozen checker/source,
research executable/runtime files, preflight failures and completed CI artifacts.
The archive supports offline reproduction of the saved checker decisions without
any native receiver execution. A separate results audit checks raw observations
and source ownership without importing the frozen experiment checker. Its
98,559 checks find no discrepancy, including all 78 actually observed CRCs,
complete source support for their input ranges and detailed channel/reliability
mapping. That auditor authored the acquisition helpers; this is independence
from the checker and output-derived truth, not from candidate authorship.

| Identity | SHA-256 |
|---|---|
| Copied input manifest | `d42a311b1367b0a200dd3c52ab0aaa3bfd292a429785a9ac534ee54348dad98c` |
| Candidate research executable | `788c655cf616ea53804f8bd70d174e42b7038a173f8a0aaf514fc2ccb47f599d` |
| Native report | `dc6e7ad0f363db329108d29b02c990fbbdd774bd5e26b339f31b8d85c7c8a14c` |

## Remaining integration gates

This first guard candidate is **not included in the released APK or Windows app**.
Register bounded preservation tests against the prior off-phase and malformed-
header controls before integrating it. Keep the independent bad-LICH recovery
work separate so improvements and regressions remain attributable. Then build
Android/Windows integration candidates through the normal product regression
and package-verification checks, preserving user settings and RC3 artifacts.

The checked API still inherits input-adapter contracts. Pulse and headful WAV
fallback behavior needs separate correction and tests; the current result does
not certify every backend. Encrypted missing-slot history is not covered by
these clear-input tests. Physical receivers/phones, playback, human listening,
independently impaired complex I/Q and broader protocol/hardware acceptance
remain pending. No CPU/GPU speedup, RF sensitivity or cryptographic claim follows.
