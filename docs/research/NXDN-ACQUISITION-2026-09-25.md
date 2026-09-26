# Qualifying real NXDN48 acquisition measurements

The first native Windows run passes the fixed discriminator-domain measurement
contract: **120/120 cases, 87,360 independently checked dibits, and 40/40 groups
with identical acquisition frontiers across read chunks of 1, 37 and 512**.
The measurement hook does not change either decoded payload or sync result.
This is measurement infrastructure; no receiver optimization or app speedup is
being claimed. The existing APK/EXE packages and defaults are unchanged.

## Method and provenance

[Preregistration](NXDN-ACQUISITION-PREREGISTRATION-2026-09-25.md) fixes the matrix,
oracle and gates before the native run. The source baseline is
`4b0dd222c3bb6abb80c50729058471313bbcb5ce`. New
[harness source](../../experiments/nxdn_acquisition/observer.c) reuses the existing
phase-test generator and invokes the actual getFrameSync/getSymbol/getDibitSoft
chain. An independently written validator reconstructs every expected payload
and checks each successful sample delivery against the recorded frontier.

Two transition shapes and every initial sample offset 0–19 are paired with three
provider chunk sizes. Each case first disables, then enables the observer, with
state reset between runs. Two sync-plus-payload observations are retained per
run: 480 payload observations, each 182 uncoded dibits. No alignment search is
used to select the expected payload. Every trace index is checked in bounds,
strictly increasing and reconciled with the actual cache position. All 120
traces report zero skipped samples and zero lineage errors.

Eight direct controls cover successful delivery, disabled observer, empty cache,
null output, null state, a nonzero cache index, and generation rejection both
before and during delivery. These are instrumentation controls, **not** noise-only
RF false-positive measurements. The independent validator also tests malformed
records, missing observations, wrong payloads, wrong domains and read-ahead errors.

The tested Windows executable SHA-256 is
`da1e6ba448f5973c1681966fa25c2525505cddf49832c316daa19678545f1ea2`.
The normal DSP archive has neither new observer symbol; the private research
archive contains both. The existing phase regression also passes against the
normal DSP archive. Native instrumentation stays behind an OFF-by-default build
option and is never compiled into the shipped DSP archive.

## What the timing actually says

The sample rate is 48,000 **discriminator samples/s**. It is not original complex
I/Q, elapsed CPU time, or speaker output time. The generated FSW boundaries are
known symbol landmarks, not RF onset; there is already a signal in the preamble.

| Observation | Measured result |
| --- | --- |
| First accepted generated unit, zero-based | 1 in all 120 cases |
| Next accepted unit | 2 in all 120 cases |
| First acceptance after the **first** nominal FSW starts | 4,034–4,043 samples; 84.0417–84.2292 ms |
| First acceptance after its **own accepted** FSW starts | 194–203 samples; 4.0417–4.2292 ms |
| Maximum provider read-ahead at a recorded sync | 460 samples; 9.5833 ms |
| Buffer-chunk invariance | 40/40 shape/offset groups |

The two timing rows use different landmarks; reporting only the roughly 4 ms
row as initial acquisition would omit one complete generated unit. The current
[`frame_sync_try_nxdn`](../../upstream/dsd-neo/src/dsp/dsd_frame_sync.c) requires
`lastsynctype` to match the current sync type before returning acceptance. The
observed acceptance of the second matching FSW is consistent with that code.
Provider read-ahead is also measurable and cannot stand in for consumption.

## Limits and next hypothesis

These are clean shaped discriminator vectors, not independently encoded NXDN
frames. The fixture generates the receiver's sign-only sync search pattern using
outer levels; it is not a complete 20-bit over-air FSW magnitude vector. That
distinction must be addressed in the next fully encoded frame fixture. These
vectors exercise neither channel FEC/CRC nor privacy, vocoding, matched-filter
handback, noisy I/Q, clock drift, overlapping traffic or hardware. Original-IQ
acquisition, first validated frame and first PCM measurements remain **null**.
The current 76-case I/Q corpus audit verifies hashes but finds no complete
transmitted-bit or independently marked onset truth suitable for those claims.

The source audit finds multiple places where original-IQ identity must survive:
asynchronous input/output rings, filter support, resampling, cache catch-up,
matched-filter history replay and generation changes. Some block-wide operations
can depend on later samples in a block. Attaching a transport-read counter to a
sync event would hide those distinctions. [SigMF](https://sigmf.org/) specifies
sample format and indexed annotations; it does not itself establish that a
particular received frame is valid.

The next bounded hypothesis is that **a provisional first-FSW candidate followed
by independent current-frame validation can reduce initial wait without raising
false acceptance**. Before implementation, add valid NXDN codewords, wrong-FSW
and wrong-CRC controls, noise/wrong-rate interference, reset/drop boundaries and
explicit provisional-versus-validated events. Preserve the present second-sync
path as the baseline. Do not promote a raw early sync into an audio, identity or
trunking decision. Physical RF and phone execution remain pending.

## Reproduction and evidence

[Experiment instructions](../../experiments/nxdn_acquisition/README.md) describe
the opt-in target and artifact-preserving runner. [Machine-readable results](evidence/nxdn-acquisition-2026-09-25.json)
and the [raw evidence archive](evidence/nxdn-acquisition-2026-09-25-raw.zip) retain
first-run JSONL, all 120 pop traces, frozen input hashes, independent audits,
source baseline archive, research executable, build logs, CI artifacts, failed
setup attempts and symbol-isolation evidence. All 941 archive entries were
reopened and byte-verified; the 16,287,496-byte archive SHA-256 is
`8b1728af117859a5652509a2530451b36ff175c20769b144b9bcf58ecb9991aa`.

Implementation `ebedd5c` passes the Windows phase and observer contract tests.
Normal Python passes 40 synthetic/policy methods with the native method explicitly
skipped; optimized Python passes all 41 with native execution enabled. The
artifact-preserving runner independently reproduces the same native JSONL.

Source `8b1de41` passes Linux Clang release and ASan/UBSan checks in
[PR CI](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36136385660) and
[push CI](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36136384911). All parsed
native rows and all 120 trace files exactly match Windows; raw JSONL differs only
in line endings. The existing phase test, validator mutations, 16 runner policy
controls and production-symbol isolation also pass. At this source checkpoint,
33 checks pass and Macroscope is skipped by its cost limit, not review approval.

Two infrastructure failures are preserved: CRLF shell inputs stopped the initial
dependency step, and a strict GCC release build stopped on an existing misleading
indentation warning in unchanged `analog_tones.cpp`. Shell input normalization
and explicit Clang configuration fixed the new CI recipe without changing the
decoder, waveform or gates. GCC validation remains open. Android compilation and
phone execution of this new observer were not performed. Earlier history raw
archives and the pre-existing receiver binary rehash unchanged.
