# Bounded relaxed-sync veto: first experiment

Register before generating the new input set or executing a native replay.
Baseline is the unchanged receiver at `56e83dd`, observed with the validated
observation-v2 contract. Keep the earlier 216-case failed recovery study, the
36-case observation study and all release artifacts unchanged.

## Hypothesis and candidate

H1: after a normally proven NXDN48 frame, temporarily declining relaxed sync
matches away from expected frame boundaries can break the measured payload false-
sync cycle without losing correctly decoded frames. H0 includes no improvement,
any baseline-correct frame loss, false proof or failed measurement. A deliberate
off-phase weak-sync transition is included because the proposed veto can plausibly
harm it; do not remove that control or weaken the retention gate after execution.

Only the isolated candidate changes matching policy. Preserve the existing
threshold-level blend. Before offset/lastsynctype/clock/warm-start mutation,
consider withholding one of the eight noncanonical tolerated NXDN sign patterns.
Both exact canonical polarities remain unrestricted everywhere. No synthetic sync,
changed FEC, changed CRC, voice gate, altered acquisition setting or source-truth
lookup is allowed.

A separate NXDN-only stamp is armed only by the real frame handler returning 2
after exactly 182 completed symbol increments, with matching begin/end receiver
identity, generation, profile, SPS and modulation and confirmed state at the end.
Do not reuse the generic profile-proof stamp as NXDN ownership. Eligibility is
the fixed conventional NXDN48-only, RTL discriminator, 20-SPS, rf_mod=2,
filter/scanner/trunk/datascope-off test profile. All other protocol modes are off.

From the proven frame-end symbol counter, allow relaxed matches only at unsigned
ages 9..11, 201..203 and 393..395. Expire strictly above 395 symbols. These windows
derive from ten sync dibits and a 192-dibit frame, with one-symbol slip tolerance.
The third opportunity allows the unchanged two-hit matcher to prime once and
then dispatch after a polarity/header disruption. The lifetime is about 164.6 ms
at 2400 symbols/s; it is a source-symbol bound, not measured wall-clock latency.

Unproved frames and rejected matches cannot refresh the stamp. Reset/carrier loss,
acquisition reset, profile changes, receiver identity/generation changes,
ineligible configuration, loss of confirmation and backward/expired counters
clear it. A newly proven complete frame may establish a fresh stamp. Unknown
patterns fail open. The baseline runs identical bookkeeping with veto disabled.
The research runtime owns one stamp for its single receiver; this is not a
production multireceiver/threading implementation.

## Fixed native matrix

Copy these exact frozen recovery inputs for each held-out payload h0/h1:
`warm_clean`, `warm_sync_blank`, `warm_sync_invert`, `warm_repeat20`, `bad_crc`,
and `cold_clean` (12 waves). Also copy h0 `warm_drop20` and h0 `zero` (two).
Copy the observation-v2 `scch_valid` and `scch_wrong` controls (two). Their voice
slots have no independent speech truth; they test retention of known plumbing.

Create exactly two additional h0 `CCSSSSSS` controls before execution. Both insert
100 zero-valued discriminator samples immediately before frame 4 in the unshaped
sequence, then apply the same centered eight-sample shaping to the full waveform.
The canonical control retains the original frame-4 FSW. The relaxed control flips
the sign bit (dibit XOR 2) of frame-4 FSW dibit index 1 before shaping, producing
the already-tolerated `3331331131` sign pattern. Keep the full LICH and all channel
bits unchanged. All remaining frame syncs stay canonical. Frames after the gap
have new declared source coordinates; independent input validation must reproduce
the exact bytes, maps, frame layout and unchanged channel bodies.

Total: 18 waveforms × chunks 37/512 × observation off/on × baseline/candidate =
144 fresh processes, once each. Fast acquisition is fixed off. Same compiler,
features, dependency libraries, driver-free finite provider and disabled audio/
file output. No native matrix runs before source/build/input/checker freeze.

The four copied observation-v2 waves (h0 warm_clean, h0 warm_drop20, scch_valid,
scch_wrong) provide 16 archived baseline anchors. Compare their original events
and sample traces exactly without executing the old binary again. Preserve all
attempts, preflight corrections and failures; never retry for a favorable result.

## Observation, checks and gates

Keep the existing stdout/common/per-dibit/LICH/CRC/voice observations unchanged.
A separate bounded policy log records real frame begin/end contexts, arming,
resets, matcher input and the actual decision in both observation modes. This
common diagnostic does not install the optional sample/CRC callback when off.
Bind the new symbols to their real/private implementations with a link map.

Before replay, test the pure policy on inclusive window boundaries, canonical
polarities, unknown patterns, baseline bypass, missing proof, 181/183-symbol
bodies, resets, identity/generation/profile/confirmation changes, backward counts,
and unsigned rollover. Pure-policy tests are not receiver or RF acceptance.

Extend input validation explicitly for existing inversion/repetition transforms
and the two pre-shaped gap controls. Preserve the frozen observation checker;
an adapter may independently verify these constructions and supply its existing
sample/CRC/ownership inspection with the already validated lineage. No change to
the old checker or its completed outcomes. Cross-check new policy decisions with
independent arithmetic, observed complete-frame proof and normal input counters.

Measurement requires all 144 identities, zero native/recorder errors, exact finite
sample traces, observer neutrality, chunk agreement, identical archived baseline
anchors and source/artifact preservation. Frame truth requires a complete sampled
body attributed to its declared source frame and exact expected returned body;
partial/EOF values cannot claim recovery. Compare supported current proof and
fully correct body sets, including clean control and SCCH/voice-plumbing retention.

Progression requires at least one improved post-fault correctly decoded source
frame in h0 sync-invert or repeat20, no previously correct source-frame loss in
any case, no extra false current proof, and no loss of the baseline's known voice
staging/control content on clean controls. Report any counterexample separately;
passing useful cases cannot override a failed aggregate retention gate.

Even a pass is a bounded discriminator screen, not legitimate voice certification,
complex-IQ/RF robustness, CPU/GPU speed, audible output or an app release. Further
independent voice/control changes, weak/noisy IQ and device acceptance must precede
promotion to APK/Windows defaults. Modern-key recovery is outside this work.
