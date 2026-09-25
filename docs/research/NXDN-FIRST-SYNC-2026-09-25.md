# Earlier NXDN48 frame validation: isolated candidate A

In the registered Windows component experiment, the candidate recovers the
opening control frame in all 120 positive cases while keeping every later frame
recovered by the frozen baseline. The first complete, correctly decoded frame
becomes available 79.9375–80.0625 ms earlier. The 36 negative/history controls
gain no false current-frame proof. This qualifies the candidate for the next
experiment; it does not qualify a change to the APK or EXE defaults.

## What changed and how it was isolated

Implementation commit: `b4e2455bf1e2fbca51e342f35250e149abc8cfa4`.
Frozen starting commit: `ef39e4993c2467e40a4782ae4beae335fe72a5dd`.
The [preregistration](NXDN-FIRST-SYNC-PREREGISTRATION-2026-09-25.md) fixes the
single change, input matrix, comparison gates and limits before execution.

For an unconfirmed NXDN48 waveform on the actual 2400-symbol/s, four-level
profile, the candidate provisionally accepts the first canonical positive
ten-symbol sign pattern. The existing warm-start, real LICH, convolutional
decoder, fallback and CRC checks then determine whether the frame is valid.
The sign pattern is not a full 20-bit amplitude-sensitive sync matcher.
Inverted polarity, NXDN96 and raw symbol-file input receive no such shortcut.

The change requires two private test definitions and is compiled into a separate
DSP archive. Ordinary builds and the comparison baseline omit it. The observer,
independent encoder, vectors, frame decoder and schema2 inspector are unchanged.
The frozen baseline's 45 inputs were copied and verified before editing.

Before native execution, independent source/build review found and corrected
two setup issues: the shared profile helper also accepts raw symbol modes, and
the cloned target needed the baseline's language standards and directory
definitions. Final Windows review matches 28 DSP and six observer source pairs,
including SIMD flags, with only the intended candidate definition different.
The first failed CMake configuration and preliminary audits are retained. No
native quality result was retried with changed parameters or input.

## Registered Windows pair

Both real native executables ran once, baseline first. The fresh baseline
reproduces all 160 parsed rows, 156 pop traces and four vector files from the
previous [complete-frame baseline](NXDN-FRAMES-2026-09-25.md). All input and
output hashes remain stable through independent validation.

| Measurement | Fresh baseline | Candidate |
|---|---:|---:|
| Correct source frames per positive case | 1, 2, 3 | 0, 1, 2, 3 |
| Correct positive frames across 120 cases | 360 | 480 |
| First correct frame after initial nominal FSW | 159.9375–160.0625 ms | 79.8958–80.0833 ms |
| Positive channel CRC checks passing | 1,080 | 1,440 |
| Correct frames in six mixed-history cases | 6 | 12 |
| False current proof in 36 control cases | 0 | 0 |
| Read-size groups with identical decoded results, consumed frontiers and trace bytes | 52/52 | 52/52 |

The paired gain, computed separately for every case, is
**79.9375–80.0625 ms**, exceeding the registered greater-than-70-ms gate in
120/120 cases. Taking differences between unrelated extrema in the table would
not be a paired measurement. Source-frame identities and decoded channel bits
are checked; neither a sync count nor historical confirmation can substitute.
All three independent direct channel-block controls are unchanged.
Read-size invariance excludes only six explicitly recorded provider/cache
read-ahead fields; those raw values are retained and are not claimed identical.

The matrix contains two deterministic boxcar waveform shapes, 20 starting
sample offsets and read sizes 1, 37 and 512. Controls include valid FEC with
wrong CRCs, wrong LICH parity, valid-to-invalid history, one FSW followed by
constant symbols, zero discriminator input and one fixed random seed. These
are finite generated 48 kHz discriminator streams. There is no original complex
IQ, fading, voice or RF hardware in this experiment.

## Extra work caused by provisional acceptance

| Diagnostic across its scenario | Baseline | Candidate |
|---|---:|---:|
| Wrong-LICH frame-handler calls | 24 | 48 |
| One-FSW frame-handler calls | 0 | 6 |
| Wrong-CRC real hard-fallback checks | 54 | 72 |
| All waveform hard-fallback checks | 72 | 90 |
| Mixed-history calls with old confirmation but no current proof | 12 | 12 |

Invalid frames still consume receiver work. The raw comparison separately
reports result-0 and result-1 calls and body sample consumption; result 1 is
historical confirmation, not proof of the current frame. The candidate's extra
work is neither hidden nor interpreted as a measured CPU cost. No wall-clock
throughput, GPU benefit, power or full-app speedup has been established.

## Qualification boundary and next experiments

The component uses real acquisition and frame/FEC/CRC paths, with the inherited
documented side-effect sinks and a bypass of full dispatcher/profile feedback.
The existing sync path also updates the scanner clock before frame validation.
These results cannot show that invalid candidates will never delay scanning.

Next gates are fixed held-out payloads and negative seeds; entry mid-frame;
damaged/missing sync words; sample slips and recovery; controlled impaired IQ;
then full-engine mixed-protocol/scanner regression. Channel-to-channel leakage,
scanner hold behavior, mobile audio and physical hardware remain untested here.
Any candidate that fails those gates must stay outside released defaults.

This work neither identifies nor recovers unknown encryption keys. It tests
clear control data with independent known vectors. Existing release artifacts
and user settings are unchanged.

## Reproduction and evidence

See [the isolated build and paired runner](../../experiments/nxdn_first_sync/README.md).
The prerequisite frozen raw archive has SHA-256
`65bab2562c9627e71ffc9debcb55014bdf853f39745fbfa45e2077eb11fb6eb7`.
New policy tests cover lost frames, wrong bits, truncated data, stale proof,
changed trace bytes, insufficient gains, input drift and failed-baseline stops.
All 22 pass normally and under Python optimization on Windows. The existing
native symbol-phase regression also passes.

Both [push 36146171306](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36146171306)
and [PR 36146177193](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36146177193)
pass Linux Clang release and ASan/UBSan builds. Each job passes the 66 existing
frame tests plus 22 new policy tests, normally and under Python optimization;
the native pair, symbol-phase regression and candidate-only archive isolation
also pass. All 45 implementation checks pass; one external review is skipped.
The research workflow requires valid evidence, while recording the candidate's
progression gate separately: a green workflow alone is not proof of improvement.

The independent Windows review rechecks every relevant frame identity, all
2,736 case CRC events across both binaries, chunk invariance and hash bindings
without importing the project comparer or inspector. A separate cross-platform
audit verifies all four Linux pairs against Windows: 160 parsed JSONL rows,
156 identical sample-trace files and four identical vector files per executable.
Raw JSONL line endings differ across operating systems; parsed observations
are identical. All 1,304 output artifacts from the eight Linux executions and
all eight downloaded ELF executables match their recorded hashes. This closes
the binary-retention gap documented in the earlier frame study for these new
runs; it does not retroactively verify the older unavailable CI binaries.

The push checkout is the implementation commit; pull-request jobs record
GitHub's synthetic merge `4ee1fdd3f93ef7951f57eb7359be33f14611be1f`.
Measured observations and corresponding release/sanitizer executable bytes are
identical between the two CI events. The report retains build commands, symbol
tables and sanitizer output; this is not a hermetic dependency proof.

The [machine-readable evidence](evidence/nxdn-first-sync-2026-09-25.json) links
the registered pair, independent audits, CI jobs, costs and preserved hashes.
The [raw archive](evidence/nxdn-first-sync-2026-09-25-raw.zip) contains 1,870
entries and 47,099,730 bytes. Every entry was reopened and verified. SHA-256:

`716898ae7adcfcebfaefd05921964f9560a3786e5ac83c065f2f94561d65b217`

It retains both Windows executables, measured input sources, frozen original
inputs, build/linkage audits, failed setup logs, four Linux pairs and all eight
Linux executables. The prerequisite frame archive remains separate. Full source
tree snapshots remain local with recorded digests; the public commits and exact
measured source inputs provide the distributed source reference. All 269
preservation checks pass, including five earlier raw archives and three existing
research receiver binaries.
