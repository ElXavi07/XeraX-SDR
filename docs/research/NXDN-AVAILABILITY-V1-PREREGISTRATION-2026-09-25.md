# NXDN explicit input availability: candidate registration

Register this bounded implementation before candidate source generation, building
or receiver execution. Baseline publication is
`ec712a0869184c0b73ec06b1ce36d3d1bdaf6b04`. The preceding active-boundary result
is immutable: 40 unavailable-slot synthesis calls, retained complete early words,
and a separate 12/20 later-word recovery failure after exposed bad parity.

## Candidate and isolation

Implement the [reviewed design](NXDN-INPUT-AVAILABILITY-DESIGN-2026-09-25.md) only
in `experiments/nxdn_availability_v1/candidate`. Do not edit upstream, patches,
released defaults, app settings or older experiment sources/artifacts. Record
original Git blobs and the full private source diff. Add checked symbol/dibit
APIs returning explicit per-call availability while retaining legacy APIs.
Carry a local 182-entry validity map into NXDN control decoding and a per-slot
mask into voice processing before FEC, media marking or audio copying. Retain
absolute slot identities and complete early slots despite later EOF. Require
complete LICH/control ranges before their interpretation. No new sync policy,
FEC algorithm, silence substitution, key operation or vocoder reset is allowed.

The private changes are limited to `dsd_symbol.c`, `dsd_dibit.c`, `nxdn_frame.c`,
`nxdn_voice.c` and their declaring headers, plus candidate-only build, observation
and tests. Preserve old successful behavior, replay cleanup/legacy bookkeeping,
soft metrics, matched-filter history and datascope behavior. Availability cannot
be inferred from symbol counters, numerical zero, reliability, current EOF,
status or synthesis flags. Existing privacy/history behavior for missing encrypted
slots is not certified by this clear conventional experiment.

## Preflight contract tests

Compilation and small dedicated unit-test processes are permitted during
implementation; retain failures and resulting corrections. They are not the
registered receiver matrix or a hidden native fixture generator. Cover checked
acquisition at zero/partial/exact EOF and SPS10/20; binary, soft-binary and float
replay, short/invalid records and bounded loop behavior; actual datascope counter
reset; unchanged legacy successful values; missing control-block boundaries;
incomplete LICH; all 16 availability masks crossed with voice selectors and hard/
soft paths; no stale audio or media/file activity when no slot is available.
Keep meaningful existing regression assertions. Compile radio and radio-less
symbol paths where applicable. Keep release-mode tests active rather than relying
on disabled assertions.

Before any receiver invocation, commit the final candidate, observer, independent
checker, runner and tests, record exact hashes and verify real object/linkage
targets. The new checked-reader/masked-voice seams must be observed directly;
unused legacy wrappers cannot establish lack of processing. Preserve each failed
build. Do not run a receiver as a preflight smoke test. The frozen baseline EXE
is never rerun or rebuilt.

## Fixed receiver matrix and cached comparisons

Use exactly 20 new candidate identities: four active-boundary inputs plus the
full cold clean anchor, each at chunks37/512 and observation0/1, with the public
fast option1. Reuse existing input bytes without regenerating or reshaping them.
No new native encoder is needed. The inputs and complete source oracle are in
the prior raw archive and verified original study.

- Active input manifest SHA256:
  `899bc2f55403b4b5f465dfbf8939d3dc396e86d197feef86654d3a6529b7a0c6`.
- Active baseline report SHA256:
  `058cf74cb23a390d0815e20ae0a2faeb8cf8e2c4e2c4fee98beb04ac290864db`.
- Prior clean-anchor report SHA256:
  `50a7dbb4b33200e203e102f58195110abedf6159ce02b66b551ebb2c65b74ab0`.
- Cold waveform SHA256:
  `187ec959f1d3fb81b7fa4f35df7a118eab7a50dca9677ef6bdacae06aa9657c8`.

The active inputs are `active_prefix_6159`, `active_prefix_6160`,
`active_prefix_6161`, `active_bad_lich`; the fifth is unchanged `cold.f32le`.
Each identity runs once, including failures, with a60second timeout and no
automatic retries. Save arguments, actual exit, stdout/stderr and partial traces.
Continue distinct identities after an execution/measurement failure; abort new
launches on source/input/runtime drift. Do not widen this matrix based on results.

## Falsifiable gates

Separate measurement validity from receiver quality and targeted improvement.
Independently establish actual input delivery and source frame/slot ownership,
then known49-bit FEC/synthesis-input equality. Retain hard/soft input matrices,
reliabilities, actual status and32/64/128 flags. No accepted-speech metric.

1. Strong header and intended V0 actually exposed in every active case; parity
   rejection remains exposed without target voice, control proof or synthesis.
2. No FEC, synthesis, stale audio copy or media activation from an unavailable
   voice slot. Expected prefix FEC/synthesis counts are0,1,1, with exact word0
   retained at6160/6161. Complete earlier SACCH remains eligible.
3. Full cold anchor retains all24 source occurrences and the correct clear epoch,
   both FACCH half-steal layouts and actual trailer. Complete supplied paths
   agree with cached baseline in source delivery, bits, control and call state.
4. Detail/chunk modes agree on common outcomes and source-pop traces. Explicit
   availability observations must agree with independent finite-input evidence.
5. Bad-LICH later recovery remains separately judged against all20 expected
   clean words. Its existing12-word outcome cannot be relabeled a recovery pass.
   Require no regression against cached baseline, while preserving that unmet gate.
6. Preflight contracts and every source/input/dependency/runtime/release identity
   remain valid. Preserve previous failed primer, off-phase recovery veto and
   malformed-header PCM evidence; do not rewrite or rerun them.

The targeted guard gate requires1–4 and6 plus no bad-LICH regression. Aggregate
receiver progression additionally requires the20-word recovery gate; a successful
guard may coexist with aggregate failure. `product_promotion:false` remains fixed
in this first candidate study. Before product integration, separately register
bounded preservation checks for prior off-phase/malformed-header controls and
complete application/device acceptance. Synthetic discriminator evidence cannot
certify independently impaired complex I/Q, real RF, listening quality, CPU/GPU
speed or complete Android/Windows readiness. Build app candidates only after
their relevant integration gates, preserving existing release artifacts.
