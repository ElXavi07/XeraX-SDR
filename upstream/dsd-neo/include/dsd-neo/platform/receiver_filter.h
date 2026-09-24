// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <stdint.h>
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef struct {
    uint64_t frequency;
    double ctcss;
    int dcs; /* -1 any; octal code stored as integer */
    int inverse;
    int color; /* -1 any */
    int slot; /* 0 both; 1/2 */
    uint32_t talkgroup; /* 0 any */
} dsd_receiver_filter;
/* Bounded frequency rules, copied atomically. No pointers into Qt objects. */
void dsd_receiver_filters_set(const dsd_receiver_filter* rules, size_t count);
int dsd_receiver_analog_allowed(uint64_t frequency);
int dsd_receiver_digital_allowed(uint64_t frequency, int dmr, int color, int slot, uint32_t tg);
#ifdef __cplusplus
}
#endif
