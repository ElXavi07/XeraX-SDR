# Acquisition-conditioned NXDN boundary controls

This follow-up observes unchanged production logic with the previously audited
recorder. The [registration](../../docs/research/NXDN-ACTIVE-BOUNDARIES-V1-PREREGISTRATION-2026-09-25.md)
fixes four new signals: three literal cold-parent prefixes around the first
voice-slot boundary and one cold sequence with only V0's LICH parity changed.
Public fast acquisition is enabled; two chunk sizes and two observation modes
produce exactly 16 once-only native identities. Historical traces are read-only
anchors and are never rerun.

The checker independently reconstructs input bytes and observes real exposure,
per-slot sample availability, exact known source bits and real synthesis calls.
It separates actual receiver failures from measurement failures and does not
credit silence or lack of exposure as an active-voice safety success. An early
fully received slot remains eligible when a later slot is unavailable.

The corrected ERASURE/REPEAT/MUTE counterexamples use actual masks 32/64/128.
No accepted-speech metric, RF claim or app promotion follows from matching bits.
Frozen earlier code, its disclosed test limitation and failed results remain
unchanged. No decoder policy, APK, EXE release or setting is changed here.

```text
python -m unittest discover -s experiments/nxdn_active_boundaries_v1 -v
python -O -m unittest discover -s experiments/nxdn_active_boundaries_v1 -v
```

`prepare.py` refuses an existing corpus. `run.py` requires committed source,
hash-verified input, every historical preservation group and actual audited
decoder/runtime identities. It records each actual exit before the checker,
preserves failures and refuses native identity reuse. It performs no compilation.
