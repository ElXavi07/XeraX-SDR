// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef struct { double ctcss_hz; int dcs_code; int inverted; int dcs_inverse_code; } dsd_analog_tones;
void dsd_analog_tones_feed(const float*, size_t, unsigned rate, uint64_t channel, int enabled);
void dsd_analog_tones_get(dsd_analog_tones*);
void dsd_analog_tones_reset(void);
#ifdef __cplusplus
}
#endif
