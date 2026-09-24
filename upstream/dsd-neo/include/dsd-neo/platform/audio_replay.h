// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef XERAX_AUDIO_REPLAY_H
#define XERAX_AUDIO_REPLAY_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Bounded, process-local, 60 seconds of received PCM at 48 kHz mono.
 * Silent gaps are omitted. Never capture replay playback through this API. */
void dsd_audio_replay_capture(const int16_t* pcm, size_t frames, int rate, int channels);
size_t dsd_audio_replay_snapshot(int16_t* pcm, size_t capacity, int seconds);
void dsd_audio_replay_clear(void);
double dsd_audio_replay_seconds(void);
/* Suppress only the physical live sink. Decoding, recording and this ring continue. */
void dsd_audio_live_suppress(int enabled);
/* Independent range-scanner gate; never clears replay/worker suppression. */
void dsd_audio_range_suppress(int enabled);
int dsd_audio_live_suppressed(void);
uint64_t dsd_audio_received_frames(void);
uint64_t dsd_audio_nonzero_frames(void);
/* Frames accepted by the output API, normalized to 48 kHz; not proof of sound. */
void dsd_audio_note_output(size_t frames, int sample_rate);
uint64_t dsd_audio_output_frames(void);
void dsd_audio_note_gap(void);
uint64_t dsd_audio_gap_count(void);
#ifdef __cplusplus
}
#endif
#endif
