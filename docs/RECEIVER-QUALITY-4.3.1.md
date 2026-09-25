# XeraX SDR 4.3.1 — reception and decoder efficiency

This update shares the same decoder change between Android ARM64, Android ARMv7
and Windows x64. It is the first production optimization after the
[2026 research and baseline](research/INITIAL-RESULTS.md).

## Changes you can use

- The listening screen distinguishes incoming radio samples, searching for
  synchronization, digital synchronization without voice, voice activity without
  decoded audio, decoded audio arriving, and a stopped input.
- **Receiver tools → Quality → Save reception report** writes a local JSON file
  with frequency, mode, gain, signal measurements and audio counters. It excludes
  keys, account credentials and recordings. Nothing is uploaded automatically.
- Control-frame statistics say when measurements are unavailable instead of
  displaying a misleading zero. Their observation window resets on a mode or
  saved-system change, including changes at the same frequency.
- Windows audio advice refers to Windows output and volume. The phone-speaker
  shortcut is shown on Android. English and Spanish include the new messages.
- Android also receives the existing digital gain and analog peak-handling fixes
  previously released in Windows 4.3.0 preview 3.

## Measured optimization

The shared four-level soft-bit calculation previously recomputed distances and
level spacing separately for each bit. It now shares that work between the two
bits while preserving ordering, rounding, scaling and decision behavior.

| Experiment | Observed result |
|---|---|
| Old/new calculation, finite symbols and level permutations | 934,957 inputs matched exactly |
| Windows release compiler, seven paired kernel trials | Median old/new time ratio **1.5208×** (about 34% less time in this calculation) |
| GCC cross-check, seven paired kernel trials | Median old/new time ratio **1.3941×** |
| Native receiver replay, 76 captures × two builds | All 152 executions completed; all 76 before/after observation pairs matched |
| Actual output audio | PCM format and PCM bytes matched for all 76 pairs |
| Decoded frame payloads | All compared hashes matched; 31 pairs produced nonempty payloads |
| Mandatory clean/negative gates | Passed in both builds |

This is **not** a 1.52× whole-receiver speedup, an Android-device speed measurement,
or a weak-signal quality improvement. The baseline's five impaired-signal misses
remain unchanged. The full pipeline includes demodulation, synchronization, error
correction, voice synthesis and I/O beyond this small calculation. No GPU decoder,
new privacy algorithm, or unknown-key recovery was added.

The replay corpus covers DMR, NXDN48/96, P25 Phase 1 C4FM/CQPSK and Phase 2,
with clean signals, noise, offsets, clock error, interruptions, overlapping
traffic and negative controls. These are controlled synthetic fixtures; they
do not certify every trunking system or real RF environment.

## Repeat the measurements

Release software checks: 37 shared host test groups passed, including the QML
suite (85 reported checks, including fixture setup/cleanup). The benchmark
framework passed 49 tests; the existing native soft-symbol regression passed.
The packaged Windows application passed 29 checks for navigation, English/Spanish
layouts, diagnostic tones, WAV replay, synthetic NFM/AM/WFM through RTL-TCP and
PortAudio, scanner audio gating, and connection failures. The translation catalog
passed 981 placeholder checks.

Both Android packages identify as `com.xerax.sdr`, version `4.3.1`, code `40301`,
minimum Android 10. Their signatures match the previous official release, their
packaged decoder libraries match the build output, and dependency/ZIP/license
checks passed. All ARM64 native libraries pass 16 KB load-alignment verification.
These package checks do not replace running the app on a physical Android device.

The Windows portable archive and a validation installer each matched all 1,493
staged files. The validation installation started, showed the embedded icon and
uninstalled successfully under a separate test identity; it did not replace the
user's installed app. The distributed installer retains the normal application
identity. The Windows binaries are unsigned.

A first Windows test-tone check expired while still playing during concurrent
compilation. Its test allowance was increased from three to eight seconds without
relaxing the output assertions; the complete packaged-app suite then passed.
An initial QML run also failed without a captured diagnostic; the suite was rerun
with file-based logging and passed, then passed again after making the mobile
fixture explicitly identify as Android. These transient test failures are retained
here rather than counted as successful first attempts.

Build the `checks` project and run `dibit_metrics --benchmark`. The frozen old
calculation remains in that test so comparisons use the same input sequence.
For complete receiver comparisons, use the [benchmark runner](../benchmarks/README.md)
with baseline/candidate profiles, then run:

```text
python scripts/check_iq_parity.py <report.json> --out <parity.json>
```

The tool compares actual PCM samples as well as decoded metrics; WAV container
metadata alone is not treated as an audio difference. Keep the same capture hashes,
compiler options and input-stage definitions. Do not time benchmarks during builds.

Raw compact evidence is in [research/results/4.3.1](research/results/4.3.1).
The baseline receiver SHA-256 was
`515e81d7fd0ce4bcd8c4ca299fa5232592141faff694640314358cc473e6668f`.

## Interpretation and next work

The UI samples health approximately once a second; its phases are troubleshooting
observations, not precise acquisition-latency measurements or proof of intelligible
speech. P25 control-channel counters do not substitute for DMR/NXDN frame-error
rates. A selected supplied key is not proven correct merely by its key ID.

Physical phone/SDR acceptance, thermal/battery tests, live weak-signal reception,
and Android on-device performance remain to be measured. The next engineering
milestone remains sample-indexed synchronization timing and protocol-specific frame
quality metrics, followed by measured recovery/filtering and multi-channel work in
the [roadmap](research/ENGINEERING-ROADMAP.md).
