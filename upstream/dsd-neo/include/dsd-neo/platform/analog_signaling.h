// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef struct { uint64_t serial; uint32_t source, target, fleet, opcode, frequency; char protocol[20], detail[96]; } dsd_signal_event;
void dsd_signaling_feed(const float* samples,size_t count,int rate,uint32_t frequency);
void dsd_signaling_reset(void);
int dsd_signaling_latest(dsd_signal_event*);
int dsd_signaling_pop(dsd_signal_event*);
int dsd_signaling_two_tone(double a,double b,int a_ms,int b_ms);
// Parsers accept fully framed, deinterleaved bytes / on-air block bits; CRC is mandatory.
int dsd_signaling_mdc(const unsigned char* info,size_t count,dsd_signal_event*);
int dsd_signaling_fleet(const unsigned char* bits,size_t count,dsd_signal_event*);
#ifdef __cplusplus
}
#endif
