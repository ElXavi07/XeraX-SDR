# Bounded NXDN acquisition measurement

This opt-in experiment calls the real NXDN48 symbol/sync/dibit chain with known
generated discriminator samples. It does not decode full CRC/FEC-valid frames,
run a vocoder, measure original-IQ latency, or change the apps.

Configure the normal upstream dependencies, adding `-DBUILD_TESTING=ON
-DXERAX_ACQUISITION_RESEARCH=ON -DDSD_FORCE_RADIO_PIPELINE=ON`. Build targets
`xerax_nxdn_acquisition_observer` and `dsd-neo_test_frame_sync_nxdn_fsk_phase`.
The [Linux workflow](../../.github/workflows/acquisition-research.yml) contains
a complete dependency and sanitizer recipe. On Windows use the existing host
toolchain and dependency paths in `scripts/build_windows.ps1`, but a separate
build directory; Qt is unnecessary for this test.

Run `python experiments/nxdn_acquisition/run_acquisition.py <observer executable>
<new artifact directory>`. The runner refuses an existing destination, freezes
input hashes before execution, preserves stdout/stderr and every raw sample-pop
trace, then applies the independent validator. Instrumentation runs are not
speed trials. `python -m unittest discover -s experiments/nxdn_acquisition -v`
checks synthetic mutations; set `XERAX_NXDN_ACQUISITION_EXE` to explicitly enable
the native matrix too. CTest `XERAX_NXDN_ACQUISITION_CONTRACT` enables it automatically.

The OFF-by-default option adds hooks only to the private DSP test archive. The
production DSP archive never compiles the observer branch. A source-level
observer-disabled/enabled comparison does not substitute for an uninstrumented
production speed comparison.

Schema 1 uses exclusive delivered-sample frontiers in the explicitly named
`discriminator_samples` domain. Do not load it into the benchmark timeline's
original-complex-IQ schema. Payloads are 182 known uncoded dibits. Nominal FSW
landmarks identify generated unit boundaries, not RF energy onset; the signal
already exists in the preceding preamble. No matched-filter handback is exercised.

See the [fixed preregistration](../../docs/research/NXDN-ACQUISITION-PREREGISTRATION-2026-09-25.md)
for the 120-case matrix, exact waveform and separate correctness/invariance gates.
