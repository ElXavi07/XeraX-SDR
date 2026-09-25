# NXDN rejected-LICH evidence gap: preregistration

Baseline: publication commit `2ab607fe859eb1c9d535e1e7e3c7158a885075c9`.
No native run of this experiment has occurred at registration. Existing app
binaries, default settings and all earlier measurement matrices remain frozen.

## Hypothesis and bounded intervention

The local primary contract in `nxdn_confirm.h` says weak CRC evidence must occur
in two consecutive frames; the unit test explicitly requires an empty frame to
break that streak. In `nxdn_frame.c`, three early LICH rejection paths currently
skip both begin/end accounting. Hypothesis H1: weak / rejected-LICH / weak can
therefore confirm despite failing the documented consecutive-frame contract.
H0: the real frame handler or an intervening reset prevents that transition.
This study deliberately tests the frame-handler boundary; whether a particular
full engine path resets in between remains a separate integration question.

The only candidate change is in a private build copy of `nxdn_frame.c`: move
begin-frame accounting before LICH collection and close accounting at the common
END label, computing current proof there. Preserve the sticky transmission flag
across later rejected frames, and preserve valid consecutive weak and strong
confirmation. Do not modify the source used by APK/EXE builds. No filter, FEC,
CRC threshold, key behavior, acquisition policy or decoded channel bits changes.

## Inputs and fixed matrix

Use independently encoded numeric dibits with real LICH collection, whitening,
channel deinterleaving, convolutional decoding, CRC and confirmation. No injected
CRC verdicts. Reuse the previously independently audited encoder, pin its hash,
and explicitly compose two deterministic payloads: RAN 23 / IDLE / trailing
zeros, and RAN 37 / IDLE / trailing alternating 10 bits; FACCH IDLE payloads
have respectively zero or alternating trailing 72 bits. This is controlled
clear-channel data; no encrypted traffic or unknown keys.

W: passing SACCH CRC6 with both FACCH CRC12 checkwords deliberately wrong.
S: all three checks pass. C: all three checkwords deliberately wrong.
P: wrong parity on supported outbound LICH 0x41.
U: correct parity on unsupported LICH 0x7f.
D: correct parity on supported inbound LICH 0x40 with trunk filtering enabled.
R: explicit transmission confirmation reset, not an RF/carrier simulation.
All other frames use outbound LICH 0x41, PN95 seed 228, full reliability 255.

For each payload, run these eleven sequences from fresh state:

| Sequence | Steps |
| --- | --- |
| adjacent weak | W W |
| parity gap | W P W W |
| unsupported gap | W U W W |
| direction gap | W D W W |
| CRC gap | W C W W |
| strong then parity gap | S P W |
| explicit reset after weak | W R W W |
| explicit reset after strong | S R W W |
| adjacent strong | S S |
| rejected LICH before weak | P P W W |
| confirmed CRC gap | S C W |

Both baseline and candidate run the same matrix once, each with CRC observer
on and off to verify the observer does not affect state/results. Log every
step: source vector/consumed dibits, real CRC bits and outcomes, weak streak,
per-frame evidence, sticky confirmation, result, carrier, scanner clock-change
flags, voice/content request counts and errors. Fixed timestamps are unnecessary:
compare whether clocks changed from their sentinel values. No voice is in these
profiles; any voice request is a measurement failure. Rejected LICH must consume
exactly eight dibits and run no channel callbacks; body frames consume 182.

## Registered gates and interpretation

A valid measurement requires complete rows/traceable vectors, exact independently
expected channel information and CRC outcomes, no overread or fabricated body,
observer transparency, and unchanged production source hashes. Publish baseline
and candidate outputs even when progression fails. Never tune vectors after a
native outcome to obtain a desired result.

H1 is demonstrated at this component boundary only if baseline W P/U/D W confirms
at the third step while a consecutive-evidence oracle does not. Candidate passes
only if all sequences match that oracle, all three rejection types break an
unconfirmed weak streak, the next two valid weak frames can confirm normally,
strong CRC still confirms immediately, previously confirmed calls retain their
sticky flag through bad frames, and bad frames never return current proof.
Compare channel output bits/outcomes and consumption between builds exactly.
Baseline/candidate deviations for other sequences are failures, except stale
per-frame evidence is allowed to be cleared on early rejection. Preserve all
negative results and build diagnostics. Reproduce on Linux release and ASan/UBSan;
require independent review before considering a product patch.

No claimed RF false-positive rate, lost-sync rate, timing gain, CPU improvement,
voice benefit or complete NXDN conformance follows from this dibit test. The
study does not replace pending damaged-sync/slip, independent-IQ or full-engine
scanner/profile-feedback studies. An observed component bug is not evidence that
every application path exposes it. Leave RC2 default-off and artifacts intact.

## Frozen source hashes

- frame source SHA-256: `9022df4c611a129332123f7062a99e478ea4d24e0ce6f6a5104b5cc7fb191192`
- independent encoder SHA-256: `3e2c63b57dba137bbb35cdb9457a17deb9d0363fff8b8117e5d530e5990be9bd`
