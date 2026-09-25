# Absolute-entry NXDN48 recovery experiment

This is a separate component test of the optional RC2 receiver policy, not a
change to APK/EXE defaults. Read the [preregistration](../../docs/research/NXDN-ENTRY-PREREGISTRATION-2026-09-25.md)
before interpreting results.

`observer.c` reuses the frozen frame observer's waveform, state setup, real
sync/frame/FEC/CRC calls, sample lineage and observation-transparency checks.
Two executables differ only in the value assigned to the public session option.
Both inner observed/unobserved runs use the same receiver policy. Twenty
absolute positive start positions replace the old first-20-samples grid;
the complete waveform remains in its original coordinates.

`policy.py` verifies the unchanged inspector/runner hashes before loading them.
The inspector adapter changes only its allowed input MATRIX. Channel truth,
CRC checks, EOF rejection, event partitions and lineage validation are inherited
unchanged. The new progression comparison uses successful source-frame identity
and completion frontiers, not sync counts or historical confirmation.

Build the two `xerax_nxdn_entry_baseline` and `xerax_nxdn_entry_candidate` targets
in a fresh CMake directory using the dependency configuration in the dedicated
[CI workflow](../../.github/workflows/nxdn-entry-research.yml). Preserve the exact
binaries, compiler/link commands and input bytes before executing them. The
registered RC2 validation ZIP is available on the
[RC2 release](https://github.com/ElXavi07/XeraX-SDR/releases/tag/v4.3.2-rc.2).

```text
python -m unittest discover -s experiments/nxdn_entry -p "test_*.py" -v
python -O -m unittest discover -s experiments/nxdn_entry -p "test_*.py" -v
python experiments/nxdn_entry/run_pair.py BASELINE CANDIDATE NEW_OUTPUT --rc2-archive RC2_VALIDATION_ZIP
```

The output directory must not exist. Exit zero means the measurement evidence
is valid; inspect `progression_pass` separately. A rejected candidate is a valid
negative experiment and must be retained. Do not change inputs and retry to
hide a receiver failure. The runner reopens raw outputs, checks exact frozen
anchor rows/traces, validates all chunk groups and retains failures separately.

The inputs contain repeated clear control frames, not voice or encrypted
traffic. No hardware, complex I/Q, RF noise, payload variation, warm-receiver
loss/recovery, overlapping signals or full application dispatcher is exercised.
Signal-time gains are neither CPU speedups nor audible latency measurements.
