# NXDN confirmation continuity in the actual receiver loop

The rejected-LICH accounting defect survives real synchronization, dispatch and
no-carrier handling in a continuous finite sample stream. The isolated fix
corrects the registered directly adjacent W/P/W exposures, preserves the tested
strong/consecutive-weak controls, and passes actual signal-loss reset checks.
Production sources, app packages, defaults and user settings remain unchanged.

This establishes an integration result for a controlled discriminator source.
It does not establish RF sensitivity, voice quality, CPU speed or performance of
the complete Android/Windows application. Two genuine passing weak CRCs are being
combined too early; the defect does not manufacture a CRC or recover encryption.

## Registered test and actual exposure

[Preregistration](NXDN-ENGINE-GAP-PREREGISTRATION-2026-09-25.md) preceded native
execution: commits `a6e9218` and `38a8346`. Harness source was frozen at
`54a2f85b08109525dbe57f1fa02dffa567e32b19`; Linux reproduction uses `6a82ea6`.
The candidate is the exact private patch from the
[direct rejected-LICH study](NXDN-LICH-GAP-2026-09-25.md), with no new decoder
policy or source-vector tuning in this stage.

The real `live_scanner_main_loop`, `getFrameSync`, `processFrame`, NXDN dispatcher,
returned dibits, frame/FEC/CRC/semantic paths and `noCarrier` execute. Initialization
and cleanup are real. A real RTL context is created but never started. The input
hook supplies finite 48 kHz discriminator samples, with a known 2400-symbol/s,
four-level profile. Hardware startup and application/audio startup are excluded.
No semantic, voice, protocol or reset stubs replace these paths.

Two previously independently verified payloads, eight registered scenarios,
runtime fast acquisition off/on, and chunks of 37/512 samples make 64 cases per
role. Each runs once with optional sample/CRC observers off and once on in fresh
processes: 256 Windows invocations for the paired policies. Linux repeats that
complete matrix in release and ASan/UBSan builds. Every waveform includes the
unread portion of a rejected frame; the harness never jumps to the next sync.

`W` has valid SACCH CRC6 and wrong FACCH CRC12 checks; `P` has wrong LICH parity;
`S` has all valid channel checks; `C` has all wrong checks. Nominal parity input is
C C W P W W. Actual search results, including incidental rejected candidates,
determine which registered path was exposed.

| Observed path | Cases | Baseline following W | Candidate following W |
| --- | ---: | --- | --- |
| Exact adjacent W/P/W, initially unconfirmed | 2 | Confirms prematurely | Remains pending; next consecutive W confirms |
| W/P, then one or two incidental rejected LICH candidates, then W | 6 | Confirms prematurely | Remains pending; final W confirms |

The primary gate counts **only the two exact adjacent cases**: payload0, fast
acquisition off, both chunk sizes. The other six are useful extended rejection
paths, not additional instances of the registered adjacent triplet. They remain
in the raw evidence. A missed following W could not have passed as a correction:
the same source ordinal, complete returned dibits and correct channels are
required, followed by the next W confirming without an intervening body/reset.

The two direct exposures return 0,0,2,2 in baseline and 0,0,0,2 in candidate for
W/P/W/W. Results mean unconfirmed, historical confirmation without current proof,
and confirmed with current-frame evidence for values 0,1,2 respectively. Rejected
P itself returns zero here. Stale helper evidence on that path is not counted as
a fresh proof. The actual dispatcher verdict and profile-proof stamp are checked.

## Results and controls

For each role's 64 observed cases:

- 348 dispatched frames: 284 complete 182-dibit bodies and 64 eight-dibit LICH
  rejections. 300 frames are attributable to intended source ordinals; 48 are
  incidental rejections and remain explicitly unattributed.
- Of 336 nominal frames in nonzero-input cases, 36 are not decoded as intended
  bodies by either policy: 28 initial C frames and eight first-post-gap W frames,
  all with fast acquisition off. The candidate adds no source-frame loss; this
  does not imply complete acquisition of every source frame.
- 852 channel CRC observations and 2,365,440 consumed source samples. There are
  no skipped/backwards/invented sample deliveries and no EOF-truncated frames.
- Every attributed body's actual per-dibit boundary matches its nominal source
  boundary exactly. Attribution additionally requires full dibit equality and
  membership in that body's own consumed-sample trace.
- All 16 strong source frames remain decoded. Consecutive-weak and sticky
  strong/P/weak controls retain their observed outcomes. Neither policy reports
  current proof on the all-bad-CRC or zero-input controls.
- 96 real no-carrier calls complete, including initial entry and gap handling.
  Every pending/confirmed gap case actually clears its preceding confirmation
  state during the registered gap. The gap spans samples 12160–60160; reset
  occurs at consumed frontier48160, including the actual outer-loop follow-up.
- Optional observers leave common engine outcomes unchanged. Chunk sizes give
  the same source identities, channels, verdicts and reset outcomes. Provider
  read-ahead remains recorded separately from consumption.

Guarded hardware start/tune counts are zero. Direct backend rate/reacquisition
operations are also zero in this matrix; instrumentation of those operations
does not claim they were exercised. Real elapsed clocks run, but fast sample
replay is not a real-time RF timer test. No CPU or latency improvement is graded.

## Reproduction and review

The [Linux release and sanitizer run](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36162158675)
and its [PR counterpart](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36162164150)
pass. Reopening verifies 2,680 Linux file hashes and all four uploaded executable
identities. Comparing both Linux modes with Windows gives exactly matching
24,976 event rows and 512 per-invocation sample traces. The implementation
checkpoint has 47 successful checks and one skipped external review.

An independent auditor reconstructs all twelve encoded vectors and sixteen
waveforms byte-for-byte, reopens 60 pre-execution and 1,341 final-manifest hashes,
and audits all 256 Windows invocations without importing the study's encoder,
runner or analyzer. It recomputes all 1,704 observed CRCs and finds no measurement
or quality discrepancy. Both roles have 192 passing and 660 failing CRCs; current
proof returns fall from 104 to 96 because eight following-W frames correctly stay
pending until the next consecutive W. Decoded channel bits do not change.

An initial audit-only assumption incorrectly demanded nominal slicer decisions
even on incidental false syncs. Its original code/output is retained. The final
audit records the actual 142 incidental dibit differences across 20 rejected
frames per observed role, leaves them unattributed, and checks they produce no
current proof. Exact source/channel equality remains mandatory for every credited
intended frame. Neither the native matrix nor its registered checker was rerun
or changed for this audit correction.

Both ordinary baseline and candidate frame-routing regressions pass. Eight
framework counterexample tests pass normally and with Python optimization.
They reject skipped following frames, incidental bodies/resets between required
frames, truncated/forged source identities, empty controls, negative-source proof
and observer changes; timeouts retain their attempted outputs. Measurement
validity remains separate from hypothesis/progression gates.

Independent pre-execution review verified private-vs-real symbol ownership and
the absence of the old force-fast-acquisition research macro. It caught source
hash omissions, vacuous controls, insufficient source attribution, incomplete
reset/adjacency gates, missing event grammar and a reversed test-only verdict
fixture; these were fixed before the first native matrix. Initial Windows build
failures were missing real external-link dependencies and an imported-target
scope, corrected before execution. All diagnostics are retained. No native
matrix was retuned or repeated to obtain a favorable result.

## Integration boundary

This advances the private reliability fix to product-integration review. It does
not promote the optional faster-acquisition setting to the default. Before the
next APK/EXE, preserve these studies against their immutable original frame source,
integrate the exact measured accounting change, rerun applicable product checks,
and verify package identities and settings compatibility. New hardware, damaged
sync/sample slips, mixed protocols, overlapping signals, complex I/Q, scan-row
tuning, live audio and Android device execution remain separate acceptance gates.

All thirteen RC1/RC2 artifact/verification hashes and the original production
frame-handler source are unchanged at this research checkpoint.

## Published evidence

[Machine-readable results](evidence/nxdn-engine-gap-2026-09-25.json) include the
registered outcome, independent audit, cross-platform comparisons, executable
identities and release-preservation checks. The
[raw evidence archive](evidence/nxdn-engine-gap-2026-09-25-raw.zip) contains
4,061 entries / 88,359,333 bytes: all Windows and Linux attempts, frozen binaries,
source floats/vectors, sample traces, compiler/link identity, pre-execution
reviews, initial/final independent audits and build diagnostics. Every entry
was reopened and hash-checked. SHA-256:
`ba7a7b3c2d8fd22a22f9b091bf756ef683c207bb31f62f7583791268971b6704`.
