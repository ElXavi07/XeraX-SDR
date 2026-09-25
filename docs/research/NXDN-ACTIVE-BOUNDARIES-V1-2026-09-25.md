# Active NXDN boundaries: unavailable voice synthesis and recovery loss

The new 16-process experiment reaches the intended clear call, corrupted LICH
and partially delivered voice slots. Measurement, observation neutrality and
source preservation pass. **Finite voice safety and subsequent clean retention
fail.** These are receiver findings, not failed measurement infrastructure.

On truncated input, the real receiver calls speech synthesis for slots whose
samples were not fully delivered. After an exposed parity rejection, it correctly
rejects the damaged frame but retains only 12 of the next 20 known voice-word
occurrences. No product fix, default change or new APK/Windows package is claimed.

## Frozen scope

[Registration](NXDN-ACTIVE-BOUNDARIES-V1-PREREGISTRATION-2026-09-25.md) was committed
at `b3a8cee4608db93ba3bc446281ed1ded954a6270` before construction. The harness and
independent checker were committed at `2a5af570a71d03a7753c4d73ba11c0c379e2b165`
before execution. Exactly 16 new identities ran once; all exited zero.

The existing observer executable is reused byte for byte, with its real FEC and
synthesis linkage previously audited. There is no native rebuild, encoder run,
old matrix rerun or change to production logic. Its receiver source remains
`289a82f8fd9c0495b64bf948fd45413bc63261c4`. Four archived cold-fast traces are
checked read-only as 24-word anchors; they are not new trials.

The four inputs are three literal prefixes of the previously shaped cold
reference, ending at samples 6,159 / 6,160 / 6,161, and the same nine-frame cold
sequence with only V0 full-frame bit 34 changed before shaping. The complete
source oracle remains intact, including future samples that were never supplied;
those future entries cannot credit missing data. Independent reconstruction
checks all bytes, lineage and source words without importing the generator.

Each input uses the already available public fast-acquisition option, provider
chunks 37 and 512, and detailed callbacks off/on. These four combinations per
input check measurement stability, not independent RF trials. The data are clear
synthetic NXDN48 conventional discriminator samples at 48 kHz, not complex I/Q,
speech recordings, transmitted signals or encrypted traffic.

## Measured outcomes

Counts below are per process, identical across chunks and observation modes.
An exact word is credited only after establishing its source frame/slot identity
and complete delivered interval, then comparing original bits at the real FEC
return and synthesis input.

| Input | Frame dispatches | Real synthesis calls | Exact complete source words | Calls using unavailable slots |
|---|---:|---:|---:|---:|
| Prefix 6,159 | 2 | 4 | 0 | 4 |
| Prefix 6,160 | 2 | 4 | 1 | 3 |
| Prefix 6,161 | 2 | 4 | 1 | 3 |
| Exposed bad LICH | 8 | 12 | 12 of 20 clean survivors | 0 |

Across all 16 processes: 56 dispatches, 96 actual soft FEC calls, 96 actual
synthesis calls, 56 exact source-owned occurrences and **40 synthesis calls with
unavailable slot input**. The other 56 calls preserve their known source bits.
There are no hard or nested FEC calls in this path. These are internal processing
observations; device playback is disabled and intelligibility is not measured.

### Active finite-input failure

Every prefix first exposes the complete strong header and known clear call
(source 901, group 1201), then the accepted source V0 profile. All 182 attempted
V0 body reads are observed, including actual incomplete and empty intervals.

| Prefix | Complete body reads | First unavailable read | Later empty reads |
|---|---:|---|---:|
| 6,159 | 73 | Partial: 19 of 20 samples | 108 |
| 6,160 | 74 | Empty at first EOF | 107 |
| 6,161 | 74 | Partial: 1 of 20 samples | 107 |

Slot 0 requires body indices 38 through 73. It is incomplete at 6,159, complete
at 6,160 and still complete at 6,161. All later voice slots are unavailable.
Nevertheless, all four slots reach FEC and synthesis in every prefix. The single
fully delivered early slot in the latter two cases retains its exact original
bits even though later reads discover EOF.

This establishes two simultaneous requirements for a fix: suppress processing
of unavailable slots, and retain a complete early slot when a later slot is
missing. A global EOF test at synthesis time, or discarding the whole frame,
would fail the second requirement. Matching a returned bit string, status zero
or ordinary synthesis flags cannot establish that the input was received.

The source audit identifies the relevant path: a failed symbol read can return
numeric zero without completing a symbol; the dibit path can then slice an
ordinary value. NXDN collects its body before processing voice and does not
carry explicit per-read availability into each 36-dibit voice slot. A future
candidate needs an explicit read-completion result, not a symbol-counter delta,
signal reliability value or frame-wide EOF flag. This study changes none of
that behavior.

### Corrupted LICH and later recovery

The target V0 LICH is actually observed at its source position as `0xaf` with
parity rejection. It returns with no current proof or evidence and triggers no
target control decoder, FEC or synthesis. Sticky confirmation and frame return
value 1 remain; neither is incorrectly counted as acceptance of the rejected
frame. This negative restriction passes.

The subsequent clean-retention gate fails. V1 and V2's eight voice occurrences
are missing. The trace instead dispatches an off-source `0x5e` profile at body
sample 11,200 and consumes a complete body without voice. Canonical source
dispatch resumes at V3, body sample 16,200. V3, V4 and both FACCH half-steal
survivors supply 12 exact occurrences. The original known clear epoch persists
and the actual source trailer ends it with TERMINATOR; no trailer or identity
failure is inferred from the earlier losses.

The previously failed default-mode primer and unexposed bad-LICH result remain
unchanged. This acquisition-conditioned experiment answers their missing
exposure question; it does not rewrite the old gates or prove a recovery fix.

Source review shows that parity rejection clears the last-sync marker while
keeping confirmation. The first-canonical shortcut applies only while
unconfirmed. That makes an internal priming match plausible, but the frozen
recorder does not report every attempted sync match. The precise intervening
match sequence remains an inference; the off-source dispatch span and lost
source occurrences are directly recorded.

### Flags and separate gates

Ninety-two synthesis calls have flags `0x03`; four have `0x23`, including ERASURE
on source word 19 in the bad-LICH sequence. No REPEAT or MUTE occurs. All 40 calls
using unavailable slots have ordinary `0x03` flags, illustrating why flags alone
cannot validate source availability. Exact bits and zero return do not certify
accepted speech or playback.

Unlike the disclosed older test limitation, this separately frozen framework
tests the actual ERASURE/REPEAT/MUTE masks 32/64/128 before execution. It has no
accepted-speech metric. The old tests and their coverage limitation are preserved.

| Gate | Result |
|---|---|
| Input identity, measurement, callback/chunk neutrality, preservation | Pass |
| Actual strong-header, bad-LICH and partial-voice exposure | Pass |
| Exact routing of completely source-owned occurrences | Pass |
| Retention of every fully delivered early prefix slot | Pass |
| No processing of rejected V0 | Pass |
| Retention of all 20 later clean occurrences | **Fail: 12 retained** |
| No synthesis from incomplete or empty slots | **Fail: 40 calls** |
| Aggregate progression / product promotion | **False / false** |

The routing gate does not silently credit unavailable calls: they fail the
separate mandatory finite-safety gate. Likewise, zero eligible complete words
at prefix 6,159 cannot turn its retention result into a safety success.

## Validation and evidence

All **41 framework tests** pass normally and under Python optimization locally
and on Windows/Linux CI ([push](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36193709852),
[PR](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36193715105)). Tests include
wrong/repeated source identities, complete early-slot retention, partial/empty
ownership, failed parity exposure, later loss, changed bits, incomplete grids,
callback/chunk differences, real flag masks and once-only failure recording.
CI executes no native receiver matrix.

A separate raw-results audit imports no experiment checker and independently
checks actual sample intervals, source words, FEC/synthesis boundaries, metadata,
flags and preservation. Its 42,075 checks find no discrepancy with the failed
quality outcome. In particular, the incomplete slot 0 at sample 6,159 returns
FEC status zero while its last source bit changes from 1 to 0. This is retained
as an unavailable-input counterexample, never credited as a received word.

Preservation checks retain 240 frozen files, 1,638 original identities, 240
copied identities, 922 distinct configured source paths and 1,535 protected
historical identities. All 337 report-listed files remain unchanged. These
overlapping groups are identity checks, not a count of newly built objects.

The [publication index](evidence/nxdn-active-boundaries-v1-2026-09-25.json) and
[raw evidence archive](evidence/nxdn-active-boundaries-v1-2026-09-25-raw.zip)
retain all 16 attempts, complete inputs, events, actual sample-pop traces,
frozen source/binary provenance, preflight reviews, separate result review and
CI logs. The archive supports offline checker replay without a native run.
The included observer executable is a research tool, not an app update.

An [external publication audit](evidence/nxdn-active-boundaries-v1-publication-audit-2026-09-25.zip)
then verifies all 372 archive entries, all 371 manifest-listed payloads and 52
frozen Git source blobs. It reproduces all 16 saved audits and the final failed
comparison exactly through the extracted frozen checker, with 5,854 checks and
no native execution. This later audit is preserved separately to avoid a
self-referential archive hash.

| Identity | SHA-256 |
|---|---|
| New input manifest | `899bc2f55403b4b5f465dfbf8939d3dc396e86d197feef86654d3a6529b7a0c6` |
| Reused observer executable | `6682f833c9c9a9ec23b596af2c8fe3f176de28134a90f3f487e8ab996b464704` |
| Native report | `058cf74cb23a390d0815e20ae0a2faeb8cf8e2c4e2c4fee98beb04ac290864db` |

Next, separately freeze a small explicit-availability candidate and test it
against these already recorded baselines. Keep complete early-slot retention,
clean calls, both half-steal layouts and replay-mode compatibility mandatory.
Do not mix this fix with a new synchronization policy. Preserve the off-phase
recovery and malformed-header PCM counterexamples for their own acceptance
gates; unavailable-input protection alone cannot solve either one.

APK/Windows RC3, settings and defaults remain unchanged. Physical receivers,
phone playback, human intelligibility and independently impaired complex I/Q
remain pending. No CPU/GPU speedup, RF sensitivity or encryption claim follows.
