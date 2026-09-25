# NXDN48 recovery: retained negative measurement

The registered 216-invocation Windows matrix completed once. Every receiver
process exited zero, but the overall measurement and progression gates failed.
No new receiver patch, acquisition-default change or APK/EXE rebuild is justified
by this result. RC3 and the previous releases remain unchanged.

The two failures are useful engineering targets: a whole-symbol deletion can
redirect a valid control stream into another NXDN voice format, and the recorder
assigns misleading positions to symbols returned after input exhaustion. Neither
finding demonstrates an RF sensitivity change, intelligible audio or a new-key
decryption capability.

## Fixed design and evidence

[Preregistration](NXDN-RECOVERY-PREREGISTRATION-2026-09-25.md) was committed at
`38552e4b7d7391a79f4599ff9d6bbc2ce6601371`; the implemented harness was frozen at
`78b5846` before execution. [Preflight review](NXDN-RECOVERY-PREFLIGHT-2026-09-25.md)
independently reconstructs the encoded payloads, floats and sample maps. The
existing instrumented native candidate is reused unchanged, with acquisition
off/on, chunks 37/512 and observer off/on. Two held-out payloads cover damaged
sync, deletion/repetition of one or twenty samples, clean and negative controls.
Eight legacy invocations reproduce the original observer profile.

This is finite 48 kHz discriminator input with a known NXDN48 profile and matched
filtering disabled. It is not complex-IQ impairment or an installed-app execution.
Original sample indices and repetition occurrence labels remain immutable.
Source attribution does not require the returned payload to be error-free;
independent final CRC and exact source-information checks establish channel truth.

| Gate | Result |
| --- | --- |
| Registered invocations retained | 216/216; all native exit codes zero |
| Individual recorder inspections | 200 pass; 16 fail the audio-buffer guard |
| Legacy raw events and sample traces | All eight invocations match their frozen references |
| Observer common outcomes on inspectable pairs | No differences |
| Chunk equality | Six pairs fail on EOF body-position records |
| Frozen evidence and live executed Python sources | Preserved |
| Warm-recovery progression | Fails; no qualifying warm scenario |

## Whole-symbol deletion changes the interpreted channel format

All 16 audio-buffer failures are the declared `warm_drop20` case: two payloads,
two chunks, both acquisition options and both observation settings. The affected
frame's independently reconstructed received LICH is parity-valid full `0xEF`
(profile `0x77`), whereas the transmitted control LICH was full `0x83`
(profile `0x41`). The received profile selects IDAS RTCH2, SCCH and voice.

The call was already confirmed before the fault. The existing voice gate uses
that historical confirmation, so the affected frame enters voice processing and
changes audio-buffer indices from `[0,0,0,0]` to `[0,640,0,0]`. It ends with
current evidence zero, current proof zero and return value one. Thus this is an
unintended voice-path transition, not new current-frame proof or an effect unique
to the faster-acquisition option.

The recorder's channel callback covers SACCH/FACCH1, not the SCCH path selected
here. No recorded CRC event does not mean no CRC was attempted. Audio output was
disabled; the buffer indices do not establish nonzero PCM, audible output or
intelligible speech. The original guard failure and all raw results are retained.

## EOF instrumentation differs with reader chunk size

The six chunk differences affect payload 0's `warm_sync_invert`, `warm_repeat20`
and `cold_sync_blank`, each with acquisition off/on. Independent inspection finds
identical delivered-pop traces, returned dibits, CRC events and receiver outcomes.
Only body-position values after exhaustion differ inside an incidental truncated
frame. The common recorder calculates position from the last refill start plus
cache position; at EOF the cache position becomes zero while the last refill
start depends on chunk size.

These are not measurements of new delivered input. The decoder's real EOF flag
prevents attribution of the truncated frame. Nevertheless, exact chunk equality
was preregistered, so the measurement remains failed. The frozen inspector and
native run are not changed or rerun to turn this into a pass.

## Descriptive recovery observations, not a passed improvement claim

Among the 100 observed invocations passing their individual inspection, including
four legacy anchors, there are 690 frame records, 438 fully correct control
frames, 450 supported current proofs and 1,776 final CRC observations. Twelve
frames are truncated at EOF. No accepted channel in that inspected subset has
incorrect or unattributed source content. The other eight observed invocations
failed inspection and remain excluded from those counts, not silently successful.

Within the inspectable warm cases, both acquisition settings have the same
endpoint. Erasing one sync loses one 80 ms source frame for both payloads.
Inverting sync or repeating twenty samples leaves payload 0 without a credited
recovery before EOF; payload 1 resumes at source frame 6 after missing frames
4 and 5. Single-sample edits preserve the full source-frame sets in these cases.
Delivered and canonical endpoint differences remain separately recorded.

Independent inspection also explains the payload dependence: held-out payload 0
contains a sign pattern at dibit 137 that the real hunt matcher accepts as an
FSW variant. The following bits decode as parity-valid full LICH `0x90`, profile
`0x48` (Japanese DCR), so after these faults the receiver repeatedly dispatches
at the wrong position. Payload 1 lacks that accepted pattern at the same
position. The warm misaligned dispatches retain historical return one; they do
not obtain current proof. This is a real recovery failure in the fixed source
sequence, separate from the EOF recorder discrepancy.

Cold clean and single-sample cases retain the existing one-frame (3,840 samples,
80 ms of source duration) first-acquisition difference. This is neither a CPU
speed measurement nor a warm-recovery advantage. It cannot satisfy the registered
warm hypothesis, and the overall failed measurement prevents a promotion claim.

## Next bounded experiment

First add a new, separately versioned observation contract that distinguishes a
real consumed sample from a symbol returned after EOF. Preserve this study and
its guard failures unchanged. Add SCCH checkword outcomes, selected LICH format,
voice-buffer writes and decoder voice-error metadata so a corrupted header's
side effects can be measured without playing audio.

Then freeze clean control, independently grounded voice and corrupted-header
fixtures before proposing a guard. Test whether a bounded channel-consistency or
voice-validity check prevents the unintended transition while retaining genuine
control-to-voice changes. Requiring a fresh SACCH/FACCH checkword for every voice
frame is not assumed valid for all NXDN channel formats. A candidate must retain
legitimate voice and every previously correct control frame; a quiet decoder
that discards traffic is not an improvement.

Separately test a bounded recovery candidate for the payload-induced false-sync
cycle: any predicted boundary must come only from a previously validated frame,
expire promptly and pass the normal channel checks. Test stream breaks, genuine
format changes and independent payloads. Source truth must never enter the live
hunt decision. This is a hypothesis prompted by the failure, not an implemented
fix or evidence that boundary prediction will succeed.

Only after those observability and retention gates pass should a new native
candidate progress to independently impaired complex IQ and Android/Windows
packages. The [primary-source review](NXDN-RECOVERY-SOURCES-2026-09-25.md) documents
why earlier timing-loop proposals need measured justification. Physical receiver,
phone, listening and real-time timer tests remain pending.

## Reproducibility

[Machine-readable result](evidence/nxdn-recovery-2026-09-25.json) and
[raw evidence archive](evidence/nxdn-recovery-2026-09-25-raw.zip) retain every
invocation, failed audit, delivered trace, encoded vector, sample map, executable,
build/source records and independent reviews. The archive includes a per-entry
hash manifest and was reopened entry by entry. All 27 protected RC1/RC2/RC3 release
files and four receiver-source files retain their pre-execution hashes.
The raw archive contains 1,263 entries and 15,168,682 bytes; SHA-256
`67cb801b5b584af204bfdb937e235aa767ccbd88b5a58626ff1afec85e6af832`.
Independent review recomputes all 1,908 recorded CRC6/CRC12 observations across
the full observed matrix, including records from failed inspections, with zero
arithmetic discrepancies. That does not supply the missing SCCH observations.

The 26 Python framework checks pass normally and with optimization locally and
on Windows/Linux CI: [push](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36169309323),
[PR](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36169315964). Those CI jobs
test the evidence checker and mocked failure paths; they do not run this native
recovery matrix or establish Linux receiver results. No default or package is
promoted by framework-test success.
