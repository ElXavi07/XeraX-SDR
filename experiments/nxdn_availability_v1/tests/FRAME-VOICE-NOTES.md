# Private frame and voice availability contract

This implements only the frame/voice portion of registration
`76e175aef1b8f30431c07cb3d4a50d431b858c02`. It is not linked into a product
target and does not change synchronization, confirmation rules, channel FEC,
vocoder algorithms, or privacy policy.

The frame stores a fresh 182-entry availability map, populated by one checked
read for each logical dibit attempt. A complete LICH is required before any
interpretation. Its rejected/incomplete path retains the existing frame-end
confirmation accounting, including a possible historical confirmed return of
1 rather than fresh proof of 2. After an accepted LICH the original 174 body
attempts are retained, including unsuccessful attempts after the input ends.

Each control decoder is invoked only when its entire original source range is
available. SACCH/SCCH use dibits 8..37; CAC uses 8..157; FACCH2/UDCH uses
8..181; FACCH3/UDCH2 uses 38..181. FACCH/PICH halves use 38..109 and 110..181.
A complete earlier control range remains eligible even if later input is absent.

`nxdn_voice_masked` uses bits 0..3 for the four original 36-dibit word positions
at 38, 74, 110 and 146. It intersects availability with the existing LICH voice
selection through the original slot loop. A missing word is skipped before
matrix mapping, vocoder/media processing, search-state changes, PCM copying and
audio dispatch. No compaction or replacement samples are introduced. The legacy
`nxdn_voice` API retains its complete-buffer contract and passes mask 15. The
frame avoids file opening/closing and voice timestamps when no selected word is
available. It does not invalidate a complete early word because a later read
failed.

## Dedicated tests and limits

`frame_voice.cmake` expects `CANDIDATE_DIR` and `XERAX_DSD` from the isolated
parent build. It registers `NXDN_AVAILABILITY_FRAME` and
`NXDN_AVAILABILITY_VOICE`, enables `NDEBUG`, and uses explicit checks rather
than disabled assertions. Tests retain the existing routing, confirmation,
rejected-LICH, reliability and audio-mapping assertions.

- Voice: all 16 masks, selectors 0..3, hard/soft paths and integer/float audio
  dispatch (256 cases). Independently calculated matrix positions, original
  slot identity, soft reliability, call counts and unchanged buffers/state for
  empty masks are checked.
- Frame: each missing LICH position with and without historical confirmation;
  missing first/middle/last dibits in each control range; all selected masks
  across NXDN48/96 option and positive/inverted sync state; no empty-word file
  activity; a fresh map on the next frame; complete SACCH and complete word 0
  retained at a later body end.

The frame tests use channel-decoder spies and real unchanged confirmation and
bit-packing helpers. Voice tests use vocoder/audio spies, not a speech decoder.
Variant/polarity settings exercise routing state only, not RF demodulation or
polarity recovery. Real checked-reader acquisition is tested independently.
These tests establish no playback, RF, timing, speech-quality, encrypted-slot
history, or whole-receiver result. The registered receiver matrix is separate.

## Implementation preflight record

Dedicated GNU C11 Release/NDEBUG compilation uses `-O2 -Wall -Wextra -Werror`.
The first voice compile passed. The first frame link failed because its test
target omitted the existing `convert_bits_into_output` implementation; the
failure is retained at
`build/nxdn-availability-agent-unit/frame-compile-1.log`. The target was corrected
to link unchanged `src/core/util/bit_packing.c`, and the second frame compilation
passed. Both dedicated test executables then exited 0; their first outputs are
retained in the same directory as `voice-test-1.log` and `frame-test-1.log`.
A subsequent explicit range-safe cast in the selected-mask expression does not
change its values; the final frame test output is retained separately as
`frame-test-final.log`. The successful compiler commands emitted no text, so
PowerShell's output pipe created no success-compile log files; their exit codes
were observed in the tool results and their executable outputs remain on disk.
No receiver, encoder, historical matrix, or app build was invoked by this
frame/voice subtask. MSVC and the combined candidate build are not established
by these local GNU test results.
