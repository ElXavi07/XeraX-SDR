// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
// Extra receivers retain independent decoder state; capture storage is shared.
#define DSD_CHANNEL_LANES 4
typedef struct {
    uint64_t bytes, dropped;
    uint32_t source_hz, sample_rate, target_hz;
    int port, connected, error; // 1 overflow, 2 rate mismatch, 3 out of band, 4 source moved
    uint32_t output_rate;
    uint64_t source_bytes, source_age_ms; // age UINT64_MAX until first valid block
} dsd_channel_info;
void dsd_channel_reset_source(void); // call only after the capture thread stops
int dsd_channel_fits(uint32_t capture_hz, uint32_t rate, uint32_t channel_hz);
int dsd_channel_open(int lane);
void dsd_channel_close(int lane);
void dsd_channel_get(int lane, dsd_channel_info* out);
void dsd_channel_feed_cu8(const unsigned char*, size_t, uint32_t center, uint32_t rate);
// Phase accumulator is carried across blocks. Oscillator recurrence is normalized periodically.
void dsd_channel_translate(const unsigned char*, unsigned char*, size_t, double delta_hz, double rate, double* phase);
// Stateful anti-aliased frequency translation and power-of-two decimation.
// Returns null for unsupported ratios. Output capacity must be at least input bytes.
void* dsd_channel_filter_create(uint32_t input_rate, uint32_t output_rate, double delta_hz);
size_t dsd_channel_filter_process(void*, const unsigned char*, size_t, unsigned char*);
void dsd_channel_filter_destroy(void*);
void dsd_channel_worker_rate_set(uint32_t rate);
uint32_t dsd_channel_worker_rate(void);
#ifdef __cplusplus
}
#endif
