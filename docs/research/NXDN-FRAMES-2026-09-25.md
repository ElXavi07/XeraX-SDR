# NXDN48 complete control-frame baseline

The real NXDN channel decoder recovers the independently encoded control data in
all 120 positive cases. With the repaired schema 2 recorder, all 156 paired cases
pass measurement integrity and the declared receiver-quality gates. This is a
controlled component qualification, not a new app performance improvement.

The baseline code is 0eb809538aa8e964fc8d0776e07579a832e112c6. Only private test
hooks and an isolated harness are added. Existing APK/EXE releases, settings and
receiver defaults are unchanged.

## Independent inputs and fixed protocol scope

The [preregistration](NXDN-FRAMES-PREREGISTRATION-2026-09-25.md) fixes 120 positive
cases (two boxcar shapes, 20 sample offsets, three read sizes),36 negative/history
controls, and three direct channel-block controls. The source is a finite
48 kHz discriminator stream containing four NXDN48 RDCH/non-superframe SACCH plus
two FACCH1 IDLE blocks per frame. Original complex IQ, RF noise and audio are not
in this experiment.

The independent Python encoder supplies the full 20-bit FSW 0xCDF59, LICH 0x41,
RAN 23, CRC6=0x12 and CRC12=0x830. Channel CRC, K5 convolutional encoding,
puncturing, interleaving and PN95 whitening agree with pinned
[MMDVM-Host source](https://github.com/g4klx/MMDVMHost/tree/590c531391dfd3146073afbc3956f70d42c62a46).
Eight compiled-oracle fields match. The reference FACCH encoder has a terminal
puncture-list overread in this pinned revision; the audit uses an explicitly
saved192 sentinel adjustment and retains the original source and patch. This is
corroboration, not a standards certificate or a comparison against MMDVM decoding.

Wrong-CRC controls change check bits before channel encoding, preserving valid
FEC and original information bits. Wrong-LICH controls retain valid encoded
channel bodies. The sign-only matching oracle preserves payload sync-like
windows; vectors were not selected to avoid acquisition ambiguities.

## Measured Windows results

| Scenario | Cases | Fully verified true frames | Final channel checks | Fresh false proof |
|---|---:|---:|---|---:|
| Valid four-frame bursts | 120 | 360 | 1,080 pass | 0 |
| Deliberately wrong CRCs | 6 | 0 | 54 fail, 54 real hard fallbacks | 0 |
| Deliberately wrong LICH | 6 | 0 | No channel CRC events | 0 |
| Valid then invalid history | 6 | 6 | 18 pass, 18 fail | 0 |
| One sync word then constant data | 6 | 0 | No frame-handler calls | 0 |
| Zero discriminator input | 6 | 0 | No frame-handler calls | 0 |
| Fixed random nonprotocol symbols | 6 | 0 | 12 inverted-sync LICH rejections, no channel checks | 0 |

All positive cases recover source frames 1, 2, 3 (zero-based), not frame0. All direct
block controls return exact original information and expected checks, including
the valid channel bodies inside the wrong-LICH vector. Direct controls bypass
acquisition and cannot count as cold receiver successes.

The mixed sequence separates sticky historical confirmation from current proof:
invalid source frames 2/3 return historical result 1 without fresh evidence.
Callbacks record both FACCH checks before duplicate suppression, and report the
final decision after the real hard fallback. There are no truncated frame-body
completions in this run. Neither recorded counted voice nor other NXDN side-effect
requests occur. This does not establish that all inherited uncounted DSP sinks
were uncalled.

The full matrix records 150 off-boundary sync-handler invocations. These are
rejected; none creates channel proof. A sync match alone is therefore not a
decoded frame. The early positive accept near source sample 1700 matches a
tolerated sign pattern in the payload, rather than the independently identified
exact positive pattern at frame dibit170. The matcher admits five sign patterns
per polarity; an exact-pattern oracle is insufficient to enumerate its accepts.

## Timing landmarks and remaining acquisition opportunity

Measured timing uses successfully delivered discriminator samples, excluding
unconsumed provider read-ahead. For correctly validated frames:

- Sync is accepted 197â€“203samples after that frame's nominal FSW start.
- Final CRC availability is 3837â€“3843samples after that same start,
  or 79.9375â€“80.0625ms at48 kHz.
- Sync acceptance to final CRC availability is3,640 samples,75.8333 ms.
- From the first nominal FSW start to the **first correctly verified frame**, the
  interval is7677â€“7683samples,159.9375â€“160.0625ms. It is source frame 1.

These are signal-availability intervals, not processor execution times or
whole-app latency. CRC callbacks run after the complete body has been read; the
earlier SACCH location cannot be reported as earlier execution. The frozen
uncoded experiment's roughly 84 ms first-sync time measures a different input and
endpoint; do not treat the new 160 ms figure as a regression or speed comparison.

The next bounded candidate is provisional acceptance of the first canonical
FSW followed by real LICH and channel validation. Its hypothesis is earlier
first-frame recovery without more false proof, not an assumed speedup. Keep
original calibration, fixed vectors and negative controls; add burst entry,
missing sync, symbol-slip and engine-integration tests before promotion. Cadence
anchoring and bounded calibration rollback are separate alternatives, not
changes to combine until individual effects are measured.

## Failed first recorder and reproducibility

The first schema 1 run is preserved. Its positive/control observations are useful,
but six random cases aborted at sample 2680 when the recorder rejected an
unsupported sync value without recording it. All 45 input files and the first
binary were snapshotted and hash-verified before repairs. This was a failed
measurement, not a successful full-matrix result.

The preregistered amendment introduces schema 2 support for NXDN 28 and 29. The
corrected run records 29 at sample 2680, then another 29 at 15820 in the random
controls, both rejected by the real handler. This supports the original causal
explanation but does not retroactively insert an unrecorded value into schema 1.
The waveforms, seed, receiver code and success thresholds remain unchanged.
All 150 nonrandom rows and traces match the first run apart from the schema
number. All 52 scenario/shape/offset groups also match across the three buffer
sizes after excluding only provider/cache read-ahead fields.

The [portable runner and schema](../../experiments/nxdn_frames/README.md) freeze
sources, executable and generated files; retain raw JSONL, every delivered-sample
index, native failures and validation reports; and refuse overwritten output
directories. CI distinguishes measurement validity from receiver success. A
future validly measured receiver failure must remain visible even when the
measurement job is green.

Windows builds link the real symbol/sync/dibit, LICH, PN95, channel decoding,
soft convolution, hard fallback, CRC and confirmation implementations. Ordinary
NXDN and DSP archives export no private observer hooks. Initial missing-link and
duplicate-fixture-definition failures are retained. The latter was resolved in
the local wrapper, leaving shared sources and real `dsd_misc.c` unchanged.

Implementation `f1f43b1d2304b01eb1b9f1fe38713bf09de0745f` passes Linux Clang release
and ASan/UBSan in both [push CI](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36141207956)
and [PR CI](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36141211621).
All 39 checks pass; Macroscope is cost-limit-skipped, not review-approved. Each
Linux job passes 66 Python tests normally and under `-O`, the native matrix and
the original symbol-phase regression. Windows passes the same 66 Python methods
and existing phase regression. These sanitizer checks exercise the component
study, not every application path.

Independent reanalysis of all five retained matrices confirms identical parsed
rows and all 156 sample traces across Windows and four Linux jobs. Raw JSONL
differs only by line endings. All 40 declared source hashes and every stored
output binding verify. The four CI executable hashes are recorded but could not
be independently rehashed because those binaries were not included in the
downloaded CI artifacts. The local Windows binary is rehashed.

The [machine-readable evidence](evidence/nxdn-frames-2026-09-25.json) links the
[raw archive](evidence/nxdn-frames-2026-09-25-raw.zip): 1,233 entries, 24,473,801
bytes, SHA-256 `65bab2562c9627e71ffc9debcb55014bdf853f39745fbfa45e2077eb11fb6eb7`.
Every entry was reopened and byte-verified. It contains both Windows runs,
original input snapshots, primary reference source/oracle, schema2 source,
research binaries, linkage audits, four Linux matrices, failed build logs and
the next conditional hypotheses. Four prior raw research archives, the original
uncoded acquisition executable and the pre-existing receiver lab binary rehash
unchanged. No Android build or physical receiver test is implied.

## Limits

The harness invokes `nxdn_frame` directly, bypassing full engine dispatch and
profile-proof feedback. It uses one fixed NXDN48 profile. Semantic content,
voice/vocoding, file output, alias updates, encryption/privacy processing and
some inherited DSP side effects are explicit sinks. Scope ends at validated
channel bits and captured semantic-dispatch input, not application behavior.

No NXDN96, voice, noisy-IQ, interference, fading, frequency drift, live hardware,
DMR/P25 acquisition, trunking, authenticated decryption or performance superiority
is established. A CRC pass is not key verification or authentication. Physical
phone/RF/listening acceptance remains pending.
