# NXDN boundary prediction: useful recovery, failed retention

**Decision: reject this candidate for product promotion.** The registered
144-process experiment passes its measurement contract. A temporary sync veto
recovers two additional correct frames in each of two damaged-signal cases, but
also suppresses a complete, correctly decodable frame in the deliberately
off-phase control. That loss fails the predefined retention gate. The existing
APK/Windows release and acquisition defaults remain unchanged.

## What was tested

[Registration](NXDN-BOUNDARY-V1-PREREGISTRATION-2026-09-25.md) was committed as
`b3ee410655999bfc3499f6e6ff66b6e55c10b346`, before generating the two new controls.
Harness/checkers were frozen at `f89e78b80e631d4e7a2bf46bca4a8636a31f33ee` before
execution. The baseline preserves receiver behavior at `56e83dd`; both roles use
the same real protocol, DSP, engine and vocoder with playback disabled.

The isolated candidate remembers the end of a normally proven, complete NXDN48
frame. For at most 395 symbols, it declines eight already-tolerated noncanonical
sync patterns outside three narrow expected-boundary windows. Both exact sync
polarities remain allowed everywhere. Level tracking, two-hit synchronization,
FEC, CRC and voice routing remain unchanged. No source-truth lookup or fabricated
sync feeds the receiver. A separate single-receiver stamp avoids inheriting the
generic NXDN/dPMR profile-proof state.

Eighteen fixed waveforms, chunks 37/512, observation off/on and baseline/candidate
produce 144 fresh processes, once each. Sixteen waveforms are frozen copies;
two controls insert 100 zero-valued discriminator samples before frame 4 and
then apply the existing shaping. One retains canonical sync; the other changes
only sync dibit 1's sign. Its LICH and channel bodies remain identical. This is
an unannounced change of waveform timing, not a declared transport-generation
reset. All frame ordinals below start at zero.

## Measured outcome

The table lists fully sampled, exactly attributed bodies with all expected
channel information/checkwords correctly decoded. Both chunk sizes agree;
observation does not change receiver or policy outcomes.

| Test | Baseline correct frame ordinals | Candidate correct frame ordinals | Result |
|---|---|---|---|
| Payload 0, inverted sync | 2, 3 | 2, 3, 6, 7 | Two additional frames recovered |
| Payload 0, repeated 20 samples | 2, 3 | 2, 3, 6, 7 | Two additional frames recovered |
| Payload 0, blank sync | 2, 3, 5, 6, 7 | 2, 3, 5, 6, 7 | Same correct content |
| Payload 1, inverted sync | 2, 3, 6, 7 | 2, 3, 6, 7 | Same correct content |
| Five-symbol gap, canonical sync | 2, 3, 4, 5, 6, 7 | 2, 3, 4, 5, 6, 7 | Same correct content |
| Five-symbol gap, relaxed sync | 2, 3, 4, 5, 6, 7 | 2, 3, 5, 6, 7 | **Frame 4 lost: promotion fails** |

The counterexample is causal and directly observed. The candidate's real matcher
sees `3331331131` at symbol counter 815, 15 symbols after its proven end stamp of
800. That age is outside the registered 9–11 first window, so it declines the
match. The unchanged baseline accepts it and decodes the complete source frame:
SACCH CRC6 is 59/59 and both FACCH CRC12 results are 345/345. The candidate next
decodes frame 5. A larger favorable subset cannot override this loss. Widening
the window after seeing it would be a new hypothesis, not a pass of this study.

The earlier whole-symbol-deletion voice-routing problem remains. Both roles
stage four vocoder/audio blocks with 424 nonzero shorts out of 640 in that episode,
despite the bad SCCH check. Playback is disabled, and these synthetic voice slots
have no independent speech truth. This candidate therefore does **not** fix that
audio problem or establish crystal-clear speech. Known SCCH control and voice
plumbing are retained; that is a narrower statement than voice correctness.

## Evidence and limits

All 144 native exits are zero. Recorder checks, observer neutrality, chunk
agreement and all sixteen byte-exact archived baseline anchors pass. New policy
decisions are checked independently against real frame counters and final channel
evidence. The original 216-invocation recovery study remains failed and frozen;
the later 36-invocation observation study is likewise unchanged. Neither was
rerun. [Preflight checks and retained corrections](NXDN-BOUNDARY-V1-PREFLIGHT-2026-09-25.md)
preceded receiver execution.

Thirty-one Python framework tests pass normally and with optimization locally
and in Windows/Linux CI: [push](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36178176392)
and [PR](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36178183491).
The optimized pure C policy test passes locally on Windows and in Linux CI.
These CI jobs do not run a Linux receiver matrix. Explicit linked-library hashes,
generated sources, compiler/link records, input audits and every native attempt
are retained with the [machine summary](evidence/nxdn-boundary-v1-2026-09-25.json)
and [raw evidence](evidence/nxdn-boundary-v1-2026-09-25-raw.zip).

The raw archive has 1,064 entries and is 27,257,256 bytes; every entry was reopened
and compared with its manifest. SHA-256:
`9c2655bce75db02b8c4af6833db169b029f23900ad70a39ab6e9f0664b8494d0`.
Two independent result audits agree with the failed retention decision, verify
all 1,029 final-report file identities, and preserve all 27 release files plus
the protected receiver and earlier-study artifacts. The internal report hash is
`e090451d8aa220cde2bdc98d5d08b711450a00aa22f08ce26ad21fb22af7c88c`.

This is a finite Windows discriminator study. It measures recovered content,
not CPU speed, whole-app latency, RF sensitivity, complex-IQ robustness, human
intelligibility or phone performance. The runtime is intentionally isolated and
single-receiver. Hidden context changes between snapshots need explicit reset
ownership; endpoint checks alone do not solve arbitrary stream discontinuities.
No encryption recovery is attempted.

## Consequence for the next experiment

Bounded tracking has a primary-source precedent in the pinned MMDVM
[NXDN receiver](https://github.com/g4klx/MMDVM/blob/046e1df16105cbc33de3da7b7d6a03af402ed81d/NXDNRX.cpp)
and its [frame/rate definitions](https://github.com/g4klx/MMDVM/blob/046e1df16105cbc33de3da7b7d6a03af402ed81d/NXDNDefines.h).
That modem searches near a predicted boundary while tracking and eventually
expires lost synchronization. Its sample domain and receiver structure differ.
Our inference that a small veto might help was experimentally supported on two
faults, while the stronger no-loss hypothesis was falsified.

Next, establish independently encoded clear voice/control transitions, with
known source voice words rather than just nonzero PCM. Pinned
[NXDNClients voice construction](https://github.com/g4klx/NXDNClients/blob/8950677e9876e577fb87b955cfa93bacd059209d/NXDNGateway/Voice.cpp)
and [MMDVM-Host channel encoding](https://github.com/g4klx/MMDVM-Host/blob/590c531391dfd3146073afbc3956f70d42c62a46/NXDNAudio.cpp)
provide a possible independent path; their network records require proper air-frame
encoding and cannot simply be treated as RF frames.

Then preregister a bounded history or parallel-hypothesis experiment that can
retain an off-phase candidate while testing the expected boundary. Its gates
must include this new counterexample, all retained faults, strict memory/work
bounds, reset ownership, and exact clear voice/control retention. This is a
research direction, not an implemented improvement or release commitment.
