# Isolated NXDN explicit-availability candidate

The [registration](../../docs/research/NXDN-AVAILABILITY-V1-PREREGISTRATION-2026-09-25.md)
fixes the candidate, twenty receiver identities and separate improvement gates.
All changes live here; product sources, defaults, settings and released packages
stay unchanged. Baseline inputs and traces are copied byte for byte, never
regenerated or replayed through the old executable.

The private candidate adds checked symbol/dibit reads with a per-call result,
local NXDN validity and complete control-block checks. Voice masks suppress
unavailable words before FEC, media activity and audio copying, while retaining
a complete early word after a later read fails. Legacy successful paths remain
available. This does not change synchronization or claim to repair the separate
loss of eight clean words following the exposed bad LICH.

Availability inherits existing input-adapter contracts. The registered tests
cover RTL discriminator/symbol input, finite headless WAV, binary/soft-binary and
float-symbol replay. Inherited Pulse and headful WAV fallback behavior remains a
separate limitation. This first candidate cannot certify every backend, source
generation change, encrypted missing-slot history, speech quality or app readiness.

`baseline_observer/` is copied from the immutable previous raw study and hash
bound. `prepare_build.py` generates forwarding-only observation over the actual
checked-reader and masked-voice APIs. It retains real FEC and synthesis wrappers;
tests with spies are clearly separate from that receiver target.

`prepare_inputs.py` copies the four active inputs, full cold anchor and cached
evidence. `analyze.py` independently verifies copies and real per-slot delivery,
known source bits and unchanged complete-input behavior. `run.py` requires a
committed harness, successful native contracts and source/linkage audit before
launching each new identity once. Actual failed outcomes are retained separately
from measurement failures. Product promotion stays false.

```text
python -m unittest discover -s experiments/nxdn_availability_v1 -v
python -O -m unittest discover -s experiments/nxdn_availability_v1 -v
```

Eight dedicated native contract targets cover acquisition/replay with and without
radio, actual datascope resets, and control/voice availability. They retain
original regression assertions and add missing-input cases; no test requires a
physical receiver. CI runs these contracts and evidence checks, never the native
receiver matrix. The observed candidate executable is a research tool, not a new
Windows installer or phone APK.
