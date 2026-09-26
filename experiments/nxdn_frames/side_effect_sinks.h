// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef XERAX_FRAME_SIDE_EFFECT_SINKS_H
#define XERAX_FRAME_SIDE_EFFECT_SINKS_H
#include <stddef.h>
typedef struct { size_t length; char bits[513]; } xerax_content_observation;
typedef struct {
    xerax_content_observation content[64];
    size_t count;
    int voice_requests, other_side_effects, errors;
} xerax_side_effect_observations;
extern xerax_side_effect_observations xerax_effects;
#endif
