// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
// Single decoder-thread owner per process. Samples use signed-16-bit amplitude.
void dsd_analog_record(const char* directory, const float* pcm, size_t count, unsigned rate, uint32_t frequency, int open);
void dsd_analog_record_close(void);
#ifdef __cplusplus
}
#endif
