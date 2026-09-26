# NXDN48 damaged-sync and sample-slip recovery

This bounded study compares the existing acquisition option off/on. It does not
change product code, settings or released defaults. The hypotheses, inputs and
gates are fixed in
`docs/research/NXDN-RECOVERY-PREREGISTRATION-2026-09-25.md` before native execution.

The Windows receiver is the hash-bound candidate from the completed continuous
engine study. Its measured frame implementation equals RC3 after line-ending
normalization only. Reuse the old experiment directory as `<anchor>`; it contains
the candidate executable/DLLs, build/source records and eight legacy anchor
invocations. Do not run the original full matrix or weaken its source hash guards.

```
python -m unittest discover -s experiments/nxdn_recovery -v
python -O -m unittest discover -s experiments/nxdn_recovery -v
python experiments/nxdn_recovery/prepare.py <new-input-directory> <anchor>
python experiments/nxdn_recovery/run.py <anchor>/frozen/candidate.exe <anchor> <new-input-directory> <new-result-directory>
```

The preparer and runner refuse an existing output directory. Inputs include two
new control payloads, immutable original waveforms, delivered floats, sample
origin/occurrence maps and independent channel checkwords. Each of 27 waveforms
runs with chunks 37/512, acquisition off/on and observation off/on, in a fresh
bounded process: 216 invocations, including eight legacy reproduction anchors.
No wall-time or CPU benchmark is inferred from the invocation count.

The runner retains malformed output, timeouts, nonzero exits and negative
receiver results. It archives inputs, executable, DLLs, original build records,
scripts and preregistration before execution. Live imported script identities
are checked before and after; frozen old inspector bytes have their own guard.
Neither installed user configuration nor radio hardware is accessed.

The new inspector reuses the old trace/event validity checks unchanged. Source
attribution uses mapped body positions, independently of returned payload bits.
Final CRC acceptance and exact source information/checkwords are separate tests.
All three channels must be correct for a full recovered control frame. A single
correct channel can support partial current proof but cannot hide a different
incorrect accepted channel. An unattributed pass remains ungrounded; it is not
automatically proof of a false radio decode.

Warm exposure, actual resets, full-frame retention, incorrect accepted content,
negative controls, observer parity and exact chunk traces are reported separately.
Cold gains cannot pass the registered warm-recovery hypothesis. Recovery endpoints
include delivered and original coordinates, and each option's change against
its matching clean case. The unit tests include deliberately incorrect channel
content, broken lineage and process/trace failures; they do not execute the native
receiver.

This is a finite 48 kHz discriminator-input experiment with a known NXDN48 profile
and matched filtering disabled. It does not measure complex-IQ RF impairments,
automatic protocol choice, audio latency, phone behavior, trunking, unknown-key
recovery or multichannel throughput. Product changes require further evidence.
