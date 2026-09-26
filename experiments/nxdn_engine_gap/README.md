# Continuous NXDN evidence recovery

This is a registered experiment, not an installed decoder or a released default.
See `docs/research/NXDN-ENGINE-GAP-PREREGISTRATION-2026-09-25.md` for hypotheses,
the immutable 64-case matrix and limitations.

The executable exports the actual static engine live loop from a generated copy.
Real initialization, sync search, protocol dispatch, returned dibits, NXDN frame
handling, FEC, CRC, semantics and no-carrier reset run continuously. The candidate
is the exact private accounting patch from the preceding rejected-LICH study.
No decoder state is repaired by callbacks; rejected frame bodies remain in the
continuous source. Hardware/audio startup is excluded. A real unstarted RTL
context is created and destroyed; start/tune attempts are guarded errors.

Source is finite 48 kHz discriminator floats, not complex IQ. Source ordinals
require full returned-body equality and absolute per-dibit boundaries within
one symbol of the nominal boundary; observed sample traces must back those
positions within that frame's own execution. Neither equal repeated payloads
nor a complete body count at EOF establishes source identity. Instrumentation
on/off compares sample/CRC callbacks; the common boundary/dibit logger remains
in both runs. Wall clocks are real and input is replayed as fast as the engine
consumes it, so silent sample gaps are not real-time RF timer tests.

Configure this directory with the same dependencies/options as the receiver,
radio pipeline enabled, audio backend `none`, terminal/Qt disabled. Build:

```
cmake --build <build> --target xerax_nxdn_engine_baseline xerax_nxdn_engine_candidate xerax_nxdn_engine_candidate_routing dsd-neo_test_nxdn_frame_routing
ctest --test-dir <build> -R '^(NXDN_FRAME_ROUTING|XERAX_NXDN_ENGINE_CANDIDATE_ROUTING)$' --output-on-failure
python experiments/nxdn_engine_gap/test_policy.py
python -O experiments/nxdn_engine_gap/test_policy.py
python experiments/nxdn_engine_gap/run_pair.py <build> <new-output-directory>
```

Inspect compiler commands and role link maps before native matrix execution:
private DSP and role-specific frame code must supply the observed symbols, and
`XERAX_FIRST_CANONICAL_NXDN48` must be absent. Runtime fast acquisition is the
registered off/on dimension. Ordinary protocol/reset stubs are not allowed.

`run_pair.py` freezes sources, binaries, dependency DLLs, complete input floats,
maps, build configuration and hashes before the first invocation. It executes
each case/role/observer combination once in a separate process with a 60-second
bound and saves raw stdout/stderr, sample-index traces and audit outcomes. It
removes process `DSD_*` environment overrides for controlled initialization;
it does not read or write installed user configuration. Existing output folders
are refused. Malformed output, timeout and negative results remain retained.

Measurement validity, source exposure, correction, control retention, actual
reset coverage and chunk equality are separate report fields. Corrected W/P/W
must continue into the next consecutive W confirming, with no intervening body
or reset; a skipped W is not a correction. Clean/sticky controls must actually
decode their specified source frames. Both pending and previously confirmed
gap cases must exhibit an actual reset clearing that state for progression.
An unexposed or failed quality gate is a valid negative measurement, not a
reason to change the input or rerun a favorable subset.

No claim is made here about RF sensitivity, audio clarity, complex-IQ timing,
scanner tuning, multichannel behavior, encryption keys or whole-app speed.
