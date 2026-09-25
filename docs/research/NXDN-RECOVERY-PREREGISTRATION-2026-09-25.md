# NXDN48 recovery after damaged sync and sample slips

Registered before generating or executing the new native input matrix. Preserve
RC3 release `04c0ed3e4e4689bc5ee483cc432c4dc6c4ea62db`, its APK/EXE packages,
settings and defaults. No new native algorithm is proposed in this experiment.

## Hypotheses and receiver boundary

Compare the public faster-acquisition option off/on in the same frozen,
continuous-engine candidate executable. H1: it preserves correctly decoded
source frames and avoids false content while recovering a complete valid frame
at least 70 ms earlier after one of the declared warm faults. H0 includes no
warm benefit: the shortcut only acts while unconfirmed, so cold-acquisition
gains alone do not pass H1. Report actual no-carrier-reset and no-reset strata.

The native executable already contains the measured frame correction integrated
into RC3. Reuse Windows SHA-256
`ace9de618e098fe4878607fc43ad0d0480c3a7e80f225b5bae7ea880900882fe`.
Its source lineage is frozen in the continuous-engine study at
`54a2f85b08109525dbe57f1fa02dffa567e32b19`; reproduction tree
`9b6cf5c4c41d3d5f9496039b14e008435bbf4249` includes the same harness.
Before execution preserve the executable, DLL dependencies, map, build commands,
source records, new scripts and all inputs. Verify that the RC3 frame equals its
measured candidate after CRLF-to-LF conversion only and that other native engine
sources have not changed. This is an instrumented engine experiment, not an
execution of the distributed APK or desktop GUI.

The real loop, synchronization, dispatcher, channel FEC/CRC and no-carrier reset
run. Inputs are finite 48 kHz discriminator floats, 2400 symbols/s, four levels,
20 samples/symbol, profile known in advance. Matched filtering, scanner/trunking,
audio and RF backend startup stay disabled as in the frozen engine study.
Deletion/duplication at this boundary models a delivered-sample discontinuity;
it is not complex-IQ noise, multipath, oscillator drift or hardware-dropout proof.

## Frozen inputs and new matrix

Reuse the independent encoder at SHA-256
`3e2c63b57dba137bbb35cdb9457a17deb9d0363fff8b8117e5d530e5990be9bd`,
derived and previously cross-checked against MMDVM-Host commit
`590c531391dfd3146073afbc3956f70d42c62a46`. Do not invoke or weaken the old
hash-bound preparers against changed production source.

Two held-out clear control payloads use RAN 11 and 53. SACCH information is
two zero structure bits, six RAN bits, message `0x10`, then ten bits `0x155`
or `0x2D3`. FACCH1 information is message `0x10`, then 72 bits
`0x123456789ABCDEF012` or `0xFEDCBA9876543210AB`. LICH remains `0x41` with correct
parity. S frames have valid SACCH and both FACCH1 CRCs; C frames deliberately
flip one checkword bit before convolutional encoding in all three channels.
Use the frozen encoder's whitening, tail, puncture and interleave conventions.

Preamble is 32 alternating dibits (1,3), each held 20 samples. Frames contain
192 dibits; trailer is 64 dibits of level 0. Apply the previous centered
eight-sample moving average, then the declared fault. Fault sample coordinates
below refer to the immutable pre-fault waveform. Frame ordinals are zero-based.

| Scenario | Sequence | Fault after waveform shaping |
| --- | --- | --- |
| warm_clean | CCSSSSSS | None |
| warm_sync_blank | CCSSSSSS | Set frame 4's first 200 samples to zero |
| warm_sync_invert | CCSSSSSS | Negate frame 4's first 200 samples |
| warm_drop1 | CCSSSSSS | Delete 1 sample at frame 4 start + 217 |
| warm_repeat1 | CCSSSSSS | Insert an extra copy of the next 1 sample at that coordinate |
| warm_drop20 | CCSSSSSS | Delete 20 samples at frame 4 start + 217 |
| warm_repeat20 | CCSSSSSS | Insert an extra copy of the next 20 samples at that coordinate |
| cold_clean | SSSSSSSS | None |
| cold_sync_blank | SSSSSSSS | Set frame 0's first 200 samples to zero |
| cold_drop1 | SSSSSSSS | Delete 1 sample at frame 0 start + 97 |
| cold_repeat1 | SSSSSSSS | Insert an extra copy of the next 1 sample at that coordinate |
| bad_crc | CCCCCCCC | None |
| zero | CCCCCCCC | Replace the entire shaped waveform by zero; no source-frame truth |

For repeat-k at q, delivered data are `x[:q] + x[q:q+k] + x[q:]`.
Warm slips therefore affect the LICH boundary, not a payload-only FEC block.
Keep every delivered sample's original index and occurrence. A repeat can move
backward in original coordinates, but the native delivered-index trace must
remain strictly increasing. Frame/source timestamps are not rebased after a
fault. Report delivered frontiers and original-coordinate mapped frontiers.

For each of these 26 waveform/payload cases, run option 0/1, chunk 37/512 and
observer 0/1, each in a fresh process: 208 invocations. The two zero waveforms
are identical replicated controls, not independent signal realizations.
Additionally repeat exactly eight frozen candidate invocations for the prior
payload-0 clean_weak waveform, comparing their raw events and pop traces with
the archived same-option/chunk/observer files. Total: 216 invocations. These
anchors verify reuse of the observer; do not rerun the old complete matrix.

## Measurement and truth gates

The original inspector SHA-256 is
`76983513a67931f22347bc97b33e676a26f2350e6ab520c17f0ac5104136ee7b`.
Reuse its finite-source, event partition, sample-pop lineage, independent CRC,
observer and reset checks. Add a separate adapter; leave original bytes intact.
Source attribution uses body-frontier locations mapped back to the immutable
waveform, with the existing strict one-symbol boundary interval (-20,20).
Do not require returned dibits to equal transmitted bits before crediting FEC.
Record ambiguous, incidental, truncated and unattributed frames explicitly.

The hook reports final post-fallback information/checkwords. Independently
recompute every CRC. Final acceptance is computed == received; soft-pass and
fallback flags are diagnostic, not the final correctness criterion. A correct
channel must also match its attributed source information and transmitted CRC.
Count a full recovered control frame only when all three expected channels are
correct. A partially recovered frame may support current proof through a correct
channel; it is not automatically a false proof merely because another channel
failed. Conversely, one good channel must not hide a different CRC-passing wrong
channel: every false accepted content event is a separate quality failure.

Check confirmation/return accounting from actual final evidence and prior state
where the registered observed channel paths permit it. A first weak CRC6 alone
does not prove an unconfirmed call; historical return 1 is not new proof.
Unexpected paths without sufficient observed evidence remain ungrounded and
cannot support a success claim. Unsupported current proof, false accepted content
and negative-control acceptance must all be zero for a quality pass.

Observer on/off common outcomes must agree. Both chunk sizes must retain the
same semantic events and exact delivered-pop traces per option. Every legacy
anchor must byte-match its frozen events/trace. A native timeout, malformed trace
or missing anchor is measurement failure, not a poor-receiver result; preserve
the failure and do not alter inputs or retry to rescue it.

## Retention, warm exposure and improvement

For each option-off correctly recovered source frame, option-on must retain that
source frame and decoded truth, with completion no more than 20 delivered samples
later. Report all differences and censored outcomes, including extra failed
dispatches and body consumption. Keep full-frame and partially supported proof
counts separate.

Warm cases require an actually attributed and currently proved frame 3 with
confirmation in both options, and no reset between that prefix and arrival at
the fault. Otherwise label the exposure incomplete, with no warm recovery claim.
Record subsequent real resets rather than manufacturing a reset. The first full
correct frame after the fault is the recovery endpoint; record both its ordinal
and absolute consumed frontier. Also report improvement versus the matched clean
scenario for each option so cold-start differences cannot masquerade as recovery.

H1 requires all measurement/quality/retention gates and at least one nonclean warm
fault with >=3360 delivered samples (70 ms) improvement in all four held-out
payload/chunk comparisons. Report cold gains separately with the same threshold.
Null or negative warm results are retained. Even a pass qualifies further
independent impaired-IQ research, not default-on promotion, RF performance,
audio latency, phone behavior or broad protocol claims.
