# Independent clear NXDN complete frames

This isolated reference gate compares arithmetic frame construction with real
pinned primary encoders. It does not change the receiver or app defaults. Read
the [registration](../../docs/research/NXDN-AIR-V1-PREREGISTRATION-2026-09-25.md)
for the fixed nine-frame domain, exact source words, and stop conditions.

The sequence covers a clear header, pure voice, both FACCH half-steal directions,
and a trailer. Its 24 transmitted voice words come from the independently
validated preceding word study. Both raw and channel-whitened frames must agree
byte for byte. Channel whitening is separate from traffic privacy.

`arithmetic.py` uses hash-pinned historical arithmetic primitives. `analyze.py`
imports neither encoder, independently reconstructs source identities, checks
every voice interval, and compares all 864 expected/output bytes. Corrupted
evidence controls must fail before a registered native invocation is allowed.

```text
python -m unittest discover -s experiments/nxdn_air_v1 -v
python -O -m unittest discover -s experiments/nxdn_air_v1 -v
```

CI runs only these portable framework tests. The registered Windows native
execution is separate and immutable. `prepare_build.py` verifies a pinned source
closure, keeps originals, and permits exactly the five registered corrections
in private encoding-path copies. CMake compiles real primary encoding routines;
it does not compile the host application or substitute receiver stubs.

`run.py` requires the fixed corpus, committed harness, and read-only source/link
audit. It freezes sources, binaries, runtime libraries, inputs and identities;
checks them again at the launch boundary; records one native attempt; and
retains failures without retries. Reproductions need separate identities.

A pass supplies complete-frame reference data for a separately registered
receiver-routing experiment. It does not establish semantic call acceptance,
voice synthesis, listening quality, RF sensitivity, I/Q acquisition, speed,
encryption support, or an APK/EXE improvement. Historical failed candidates and
the malformed-header PCM finding remain retained and unresolved.
