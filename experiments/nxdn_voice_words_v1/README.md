# Independent NXDN clear voice words

This is an isolated channel-word experiment. It does not change the receiver,
Android or Windows defaults. Read the
[registration](../../docs/research/NXDN-VOICE-WORDS-V1-PREREGISTRATION-2026-09-25.md)
before interpreting results.

`encoding.py` independently generates Golay arithmetic, the A-dependent B mask,
and channel placement. `prepare.py` builds the fixed 8,266-word corpus from
pinned announcement/silence bytes, one-hot words and exhaustive A/B sweeps.
`primary_encoder.cpp` calls untouched pinned MMDVM-Host code once per paired
input; it is not a copied lookup-table oracle. `probe.c` uses XeraX's actual
dibit map and real mbelib hard/soft decoders. `analyze.py` does not import either
encoder and reconstructs source identities independently.

The production probe is allowed only after every independent channel byte
agrees with the primary encoder. Its 27,044 calls cover clean words and all
single channel-bit errors in 73 base words. Protected A/B errors must recover
the original source. Unprotected C errors must appear in their corresponding
source bit. A successful return or apparently plausible sound is not proof
that the original voice content survived.

Run the portable framework checks without radio hardware or external packages:

```text
python -m unittest discover -s experiments/nxdn_voice_words_v1 -v
python -O -m unittest discover -s experiments/nxdn_voice_words_v1 -v
```

The recorded Windows native build uses Clang 19, the MinGW sysroot, and the
existing mbelib-neo 2.1.0 archive identified by the installed package metadata.
`CMakeLists.txt` requires `VOICE_PRIMARY_ROOT` pointing to the verified pinned
source closure and an installed `mbe-neo` CMake package. Runtime DLLs, link maps,
source manifests and corresponding codec source are retained in the study
archive; compiler tools are identified by hashes rather than redistributed.

`run.py` is deliberately bound to the registered corpus manifest and independent
preflight audit. It reserves a fresh output directory, freezes inputs/sources/
binaries before executing, retains failures and never retries a native batch.
Reproductions must have separate identities and must not overwrite the recorded
attempt. Checkers can inspect the archived evidence without rerunning native
code. Python optimization must not disable any gates.

This stage does not synthesize speech, process complete calls, receive I/Q,
compare timing, estimate RF sensitivity or recover privacy keys. Full clear-call
retention and negative controls remain separate prerequisites for future
recovery work. No APK/EXE feature or speed claim follows from a pass here.
