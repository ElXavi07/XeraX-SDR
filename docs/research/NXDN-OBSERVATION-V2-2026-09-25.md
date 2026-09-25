# NXDN finite-input and voice-path observation results

The new observation contract passes all 36 registered Windows invocations.
It accurately distinguishes complete, partially sampled and empty dibit calls;
records actual LICH selection, final SCCH checkwords and internal audio staging;
and preserves the receiver outcomes in the archived comparison cases. This is
measurement infrastructure, **not improved decoding or a new application build**.
The previous 216-invocation recovery study remains frozen and failed.

## Registration, implementation and scope

[Registration](NXDN-OBSERVATION-V2-PREREGISTRATION-2026-09-25.md) was committed at
`0243ac6` before input generation or native execution. The
[preflight](NXDN-OBSERVATION-V2-PREFLIGHT-2026-09-25.md) records independent input,
source, forwarding and checker reviews, including corrections made before the
first invocation. Harness freeze:
`a07b3ab37ffcdc127d40fad9a48a043c6ffcb3f7`.

Nine fixed waveforms each run with provider chunks 37/512 and detailed observation
off/on; faster acquisition is fixed off. Each of the 36 fresh processes executes
once and exits zero. No receiver or input is retuned and no failed case is retried.
This is a 48 kHz **discriminator replay**, not complex-IQ or physical RF testing.
The real engine, frame/channel decoder, vocoder and audio staging execute, while
hardware startup and audio/file output remain disabled.

The fresh research executable is 10,637,824 bytes, SHA-256
`a92511f7e1ece923d8b848d8658dc2d9a2e8bcafdc445e859295859672226afc`.
Input manifest SHA-256:
`c1433cbded3233b24b501ce318578c0e7a2cadc5b9260a7530663920309cbf5c`.
The link map, generated source, build commands, dependencies and original source
identities are retained with the raw evidence. No released decoder source changed.

## Finite-input results

Across the 18 detailed invocations, 104 dispatched frames contain 14,212 completed
body-dibit calls, four partial EOF calls, six first empty EOF calls and 530 later
empty calls. Partial and empty calls receive no source-backed dibit position.
Exactly ten frames are truncated; none is credited with a complete source frame.

| Clean-wave cut (samples) | Completed calls in final frame | First unavailable call | Later empty calls |
| ---: | ---: | --- | ---: |
| 12,360 | 0 | Empty first LICH call | 7 |
| 12,361 | 0 | One real sample of first LICH call | 7 |
| 12,380 | 1 | Empty second LICH call | 6 |
| 12,521 | 8 | One real sample of first payload call | 173 |

Both chunks reproduce each boundary. The source-backed prefix remains observable,
but a returned dibit after EOF cannot manufacture missing input. These truncated
prefix frames retain historical confirmation and return 1, while current evidence
and proof remain zero. Historical confirmation is not newly verified content.

The copied `cold_sync_blank` case again ends inside a wrong-phase frame: 109
completed calls followed by one first empty and 72 later empty calls. The old
recorder assigned stale chunk-dependent positions to those last 73 returned
values. New positions are explicitly unavailable. Raw old records are retained;
their original failed comparison is not rewritten or reclassified as a pass.

## SCCH and internal audio results

The independent SCCH control returns all 25 expected information bits in both
chunks. Valid checkwords return computed/received CRC7 17/17 with a soft pass;
deliberately wrong checkwords return 17/81 after fallback, with no current proof.
Each control contains two V frames. The remaining voice bits are synthetic slots
with no independently established speech truth. The fixture validates observation
and known SCCH content, not speech or full standards conformance.

The retained whole-symbol deletion provides a more precise diagnosis of the
previously observed voice-path transition:

- Source LICH full `0x83` is received as parity-valid `0xEF`, profile `0x77`,
  selecting SCCH and voice=3.
- Final SCCH CRC7 is computed **1**, received **32**, after hard fallback. Current
  frame evidence/proof stay zero; the frame returns historical confirmation.
- The real pipeline calls voice once, the soft vocoder four times and audio
  staging four times. Of 640 staged short samples, **424 are nonzero**; the four
  blocks contain 0, 104, 160 and 160 nonzero samples. Peak magnitude is 18,430.
- Both chunks have identical diagnostics. Output remains disabled. These are
  actual internal samples, not proof of intelligible speech, successful vocoder
  acceptance or audible playback.

The valid and wrong-SCCH controls also stage audio under prior confirmation.
Their voice slots are identical, and so are their measured PCM diagnostics,
despite different channel checkword outcomes. This reinforces why PCM energy,
an invoked vocoder or sticky confirmation cannot certify a newly decoded frame.
It does **not** justify muting every legitimate voice frame lacking a fresh SCCH
pass; real voice/control-format retention needs a separate independent oracle.

All detailed invocations together record 162 CRC6/CRC12 events, ten SCCH CRC7
events, ten voice calls and forty soft-vocoder/audio calls. No nonfinite float
samples appear in the forty inspected internal 160-sample blocks. These counts
are diagnostics, not a speech quality score.

## Neutrality, checks and preservation

All 18 observer-on/off pairs preserve common bodies, state and per-call records.
Both chunks preserve common outcomes and identical delivered sample traces.
Twelve archived anchor invocations match after removing new telemetry and
marking only the declared old EOF positions unavailable. All original bodies,
CRC6/CRC12 values, decoder decisions, audio-index changes and real pop traces
remain equal; the old executable is not rerun.

Independent review recomputes all 172 final CRCs (54 CRC6, 108 CRC12 and ten
CRC7), verifies all frozen/source/input/anchor artifact identities, and checks
394,884 delivered sample indices. Per-call ownership is cross-checked using
common coordinates, symbol-completion counters and exact frame trace slices;
the raw pop trace does not contain a second independent call identifier.

Thirty counterexample/framework tests pass normally and under Python optimization
locally and on Windows/Linux CI:
[push](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36173450402),
[PR](https://github.com/ElXavi07/XeraX-SDR/actions/runs/36173459020).
Those CI jobs test the Python measurement framework only. The new native grid is
Windows-only. They do not establish Linux native, physical device or RF results.

Before/after checks preserve 27 RC1/RC2/RC3 release files, four protected receiver
sources and four previous-study artifacts. RC3 remains the current prerelease;
settings and acquisition defaults are unchanged. No new APK or installer is
warranted by observation-only code.

The [machine summary](evidence/nxdn-observation-v2-2026-09-25.json) and
[raw evidence](evidence/nxdn-observation-v2-2026-09-25-raw.zip) retain every
invocation, original failures from preflight review, checker revisions, source
and build identities, independent audits and the frozen input set.
The raw archive contains 317 entries and 9,033,903 bytes, SHA-256
`5235dff587781ce0a9757a3b052e51f591e47fda8bb31e8f28943387b702ee9c`.
Every entry was reopened and compared with the original bytes and archive manifest.

## Next experiment

This removes the observation obstacle to a separately registered recovery or
routing candidate. Prioritize a bounded expected-frame-boundary hypothesis for
the retained payload-dependent wrong-phase cycle, using only previously proven
sample history. Preserve an unchanged baseline and reject any invented provenance,
false proof or lost legitimate control/voice transition. A routing guard needs
independently valid voice fixtures before it can be promoted; a fresh-CRC rule
is not presumed correct for every supported NXDN format.

Modern-key recovery, GPU/whole-app speed, human intelligibility, weak RF,
independently impaired complex IQ and phone/hardware acceptance are not measured
here. Encryption work remains restricted to supplied authorized keys or controlled
test vectors. Product changes and builds follow measured improvement and retention
gates rather than this observation pass alone.
