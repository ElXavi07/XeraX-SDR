# Recovery experiment: pre-execution review

Preregistration commit: `38552e4b7d7391a79f4599ff9d6bbc2ce6601371`.
No new native invocation had occurred when this review was written.

The 27-waveform manifest SHA-256 is
`897035e6a439272d50312bcf7286b41e031bd61bdfdbba02ec775f1fc521c602`.
Inputs were generated once. An independent auditor imported neither the preparer,
encoder nor decoder, reconstructing 13,679,232 binary bytes across four new
encoded vectors, 26 new waveform/edit/map sets and the legacy anchor. All 112
input files including the manifest agree. Its matrix reconstruction gives 208
new invocations plus eight existing-profile reproduction invocations.

Independent preflight script SHA-256:
`d0a41823fd6abd7c6b7b5e034b09cff59123893d3c0eb0d0ce47b4af79e184ff`.
Preflight JSON SHA-256:
`766a2c91a2af432ede8edc8e40439ea65740e872ddcba329ccee831808b67ced`.
These are input-contract checks, not receiver correctness or performance results.

Twenty-six framework tests pass both normally and with Python optimization:
17 analyzer counterexamples, four input-transform checks and five mocked native
failure/identity checks. The mocks do not execute the receiver. Cases cover
incorrect accepted information, partial proof, unsupported confirmation, source
attribution independent of payload errors, changed occurrence maps, observer and
chunk disagreement, incomplete grids/exposure, cold gains failing warm promotion,
timeouts, nonzero exits, malformed output and missing or changed execution source.

Preflight changes made before native execution:

- An initial test incorrectly expected the deliberately corrupted checkword's
  low bit to flip. The frozen independent encoder flips its high bit. Corrected
  only that assertion; no encoder, generated input or registered fault changed.
- Corrected the runner's quality-result field name to `progression_pass`.
- Added preservation checks for the live imported Python sources and frozen
  inspector, as well as copied records; chunk differences now fail measurement
  validity as required by the registration.
- Added the canonical-coordinate counterpart to matched-clean recovery delay,
  so deletion/duplication cost is distinguishable from extra missed frames.

The two held-out SACCH payloads happen to share CRC6 value 59. Source truth must
compare information bits too. The dibit-zero trailer is level +8000, not a silent
zero-valued trailer. The two all-zero waveforms are repeated identical controls.
Whole-symbol slips can exceed the strict source-attribution boundary; an accepted
but unattributed channel cannot support a success claim and is not automatically
a demonstrated false decode. These limits remain explicit in result analysis.

The preregistered native matrix and thresholds are unchanged. Before/after
preservation covers 27 RC1/RC2/RC3 release files plus protected receiver source.
No installed settings, released artifacts or product source are modified.
