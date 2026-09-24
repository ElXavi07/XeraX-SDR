// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
void dsd_equalizer_enable(int enabled);
int dsd_equalizer_enabled(void);
void dsd_equalizer_reset(void);
void dsd_equalizer_process(float* iq,size_t elements,int sps);
double dsd_equalizer_error(void);
void dsd_trial_configure(double offset_hz,int bandwidth_hz);
void dsd_trial_process(float* iq,size_t elements,int rate);
typedef struct { uint64_t sequence; uint32_t frequency,wacn,sysid,nac,talkgroup,source; int tdma,slot,priority; } dsd_dual_grant;
void dsd_dual_enable(int enabled);
int dsd_dual_offer(uint32_t frequency,uint32_t wacn,uint32_t sysid,uint32_t nac,uint32_t tg,uint32_t source,int tdma,int slot,int priority);
int dsd_dual_get(dsd_dual_grant*);
typedef struct { dsd_dual_grant grant; int modulation; } dsd_voice_tune;
int dsd_voice_tune_valid(const dsd_voice_tune*);
void dsd_voice_tune_result(uint64_t sequence,int status);
int dsd_voice_tune_status(uint64_t* sequence);
typedef struct { uint64_t checked[2], suspected_ras[2], rejected[2]; } dsd_dmr_evidence;
void dsd_dmr_ras_enable(int enabled);
int dsd_dmr_ras_enabled(void);
void dsd_dmr_evidence_reset(void);
void dsd_dmr_evidence_note(int slot,int suspected_ras,int fec_error,int crc_ok);
void dsd_dmr_evidence_get(dsd_dmr_evidence*);
#ifdef __cplusplus
}
#endif
