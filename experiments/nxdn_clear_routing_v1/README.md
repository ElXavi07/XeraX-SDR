# Clear NXDN receiver routing and finite-input safety

This registered, isolated experiment follows known source bits through the real
receiver's FEC and synthesis-input boundaries. It changes observation only;
Android/Windows defaults and released packages stay unchanged. Read the
[registration](../../docs/research/NXDN-CLEAR-ROUTING-V1-PREREGISTRATION-2026-09-25.md)
before generating inputs or interpreting results.

The reference is the independently validated nine-frame AIR v1 sequence. Eight
waveforms cover primed/cold reception, a single weak frame, a LICH parity error,
zero input and three literal EOF prefixes. Nine option configurations, two
provider chunk sizes and detailed observation off/on produce 36 identities.
Each identity runs once, including unsuccessful attempts.

The recorder forwards real decoder/synthesis pointers once, records returned
source bits and actual synthesis inputs, and observes actual parent-frame slot
ownership. Nested FEC calls are separate from routed voice occurrences. Negative
returns expose unavailable results; uninitialized fields are never read.
Internal PCM and status flags are retained without claiming original speech.

The finite-safety gate examines each actual synthesis call's own 36-dibit slot.
A fully received early slot may be processed after the handler reaches EOF in
later slots. A synthesis call using unavailable samples fails the separate
safety hypothesis, even if its output looks plausible. The recorder does not
suppress real calls to make a gate pass.

Run the portable, non-native framework checks:

```text
python -m unittest discover -s experiments/nxdn_clear_routing_v1 -v
python -O -m unittest discover -s experiments/nxdn_clear_routing_v1 -v
```

`prepare.py` consumes the frozen AIR run and refuses an existing corpus path.
`prepare_build.py` verifies pinned originals and writes private observation
copies. CMake uses the existing actual receiver/dependencies; it does not invoke
an old matrix or compile the rejected boundary policy. The native runner requires
a committed harness, exact input identity and completed binary/linkage audit,
freezes dependencies, rechecks them before every invocation and retains failures.

Receiver quality and measurement integrity have separate gates. No receiver,
RF, I/Q, speed, intelligibility, privacy or application improvement may be claimed
solely because the framework runs or a decoder returns a successful status.
