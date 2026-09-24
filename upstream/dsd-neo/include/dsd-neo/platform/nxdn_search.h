// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Experimental voice-pattern inference, not cryptographic authentication.
 * One decoder thread owns each context. UI settings/status are synchronized. */
typedef struct {
    uint64_t epoch, frequency, source, target;
    unsigned generation;
    int ran, kid, variant;
    unsigned sequence, count, cursor, candidate_at;
    uint16_t candidate, key;
    uint8_t positions[8], prefixes[8];
    uint8_t pending, ready, applied;
} dsd_nxdn_search_context;
typedef struct {
    uint64_t epoch, frequency, source, target;
    int ran, kid, variant, cipher, established, manual_key;
    int position, position_valid, errors;
} dsd_nxdn_search_input;
typedef struct {
    int enabled, status, key, frames;
    uint64_t age_ms;
} dsd_nxdn_search_status;
enum { DSD_NXDN_SEARCH_WAITING=0, DSD_NXDN_SEARCH_SEARCHING=1,
       DSD_NXDN_SEARCH_CANDIDATE=2, DSD_NXDN_SEARCH_USING=3,
       DSD_NXDN_SEARCH_SUPPLIED=4, DSD_NXDN_SEARCH_UNSUPPORTED=5 };
void dsd_nxdn_search_enable(int enabled);
int dsd_nxdn_search_enabled(void);
void dsd_nxdn_search_get(dsd_nxdn_search_status* result);
/* Returns 1 only if THIS payload was descrambled. Never changes supplied keys. */
int dsd_nxdn_search_step(dsd_nxdn_search_context* context,
                         const dsd_nxdn_search_input* input, char bits[49]);
int dsd_nxdn_search_audio_allowed(const dsd_nxdn_search_context* context);
#ifdef __cplusplus
}
#endif
