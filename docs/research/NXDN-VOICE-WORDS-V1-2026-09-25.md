# Independent NXDN clear voice words: component gate passed

The independent arithmetic encoder and pinned external NXDN encoder agree on
all **8,266 channel words / 74,394 bytes**. The real production hard and soft
FEC functions satisfy every registered expectation in **27,044 calls**. This
establishes known source/channel words for future clear-call retention tests.
It does not change an APK/Windows decoder or establish correct audible speech.

## Registered scope and identity

[Registration](NXDN-VOICE-WORDS-V1-PREREGISTRATION-2026-09-25.md) was committed as
`784843e` before corpus generation or either native execution. The complete
harness/checkers were committed as
`3ae30bccc713af7a82ccd4310bda31e21d4c0d4a` before execution. Receiver baseline
`e8498d298ad1a6f85da93a8b07730ec99f7c1416` and existing releases are preserved.

There was one primary-encoder process and, only after its byte-exact agreement
gate passed, one production probe process. Both exited zero. No native retries,
discarded cases, adjusted inputs or post-outcome threshold changes occurred.
Measurement, content and preservation gates pass; product promotion is false.
Previous receiver matrices were not rerun.

| Frozen item | SHA-256 |
|---|---|
| Input manifest | `4d31e3d17c56162b706f9187f8f000bfbb0fce0f1e353f9ee2519bd66e355a84` |
| Primary-source manifest | `e5dda2c6b072ca4eda65d2c75c3f16550a6cafb52c8fd8e04f34c47363a24ca1` |
| Agreed channel bytes | `05ed6f2d7c548e6b6e94e81bb12534afde0c2e13301791a8f1d4d2778dd6eed3` |
| Primary executable | `b3276e18500dcad95cac8b347f032a14daecc35018859fac74c41d8daf302c4a` |
| Production probe executable | `4500157876aead15d956301dfd8fae56b1d9ba7e4893e6426a7274f4cdd3ab50` |
| Raw result report | `22e466257755e88281fc84987eb1a44687b9a51d2ac4af66a96fd9ae04df2c8b` |

## Corpus and independent construction

The external encoder is untouched [MMDVM-Host NXDNAudio.cpp](https://github.com/g4klx/MMDVM-Host/blob/590c531391dfd3146073afbc3956f70d42c62a46/NXDNAudio.cpp),
with [its Golay implementation](https://github.com/g4klx/MMDVM-Host/blob/590c531391dfd3146073afbc3956f70d42c62a46/Golay24128.cpp).
The separate Python implementation generates Golay parity with polynomial
arithmetic, generates the A-dependent B mask, and places bits arithmetically;
it does not read the native encoder's lookup tables or any decoder output.
These share protocol knowledge, so agreement is cross-implementation evidence,
not formal standards certification.

Known source words come from the pinned [NXDNClients announcement asset](https://github.com/g4klx/NXDNClients/blob/8950677e9876e577fb87b955cfa93bacd059209d/NXDNGateway/Audio/en_GB.nxdn)
and the silence unit in [Voice.cpp](https://github.com/g4klx/NXDNClients/blob/8950677e9876e577fb87b955cfa93bacd059209d/NXDNGateway/Voice.cpp),
plus zero/ones, 49 one-hot words and all 4,096 values of each protected source
field separately. The twenty announcement words, two silence words and
synthetic words retain duplicate identities. A final zero word completes the
paired encoder API. The original announcement's six unused padding bits are
preserved in provenance; encoder input normalizes them to zero.

The 4,133 input records total 53,729 bytes. Each represents two 49-bit source
words; each external output record supplies two 72-bit channel words. Every
byte agrees, including the final pairing word. The pinned upstream audio
`decode` routine is systematic extraction, not an error-correction oracle, and
was not used to judge production FEC.

## Actual production decoding

The probe uses the repository's `dsd_ambe_2450_dibit_map` and calls the actual
`mbe_decodeAmbe3600x2450Frame` and `mbe_decodeAmbe3600x2450SoftFrame` functions
from the installed mbelib-neo 2.1.0 static library. Independent link-map and
archive-symbol inspection identify both definitions in `ambe3600x2450.c.obj`;
neither is a test stub. The archive SHA-256 is
`28007fa92e61618526c876656291d671f7d8bf41cc5ff8117bbe6702ac95088f`.

Installed provenance pins [mbelib-neo](https://github.com/arancormonk/mbelib-neo/tree/be5992dab7589aec6f3a45fa1881139c0caa2a97).
The matching source tarball, portfile and metadata are retained. This does not
claim a fresh rebuild of that installed archive. It tests the actual component
used by the receiver, while bypassing synchronization, framing, routing,
synthesis and playback.

| Registered case group | Calls, including both modes | Outcome |
|---|---:|---|
| Clean words | 16,532 | Exact original 49 bits |
| One changed protected A channel bit | 3,504 | Exact original 49 bits |
| One changed protected B channel bit | 3,358 | Exact original 49 bits |
| One changed unprotected C channel bit | 3,650 | Exactly the corresponding source bit changes |
| Total | 27,044 | All registered expectations met |

Each single-bit mutation starts from a clean frozen channel word. Hard and soft
modes each receive 13,522 cases; soft reliability is fixed at 255, including the
deliberately changed bit. All returned statuses are nonnegative and input arrays
remain unchanged. No multi-bit tolerance, weak-RF or soft-versus-hard advantage
is inferred from these cases.

The single-error sweep covers all 72 transmitted positions in 73 base words;
the exhaustive A/B information-value sweeps provide additional clean coverage,
not an exhaustive cross-product of both fields and all error patterns.

The C cases are intentionally **not recovery of the original voice word**:
these source bits have no channel FEC in this mapping. The test requires their
changes to remain visible. Decoder success and plausible sound must never be
treated as proof that all original bits survived.

Observed counters reinforce that distinction: all C mutations return status
zero and zero error counts despite the changed source bit. Among 1,679 B
mutations per mode, 803 return zero and 876 return one in status/protected-error
count; all preserve the exact original source word. These are measured counter
distributions, not a new quality threshold or a claimed explanation of them.

## Validation and retained preflight corrections

Fifty-two framework tests pass locally and on Windows/Linux CI, normally and
with Python optimization. Negative controls include missing/duplicate/reordered
rows, incorrect mutation inputs, wrong source words, reversed protection
expectations, malformed JSON and failure-evidence retention. The result checker
does not import the encoder and independently reconstructs source identities.
[Push CI](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36182669076) and
[PR CI](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36182675273) test the
frozen harness commit; they do not run a Linux native decoder matrix.

A separate audit, importing neither checker nor encoder, reconstructs source
words and reads the pinned primary placement arrays to verify all 27,044 raw
rows. It confirms all 139 report-listed file hashes and all frozen/original/
configured/protected identity groups, including 41 protected historical paths.
Every frozen harness file matches the stated Git commit. Audit scripts, JSON,
notes and complete raw output are included in the evidence archive.

Preflight retained two macro-redefinition build failures (the first attempted
removal missed line endings), a missing MinGW thread-runtime link failure, and
the successful build. The redundant macro definition was removed and the real
thread runtime linked, with strict warnings retained. Before any execution,
review also corrected immediate persistence of attempted stages and added a
preservation check before launching stage two. No upstream primary encoder
source was changed.

## Consequence for the roadmap

The next gate is independently constructed complete **clear call** frames and
control transitions, with known source voice bits tracked through actual
receiver routing. Source review has already identified a tail puncture-list
bounds problem and uninitialized control-field storage in the external frame
builder; a separate registration must specify minimal deterministic corrections
and independent whole-frame corroboration. They were outside this voice-word
path and were neither exercised nor patched here.

The [failed boundary veto](NXDN-BOUNDARY-V1-2026-09-25.md) stays rejected. Its
off-phase valid frame must remain a mandatory retention control for a future
bounded history or parallel-hypothesis candidate. This study does not fix the
malformed-header PCM episode. Complete-call tests, impaired complex I/Q,
physical receivers/phones, human listening and installer execution remain
pending. RC3 Android/Windows packages and settings are unchanged. No timing,
GPU, whole-app speedup, decryption or perfect-decoding claim follows.

Raw evidence and independent audit: see the accompanying
[machine-readable publication index](evidence/nxdn-voice-words-v1-2026-09-25.json)
and [source/trace archive](evidence/nxdn-voice-words-v1-2026-09-25-raw.zip).
