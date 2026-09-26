# Clear NXDN48 routing: measured acquisition loss, no product promotion

The registered 36-process experiment passes measurement and preservation, but
**fails progression**. The fixed header primer did not establish the expected
call: only 8 of its 24 transmitted voice-word occurrences reached the actual
FEC and synthesis-input boundaries. The corrupted-LICH control was not exposed
at its source location. Neither result is repaired by extending the sequence,
rerunning a case or selecting a favorable subset.

On the identical cold-start waveform, the existing optional fast acquisition
path routed all 24 known occurrences, compared with 8 using the default path.
Its first FEC call occurred 15,360 input samples earlier: **320 ms of this
48 kHz synthetic stream**. This is acquisition position, not CPU execution
time, a whole-app speedup or an RF sensitivity result. The option was already
present in RC3; this experiment implements observation only.

## Fixed execution and source truth

[Registration](NXDN-CLEAR-ROUTING-V1-PREREGISTRATION-2026-09-25.md) was committed
at `d98ccd32ddc6cb4fa15bae07a91cf33e144df445` before input construction and
building. The runner, observer and independent checker were frozen at
`9fd7e2c859b356b3e697ce95b800ca60e9c60bbc` before all 36 native invocations.
Each fixed identity ran once and exited zero. No older matrix was rerun.
The observed product baseline is `289a82f8fd9c0495b64bf948fd45413bc63261c4`.

The [AIR v1 reference](NXDN-AIR-V1-2026-09-25.md) supplies independently agreed
header, five pure-voice frames, both FACCH half-steal layouts and trailer. Its
20 distinct source words appear in 24 transmitted slots; repeated bit strings
do not define identity. The checker assigns identity using actual delivered
sample positions, frame location and slot, then compares the 49 source bits to
the real decoder return and the actual synthesis input. Detailed observations
also verify channel dibits, the 4-by-24 input matrix and reliability placement.
The second SACCH cycle remains partial.

Eight fixed waveforms produce nine configurations. Provider chunks 37/512 and
detailed callbacks off/on supply four observations of each configuration, not
four independent RF trials. The input is finite, shaped discriminator samples;
there is no complex I/Q, antenna, radio transmission or physical receiver test.
All source traffic is clear. There is no key search or privacy operation.

## Results

Counts below are per invocation and agree across both chunk sizes and detail
modes. Every actually source-owned routed word matched its source bits at FEC
and synthesis input; that fact does not establish intelligible speech.

| Configuration | Dispatched frames | Exact routed words / synthesis calls | Interpretation |
|---|---:|---:|---|
| Primed, default | 8 | 8 | H1 fails: scored header and early voice not retained |
| Cold, default | 7 | 8 | Late acquisition; first FEC at delivered sample 23,680 |
| Cold, public fast option | 9 | 24 | All nine source frames exposed; first FEC at sample 8,320 |
| Single weak frame, fast | 1 | 0 | Actual valid weak frame exposed; remained unconfirmed |
| Corrupted LICH, default | 9 | 16 | H3 fails: target corrupted LICH was not exposed |
| Zero input | 0 | 0 | No frame or voice acquisition |
| Prefix 9,999 | 2 | 0 | No active voice interval reached |
| Prefix 10,000 | 2 | 0 | No active voice interval reached |
| Prefix 10,001 | 2 | 0 | No active voice interval reached |

Across all 36 processes there are 160 dispatches and 224 real soft FEC calls,
224 routed words and 224 real synthesis calls. There are no hard or nested
FEC calls on this natural reliability-bearing path. Common receiver/FEC/call
observations agree with detailed callbacks enabled or disabled, and across
chunk sizes. This establishes callback neutrality for these instrumented
profiles, not equality with an entirely uninstrumented app.

The default primed run dispatches unsupported off-source LICH `0xf6` twice,
then an off-source `0x5e` profile. Its first four routed words have an unknown
call identity and audio permission zero. A later FACCH publishes source 901,
group 1201 and clear-call state; the trailer terminates that later-known epoch.
This does not satisfy the registered header-to-trailer retention gate. Internal
processing of unknown-call words is not evidence of speaker output: device
playback was disabled.

The cold fast configuration exposes the strong header, publishes the clear
call, retains both FACCH half-steal directions and ends that same epoch at the
trailer. Header processing leaves live RAN at its initial sentinel until the
next eligible SACCH, which publishes RAN 1 as expected. This descriptive result
does not replace the failed primary primed gate.

The corrupted bit changes acquisition behavior; the receiver subsequently
routes 16 intact source words. Because the expected bad-LICH source interval
was never dispatched, this is **not** evidence that a corrupted LICH was
accepted, nor does it pass the required parity-rejection exposure control.

H4 reports no synthesis using unavailable slot samples. However, all three
prefixes stop before any voice route is reached. Their zero synthesis count
means this batch **does not test active-voice EOF safety**. A future experiment
must actually expose a voice interval before assessing that boundary.

## Synthesis flags and a checker-test limitation

All actual FEC returns preserve the known bits with status zero. Synthesis
sets flag `0x20` (ERASURE) on source word 19, the fourth slot of the final pure
voice frame, in every voiced configuration. Thus 16 of the 224 synthesis calls
have flags `0x23`; the other 208 have `0x03`. No REPEAT or MUTE flag occurs.
Status zero and exact input bits do not make that erasure audible speech.
The record keeps these flags rather than substituting a success claim.

Post-execution review found that the framework's substitution-flag test uses
4/8/16, while the installed header defines ERASURE/REPEAT/MUTE as 32/64/128.
The frozen test is retained with this coverage limitation. The checker never
exports a speech-acceptance result, and its bit-routing gate intentionally does
not depend on synthesis flags. Supplemental review uses the actual constants;
it is explicitly post-execution and cannot retroactively establish complete
preregistered flag-test coverage. No frozen gate or outcome was edited.

## Validation and preservation

The read-only build audit verifies all 13 source pins, inverse observation-only
source transformations, actual object relocations and resolved wrapper call
targets. It identifies 354 existing compiled object translation units versus
1,341 configured compile-command entries, 36 linked archives, 434 dependency
hashes and four non-system runtime DLLs. The real installed mbelib archive is
the one validated in the earlier independent word study. No dummy vocoder,
private first-sync prototype or rejected boundary policy is substituted.

One native build failed before execution because the copied dispatch source
needed its original header directory. The failed build log and generated
sources are retained; the correction adds that include directory only. A
source-hash transcription, map filename and corrupted-frame metadata were
corrected before corpus execution, and an audit-only AST selector correction
is retained. None used receiver outcomes to tune the experiment.

All **43 framework tests** pass normally and optimized locally and on
Windows/Linux CI ([push](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36189961365),
[PR](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36189968629)). The flag-test
limitation above still applies; passing tests do not erase missing coverage.
CI checks evidence contracts and counterexamples, not a Linux receiver matrix.

Independent raw-result review verifies all attempts and the recorded identities:
142 frozen files, 531 originals, 142 copied identities, 922 distinct configured
source paths and 47 protected earlier artifacts. All 359 report-listed files
remain unchanged. Configured paths are deduplicated; that count is not the
number of compiled objects. No APK, EXE release, settings or older study changed.

## Evidence and next gate

The [publication index](evidence/nxdn-clear-routing-v1-2026-09-25.json) and
[raw source/trace archive](evidence/nxdn-clear-routing-v1-2026-09-25-raw.zip)
retain every attempt, input, common/detail event, sample-pop trace, source and
binary identity, failed preflight evidence, audit and CI log. Offline review
imports the frozen `analyze.py` under
`study/frozen/source_repository/experiments/nxdn_clear_routing_v1`; keep that
hierarchy intact for the pinned finite helper. No native rerun is needed.

| Identity | SHA-256 |
|---|---|
| Input manifest | `6ca26a31598d8bb9d701bb9f6eba19d783de7e00a3e0730be2ccd3f0b20b12eb` |
| Observed executable | `6682f833c9c9a9ec23b596af2c8fe3f176de28134a90f3f487e8ab996b464704` |
| Native report | `50a7dbb4b33200e203e102f58195110abedf6159ce02b66b551ebb2c65b74ab0` |

Next, separately register acquisition-conditioned parity and EOF controls that
actually reach their intended source intervals. Carry the failed fixed primer,
the previous off-phase recovery counterexample and malformed-header PCM case
forward; do not retune this completed matrix. Any subsequent history or parallel
hypothesis policy must preserve known call/slot content and bounded work.
Physical reception, independently impaired complex I/Q, human intelligibility
and application acceptance remain pending. Product promotion stays false;
Android and Windows downloads remain the existing 4.3.2 RC3 packages.
