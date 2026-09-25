# Observation-v2 preflight

This is a new observation-only experiment registered at `0243ac6`. The earlier
216-invocation recovery study remains frozen and failed. No released source,
decoder decision rule, setting, input or release artifact is changed.

## Inputs and independent source review

Inputs were generated once after registration. An independent Python oracle
imports neither the generator nor decoder. It reconstructs 2,761,752 binary
bytes, accounts for all 35 files, and verifies nine waveforms and the exact
18 base cases / 36 invocation grid. Manifest SHA-256:
`c1433cbded3233b24b501ce318578c0e7a2cadc5b9260a7530663920309cbf5c`.

The valid/wrong SCCH fixtures encode 25 zero information bits and checkwords
17/81 respectively. Complete frame SHA-256 values were calculated independently
before inspecting generator output:

- Valid: `e49e9872c987d580c76ba274aca18137767ca9db452a8e6f0a508a156411b4c1`
- Wrong: `fb1afd6934f61d552131f84a635789fbae9d57f8537527cc9edc59cbeed00137`

The preflight verifies exact byte equality as well as hashes. These fixtures have
no independently established speech truth.

[DSD-FME's pinned CRC7 implementation](https://github.com/lwvmobile/dsd-fme/blob/719d9709e6d4c738be70183616b7b87081b50776/src/nxdn_deperm.c#L291)
corroborates the all-ones initialization and polynomial x^7+x^3+1, with
[25 information bits and seven check bits](https://github.com/lwvmobile/dsd-fme/blob/719d9709e6d4c738be70183616b7b87081b50776/src/nxdn_deperm.c#L888).
The retrieved file hash is
`aae26e450b73a5b74db70e6ee8e0cb99c6e6115e77aa9dfab4b8bc54b34e3c0f`.
Shared ancestry limits this corroboration: it is not independent standards
certification. The retained independent oracle uses polynomial long division,
explicit convolution history, matrix transposition and a separate PN recurrence.

## Native build and forwarding

A fresh Windows x64 Release target compiles the real continuous engine, DSP,
protocol, vocoder and audio staging. Four private generated C files introduce
observation hooks only. Original source bytes must match `938c5fe` exactly.
Unique-substitution guards reject missing or repeated seams. The original
observer and production files are untouched. Warnings are errors; all 381 build
steps pass. No native experiment was run during build/preflight.

Executable: 10,637,824 bytes, SHA-256
`a92511f7e1ece923d8b848d8658dc2d9a2e8bcafdc445e859295859672226afc`.
Link map SHA-256:
`ba3ba280f199a5280936266aab84561d4282fec3c00e2c5ecc65f8927e03b233`.
Thirteen required symbols resolve to the expected real/private objects. Each
wrapped voice, soft-vocoder, audio and dibit call forwards once with unchanged
arguments. SCCH records final results after fallback; LICH records actual flags.

The linked static mbelib-neo package is 2.1.0, with package source metadata pinned
to `be5992dab7589aec6f3a45fa1881139c0caa2a97`; archive SHA-256 is
`28007fa92e61618526c876656291d671f7d8bf41cc5ff8117bbe6702ac95088f`.
Its archive and package metadata are retained. The build has identities for 36
configured link archives; the map establishes specific selected implementations,
not that every member of every archive is used. Configured compile-command source
hashes likewise include targets not built for this experiment.

## Pre-execution corrections retained

The initial link audit expected bare object names for executable-owned objects,
but the map includes the target-directory prefix. The exact expected full paths
were corrected before execution; the original failed audit is preserved. This
changes no symbols, native code or binary.

Independent analyzer review found two unsupported assumptions before execution:
accepted voice LICH alone does not require a voice call without confirmation;
and a soft-pass result cannot end with unequal final CRC values if no fallback
ran. The checker is corrected and counterexamples cover these contradictions.
Pre-correction analyzer/test snapshots are preserved. The native instrumented
binary, input set and registered measurement gates remain unchanged.

Malformed anchor events now fail the projection without aborting remaining
registered attempts. Projection may remove new telemetry and mark old EOF-only
positions unavailable; it may not hide body, checkword, state or valid-position
changes. Prior raw anchors are compared without rerunning the old executable.

## Interpretation boundary

Internal PCM observations are post-gain/clamped float buffers and staged short
buffers at the fixed 8 kHz output rate. Counts, energy, a completed vocoder call
or zero reported errors do not establish valid speech or playback. Hardware and
audio/file output remain disabled. The scope does not include hard-vocoder or
right-channel hooks, arbitrary output rates, legitimate voice retention, physical
RF/phones, complex-IQ recovery, decoder speed or an application update.

After all preflight reviews and checker tests pass, freeze the harness revision,
binary, inputs, dependencies and build records before exactly 36 fresh processes.
Retain every outcome and failure. A pass would validate this bounded measurement
contract only; it cannot rehabilitate the previous study or promote a decoder.
