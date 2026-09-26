# NXDN weak-evidence continuity across rejected LICH

A bounded real-frame test reproduces a confirmation-accounting defect: an
unconfirmed receiver can combine weak CRC evidence from two frames even when a
rejected LICH frame occurs between them. A private candidate clears that pending
streak at the rejected frame while retaining an already-confirmed transmission.
Production source, APKs, Windows packages and user settings are unchanged.

This concerns **premature confirmation across a rejected attempt**, not a
fabricated CRC, an encryption result or a measured RF false-positive rate. Both
weak frames still have a genuine passing CRC6 of their own. Whether the same
sequence reaches the handler in a continuous stream requires another test.

## Registered input and result

[Preregistration](NXDN-LICH-GAP-PREREGISTRATION-2026-09-25.md): `04b942c`.
Isolated implementation: `170338d3b30b6a2aeee1c6f135f1d2d8479e0aa8`.
The frozen production frame handler's source is shared by RC2 and the baseline.
The candidate is generated into a separate build directory; its only behavioral
change moves frame accounting around all LICH outcomes.

The test supplies finite, independently encoded numeric dibits at a declared
frame boundary. Real LICH collection, whitening, channel deinterleaving,
convolutional decoding and CRC run. No CRC verdict is supplied by a stub.
Semantic dispatch and voice/file side effects are capture sinks. Two distinct
payloads run eleven fixed sequences with the observer both enabled and disabled.
Each executable records 152 steps and 180 observed channel CRC events.

`W` has valid SACCH CRC6 and deliberately wrong FACCH CRC12 checkwords. `S` has
valid checks on all three channels. `C` has three deliberately wrong checks.
`L` below represents each of bad parity, unsupported LICH or filtered direction.
`R` explicitly resets confirmation; it does not simulate an actual carrier loss.

| Sequence | Baseline handler results | Private candidate results |
| --- | --- | --- |
| W W | 0, 2 | 0, 2 |
| W L W W, each of three rejection types | 0, 0, 2, 2 | 0, 0, 0, 2 |
| W C W W | 0, 0, 0, 2 | 0, 0, 0, 2 |
| S L W, bad parity | 2, 1, 2 | 2, 1, 2 |
| W R W W | 0, reset, 0, 2 | 0, reset, 0, 2 |
| S R W W | 2, reset, 0, 2 | 2, reset, 0, 2 |
| S S | 2, 2 | 2, 2 |
| L L W W, bad parity | 0, 0, 0, 2 | 0, 0, 0, 2 |
| S C W | 2, 1, 2 | 2, 1, 2 |

Results mean: 0 = unconfirmed, 1 = sticky transmission confirmation without
current proof, 2 = confirmed with this frame's own CRC evidence. The baseline
bridges all six initially unconfirmed gap cases (three rejection types times
two payloads); the candidate prevents all six. The following second consecutive
weak frame still confirms. Already-confirmed transmissions remain confirmed.

For both policies, rejected LICH consumes eight dibits and produces no channel
CRC events. Accepted bodies consume 182 dibits. Channel information, computed
and received CRCs, fallback choices and consumed input bytes match across builds.
The observer does not alter outcomes. No voice request or input overread occurs.
At the third frame in the six gap cases, the candidate also leaves both scanner
hold clocks unchanged because confirmation remains pending. This checks the
handler's clock writes; it is not a full scanner test.

The baseline's stored per-frame evidence can also remain stale after rejection.
The helper that reads that field is specified for use after closing accounting,
which the early-reject baseline path does not do. We retain that raw state but
do not grade it as new proof: the actual rejected handler still returns 0 or 1,
never 2. Six premature confirmations are counted at the subsequent W, not L.

## Measurement integrity and limits

The [Linux release and ASan/UBSan run](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36157294935)
and its PR counterpart both pass. All 152 parsed steps per executable match
Windows exactly. Reopening verifies 96 recorded file hashes across the three
pairs and the identities of all four downloaded Linux executables. The branch
has 45 successful checks and one skipped external review at this checkpoint.

An independent raw-data auditor reconstructs all twelve numeric-dibit vectors,
checks all 304 Windows rows, and recomputes all 360 CRC events without importing
the generator or measurement policy. It finds no discrepancy and independently
verifies the six subsequent-W transitions, controls, input consumption and the
candidate's narrowly limited source change.

The six framework tests pass normally and under Python optimization. Negative
framework cases include valid H0, a poor candidate, an unrelated baseline
control failure, tampered observations, duplicates/missing rows, timeout,
malformed JSON and missing fields. Measurement validity is independent of the
hypothesis and candidate-quality gates. Every attempted native output is retained.

Before the first native pair, independent review caught and corrected literal
pointer subtraction, a gate that conflated H0 with invalid data, incomplete
failure reporting, an omitted baseline-control gate and a self-hash issue.
Initial Windows build diagnostics are retained: an unsupported warning flag,
missing include propagation and missing archive/thread dependencies were fixed
before execution. The first native pair passes both registered gates without
retuning or a native retry.

This does not run synchronization, symbol timing, complex I/Q, a warm continuous
stream, full engine dispatch, superframe assembly, real audio or physical radios.
The adapter deliberately presents the next supplied frame at its boundary even
after rejecting the previous LICH; it is not claiming to recover past the unread
body. Full engine no-carrier/reset hooks, incidental frames or a missed intended
frame could prevent this sequence in practice.

Next gate: preregister a finite continuous-stream and engine-dispatch study that
retains every sample, records actual dispatched frame identities and reset paths,
and compares runtime acquisition off/on without retuning the source after a
failure. Ordinary routing/regression checks must also exercise the candidate
before product integration. This result changes no released default and makes
no CPU, audio clarity or over-the-air performance claim.

## Published evidence

[Machine-readable results](evidence/nxdn-lich-gap-2026-09-25.json) retain both
policy outcomes, limitations, executable identities and release preservation.
The [raw archive](evidence/nxdn-lich-gap-2026-09-25-raw.zip) contains 133 entries /
8,761,388 bytes, including Windows and Linux outputs, frozen executable copies,
vector bytes, measured source, independent audit, build diagnostics and CI records.
Every ZIP entry was reopened and hash-checked. SHA-256:
`21f8c0c60ea2044084a5694fd0231c6b0949f0c2551a6f040973c0c25408e5ad`.

All thirteen RC1/RC2 artifact/verification hashes still match the earlier release
manifests. The original frame-handler source is unchanged. Full Windows build
cache files remain local with digests in the public manifest; exact commands and
the toolchain are included. This is evidence publication, not a new app release.
