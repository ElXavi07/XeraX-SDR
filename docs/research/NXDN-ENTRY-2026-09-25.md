# NXDN48 entry recovery: benefit near intact frame boundaries

The optional RC2 policy passes the registered cold-entry component study. It
preserves every correctly decoded source frame recovered by the default policy.
Of 102 held-out positive cases, **24 recover their first valid frame 80 ms
earlier; the other 78 have no first-frame gain**. This is a bounded result near
intact sync boundaries, not uniformly faster mid-frame recovery.

## Fixed experiment and observations

Preregistration: `7249521`. Observer/policy implementation: `011d041`.
[Registered matrix and gates](NXDN-ENTRY-PREREGISTRATION-2026-09-25.md).
The study reuses the unchanged four-frame clear-control waveform and independent
vectors; only the absolute sample at which cold input delivery starts changes.
There are 20 positive entry positions, two waveform shapes and three delivery
chunk sizes, plus 36 unchanged negative/history controls and three direct-block
controls per executable. Both policies run once in Windows; Linux release and
ASan/UBSan CI reproduce the experiment independently.

| Held-out absolute entry samples | Cases | First valid-frame gain |
| --- | ---: | ---: |
| 640, 641, 4479, 4480 | 24 | 80 ms each |
| 719, 839, 840, 999, 1240, 1599, 1600, 2440, 2559, 2560, 3199, 3200, 4000 | 78 | 0 ms |

The first frame's sync starts at sample 640, and the second starts at 4480.
The table therefore supports a benefit when enough of an intact sync remains
available at entry. It does not establish a benefit when entry is already
inside most of the body. The three retained anchor offsets (0, 7, 19) are
excluded from the held-out gain count.

Across all 156 waveform cases, exact complete current-frame validations rise
from 354 to 402. This total includes the unchanged mixed-history controls and
the retained anchor cases; it is not 48 additional held-out successes. Neither
policy records a receiver-quality error. All 54 original anchor/control rows
and traces per policy match the frozen RC2 evidence, as do the direct blocks.
For the 354 source frames both policies recover, optional-policy completion is
unchanged or at most three samples (0.0625 ms) later, within the registered
one-symbol bound. Earlier availability of an added frame is a separate result.

## Costs and scope

The option performs additional work in these component inputs:

| Observation, all waveform cases | Default policy | Optional policy |
| --- | ---: | ---: |
| Frame-handler calls | 474 | 582 |
| Rejected frame-handler calls | 108 | 168 |
| Calls with historical confirmation only | 12 | 12 |
| Body samples consumed without current proof | 102,720 | 133,200 |
| Channel CRC checks | 1,134 | 1,296 |
| Hard-fallback checks | 72 | 90 |

These are event/work counts, not CPU time, power or whole-application throughput.
The option retains real LICH/FEC/CRC validation; a historical confirmation or
truncated source does not count as a successfully decoded current frame.

The supplied stream is a 48 kHz discriminator waveform with a known 2400/4
profile. It uses the same payloads and negative seeds as the preceding study.
Negative controls still start at offset zero. Full dispatcher/profile feedback,
real scanner visits, altered payloads, damaged sync, inserted/deleted samples,
RF noise, overlapping traffic, voice and physical receivers remain untested.

## Reproduction and next gates

The [Linux release and sanitizer run](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36154067403)
passes, as does its PR counterpart. The new 12 policy tests and 66 inherited
measurement tests pass normally and under Python optimization. Parsed rows and
sample traces match across Windows and Linux release/ASan/UBSan: 160 rows and
156 traces per executable. Reopening verifies 978 recorded output hashes.

An independent raw-data auditor recomputes all 2,430 waveform and 18 direct CRC
events without importing the encoder, inspector or comparison policy. It
reconstructs the fixed vectors, checks lineage and exact channel bits, verifies
the frozen anchors, and finds no discrepancies. The script and detailed audit
are included with the raw evidence.

No app binary, default or user setting changes in
this study. RC2 remains experimental and off by default. Passing this gate
permits the separately registered damaged-sync/slip and held-out-payload study;
it does not qualify default-on promotion or a claim of RF/audio superiority.

## Published evidence

The [machine-readable result](evidence/nxdn-entry-2026-09-25.json) records every
case, the gates, work counts, independent audit and unchanged release assets.
The [raw evidence archive](evidence/nxdn-entry-2026-09-25-raw.zip) contains
1,183 entries / 49,640,735 bytes, including all three measured pairs, the six
executed binaries, exact measured source inputs, policy tests, audit scripts,
CI records and logs. Every entry was reopened and checked before publication.
SHA-256: `c94baebae9444390a6b7f83286afd19aa35e38074e9b2b23917ca8165ebdc096`.

The failed initial CMake configuration and build diagnostics are retained;
configuration and prototype issues were repaired before any native measurement.
There was one Windows measurement pair, with no tuned or favorable native retry.
Full Windows cache files remain local with recorded hashes; the public archive
includes its binary manifest, toolchain and recorded build commands. The frozen
RC2 anchor archive is referenced by its existing release URL and verified hash,
not duplicated or replaced. All prior RC1/RC2 release assets remain unchanged.
