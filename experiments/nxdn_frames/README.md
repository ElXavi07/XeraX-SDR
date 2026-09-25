# Complete NXDN control-frame measurements

This isolated research executable extends the frozen uncoded acquisition study
through real LICH handling, PN95 descrambling, SACCH/FACCH1 deinterleaving,
depuncturing, soft convolutional decoding, real hard fallback, final CRC checks
and current-frame confirmation. It does not modify application defaults.

The independent Python encoder uses benign IDLE control content. Its valid
codeword was corroborated against pinned MMDVM-Host source, with an explicitly
recorded audit-only terminal puncture sentinel. Deliberately wrong CRCs are
encoded into otherwise valid FEC. Bad LICH, mixed valid/invalid history, a single
FSW, zero input and fixed random input are retained. The valid payload contains
an extra sync-like sign window; it must not be tuned away.

Read the [registered hypotheses and gates](../../docs/research/NXDN-FRAMES-PREREGISTRATION-2026-09-25.md)
and [schema](SCHEMA.md) before interpreting results. Measurement validity and
receiver quality are separate gates. A measurement-check CI pass can document a
receiver-gate failure; it does not approve promotion into the apps.

## Reproduction

Use a separate build directory and the normal dsd-neo dependencies. The checked-in
workflow gives a full Linux Clang recipe with release and ASan/UBSan variants.
Configure with `cmake -S experiments/nxdn_frames -B <new-build-directory>` and
appropriate dependency/platform flags, then build `xerax_nxdn_frame_observer`.
The root project forces test support on; it is not an installable app build.

Run the policy/vector/validator tests with:

```text
python -m unittest discover -s experiments/nxdn_frames -p "test_*.py" -v
python -O -m unittest discover -s experiments/nxdn_frames -p "test_*.py" -v
python experiments/nxdn_frames/run_frames.py <observer-executable> <new-evidence-directory>
```

The runner refuses an existing output directory, freezes declared source, binary
and generated vectors before launch, runs once with a bounded timeout, preserves
raw JSONL/sample traces and evaluates an independently implemented validator.
Inspect both `measurement_contract_pass` and `receiver_gate_pass` in its report.
The standalone inspector CLI exits nonzero on either failed gate; the research
runner exits nonzero on infrastructure or measurement failure, and reports a
validly measured receiver failure separately.

## Boundaries

- The sample domain is **48 kHz discriminator samples**, not original complex IQ.
  There is no RF frontend, matched filter, noise sweep, vocoder or PCM timing.
- Voice, file output, alias updates and semantic content routing are explicit
  capture/no-op sinks. Actual content requests are recorded, not interpreted as
  complete application behavior. Unexpected voice/other routes fail the receiver
  gate. Shared frame-sync fixture side effects are also disabled. The wrapper
  renames four unused shared stubs so real `dsd_misc.c` remains linked unchanged.
  The inherited DSP sinks are uncounted: a zero `other_side_effects` value does
  not prove that every substituted function was uncalled.
- Historical confirmation and current-frame proof are different fields. Input
  exhaustion during a frame is explicitly censored; its output remains visible
  but cannot establish success on a fully supplied frame.
- Test CRC hooks are compiled only with both `DSD_NEO_TEST_HOOKS` and
  `XERAX_NXDN_FRAME_RESEARCH`. The ordinary NXDN archive is separately checked
  for absence of the callback setter. No public protocol API changes.
- Source hashes bind declared inputs, not a hermetic build or every transitive
  compiler/library input. Binary linkage and primary-source corroboration are
  separate retained audits. A CRC pass is not cryptographic authentication.

No encryption key recovery or authenticated decryption is tested here. Android
execution, physical receiver behavior and audible audio remain separate gates.
The observer invokes `nxdn_frame` directly; full engine dispatch, protocol hunt
feedback and retuning behavior are outside this fixed-profile component study.
