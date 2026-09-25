# NXDN continuous-stream live-loop continuity: preregistration

Baseline source/evidence checkpoint: `954ec38d26849fc0bffb2c8d2b415ca101e1aa07`.
No native run of this matrix precedes registration. The preceding direct-dibit
study is frozen; its successful outcome does not determine this study's outcome.

## Question and fixed intervention

Does the demonstrated weak / rejected-LICH / weak confirmation bridge actually
survive synchronization, ordinary protocol dispatch, handler-consumption feedback
and no-carrier handling when every sample remains in a continuous stream?
H1: at least one registered case realizes the source W/P/W path and the baseline
confirms prematurely; the same private accounting change prevents that result.
H0: reset, missed intended frames or other intervening frames prevent the bridge.
H0 is a valid negative result, not an invalid measurement or reason to tune inputs.

Both roles use the real live_scanner_main_loop, processFrame, NXDN dispatcher,
getFrameSync, real channel/FEC/CRC and real noCarrier implementation. The only
candidate decoder change is the already frozen private LICH accounting patch.
Use a private engine include to export its static live loop and record actual
search/dispatch/reset boundaries; any renamed definitions/wrappers must forward
exactly once. No product source modification. No substituted semantic, protocol,
voice or reset stubs. Ordinary existing frame-routing tests also run against the
private candidate and frozen baseline sources as supplementary regressions.

## Provider, initialization and exclusions

Each native invocation is a fresh process for one case and observer setting.
Use real initOpts/initState/freeState and a real RTL context created but never
started. rtl_stream_create copies options/registers local PPM pointers; only start
opens hardware. Start/tune calls are forbidden here. Read/metrics hooks provide
finite 48 kHz discriminator floats with known NXDN48 2400/4 profile, generation1.
Use a fixed source, no hardware or network I/O. Destroy context and clear hooks
on exit. Record or guard direct radio-context operations; an unstarted backend's
output rate or reacquisition state is not initialized by the metrics hooks.

Initialize only NXDN48 protocol matching, rf_mod2, msize1, ssize128, filters off
for this declared discriminator input, PN95 seed228. Conventional listening only:
scanner, trunking, voice-only gates and visit limits are off; there is no scan-row
list, frequency change or successful tuner acceptance. Audio/record/export output
is disabled, but the actual non-voice semantic path runs. This is real engine-loop
integration with a controlled provider, not a hardware/frontend acceptance test.
Real wall clocks run; fast replay sample time is not elapsed RF time. Report these
limits rather than simulating an unrecorded wall-clock gap.

## Fixed matrix

Reuse both independently audited payloads and W/S/C/P vectors from the LICH-gap
study unchanged. W passes only SACCH CRC6; S passes all checks; C has three wrong
checks; P changes the outbound 0x41 LICH parity. No U/D cases in this stage.
Use a 32-symbol alternating 1/3 preamble and 64-symbol zero-dibit trailer.
NRZ levels are [8000,24000,-8000,-24000]; 20 samples per dibit, centered boxcar8
with clamped edge extension. A registered silent gap is true zero-amplitude input,
not dibit zero. Complete source waveforms and their absolute frame landmarks are
written before execution; never discard the unread body of a rejected frame.

Seven scenarios for each payload:

| Scenario | Source frames / gap |
| --- | --- |
| clean weak | C C W W W W |
| parity gap | C C W P W W |
| accepted CRC gap | C C W C W W |
| already strong | C C S P W W |
| no-sync gap | C C W / 2400 zero-amplitude symbols / W W W |
| bad checks | C C C C C C |
| zero input | all samples zero, same duration as six-frame cases |

Cross with runtime fast-acquisition off/on and input read chunks37/512:
2 payloads x7scenarios x2settings x2chunks =56 cases per executable. Each case
runs observer on/off in fresh processes, exactly once. Candidate and baseline
execute the same matrix. Do not adjust scenarios after seeing native outcomes.
If a full engine cannot be linked/instrumented faithfully, publish the obstacle
and do not relabel a smaller stubbed loop as full engine validation.

## Evidence and gates

Retain all source floats, provided/consumed sample frontiers and per-sample index
trace, every search result (including incidental/wrong-polarity sync), dispatched
frame entry/exit and handler return, real dispatcher verdict/profile proof,
confirmation/evidence/streak before and after, CRC information and checkwords,
no-carrier entry/exit, EOF/truncation, input overread, backend-operation counters
and enabled side effects. Reset source identity only at process start. Record
forward sample gaps as receiver behavior; never hide them by rebasing input.

Valid measurement requires immutable inputs/binaries, finite termination,
trace-to-source value equality, no invented or backwards sample indices, complete
raw event accounting and observer-on/off equality of semantic outcomes. Independent
CRC and source identity checks distinguish complete intended bodies from incidental
candidates. A valid negative path (e.g. intended W skipped or noCarrier reset)
remains a result. Distinguish production-behavior deviations from recorder failures.
A decoder rejection or a gate failure must retain its original output and report.

Progression requires at least one observed initially-unconfirmed W/P/W bridge in
baseline with exact valid source/channel lineage, no reset or other body between,
and its correction in the candidate. Candidate must not create a false current
proof on either negative scenario, lose a complete correct strong-source frame,
or break the consecutive-weak or strong-history controls. Differences in source
frames visited must be shown, not conflated with channel bit errors. Report actual
no-sync reset coverage explicitly; a scheduled gap alone is not proof of reset.
Chunk sizes must give equivalent source identities, CRC truths and verdicts;
provider buffering positions may differ and must be retained. No CPU/latency win
is claimed; the goal is accounting reliability, not more permissive acceptance.

Preserve frozen RC1/RC2 app assets. Linux release and ASan/UBSan reproduction and
independent raw-data review are required before proposing product integration.
Physical radio, phone audio, mixed-protocol acquisition, timers at real RF speed,
scan-row tuning, damaged sync, overlapping traffic and independent complex-IQ
trials remain separate gates. A successful correction here is not default-on
approval for the optional faster-acquisition setting.

## Frozen inputs

- `upstream/dsd-neo/src/engine/engine.c` SHA-256 `fb2e493663947090fa94d8e8a5188fb2b8dc0596432e05e08acb440fce77ae9f`
- `upstream/dsd-neo/src/engine/dispatch/protocol_dispatch.c` SHA-256 `3fe0c26379e3fe9ea9c9cde080aaffdb87733b05b912e3482c359b089c6deaac`
- `upstream/dsd-neo/src/engine/dispatch/dispatch_nxdn.c` SHA-256 `fac4f15b77b85e59619a7e6d39608ffd3e9b8d7b36eb8be7ce5425a29587451f`
- `upstream/dsd-neo/src/protocol/nxdn/nxdn_frame.c` SHA-256 `9022df4c611a129332123f7062a99e478ea4d24e0ce6f6a5104b5cc7fb191192`
- `experiments/nxdn_lich_gap/prepare.py` SHA-256 `42e7c64b9e6e7b65075df9661b1f6a14bd5cf424978c0a232d968db413d10ba9`
