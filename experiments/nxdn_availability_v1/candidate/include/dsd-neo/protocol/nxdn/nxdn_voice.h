// SPDX-License-Identifier: GPL-3.0-or-later
/*
 * Copyright (C) 2025 by arancormonk <180709949+arancormonk@users.noreply.github.com>
 */

/**
 * @file
 * @brief NXDN voice decode entrypoint.
 *
 * Declares the voice handler implemented in `src/protocol/nxdn/nxdn_voice.c`.
 */

#ifndef DSD_NEO_INCLUDE_DSD_NEO_PROTOCOL_NXDN_NXDN_VOICE_H_
#define DSD_NEO_INCLUDE_DSD_NEO_PROTOCOL_NXDN_NXDN_VOICE_H_

#include <dsd-neo/core/opts_fwd.h>
#include <dsd-neo/core/state_fwd.h>

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

void nxdn_voice(dsd_opts* opts, dsd_state* state, int voice, uint8_t dbuf[182], const uint8_t* dbuf_reliab);

/* Bits 0..3 authorize complete source words at their original slot positions.
 * Missing slots perform no vocoder, media, history, or audio-buffer work. */
void nxdn_voice_masked(dsd_opts* opts, dsd_state* state, int voice, uint8_t dbuf[182], const uint8_t* dbuf_reliab,
                       uint8_t available_slots);

#ifdef __cplusplus
}
#endif

#endif /* DSD_NEO_INCLUDE_DSD_NEO_PROTOCOL_NXDN_NXDN_VOICE_H_ */
