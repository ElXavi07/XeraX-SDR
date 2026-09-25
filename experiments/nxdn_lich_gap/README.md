# NXDN rejected-LICH evidence continuity

Read the [preregistration](../../docs/research/NXDN-LICH-GAP-PREREGISTRATION-2026-09-25.md)
before interpreting this isolated component experiment. Product sources and
released APK/EXE binaries are unchanged. The generated candidate frame source
exists only inside this experiment's build directory.

The fixed input is numeric dibits after synchronization, not complex I/Q,
discriminator audio, an actual carrier-loss event or a scanner visit. Real LICH,
whitening, convolutional decoding, CRC and confirmation code run. Semantic
message dispatch, vocoding and file output are observed sinks. Weak frames carry
a valid SACCH CRC6 and deliberately invalid FACCH CRC12 checkwords; channel
verdicts are never injected by a stub.

Build `xerax_nxdn_gap_baseline` and `xerax_nxdn_gap_candidate` using the dependency
configuration in the [workflow](../../.github/workflows/nxdn-lich-gap-research.yml).
Retain compiler/link commands and inputs before execution. The runner freezes
both executable files before starting either, retains every raw output and
records execution/parse failures. Its exit status reflects measurement validity,
not whether the hypothesis or the candidate succeeded.

```text
python -m unittest discover -s experiments/nxdn_lich_gap -p "test_*.py" -v
python -O -m unittest discover -s experiments/nxdn_lich_gap -p "test_*.py" -v
python experiments/nxdn_lich_gap/run_pair.py BASELINE CANDIDATE BUILD/inputs NEW_OUTPUT
```

Inspect `measurement_pass`, `progression_pass`, `baseline_bridges` and each role's
quality deviations separately. A null hypothesis or poor candidate remains valid
data when input/CRC/observation integrity passes. Never overwrite or rerun an
attempt merely because it did not produce the predicted result. Observer-on/off
outputs must match, apart from the explicitly recorded CRC events. The runner
reopens and compares consumed dibits with the independently encoded inputs.

Changing when frame accounting opens/closes must not lower any CRC threshold or
discard an already-confirmed transmission's sticky status. Even a successful
result here requires full-engine and waveform tests before product integration.
