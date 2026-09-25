// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef XERAX_NXDN_BOUNDARY_V1_PHASE_POLICY_H
#define XERAX_NXDN_BOUNDARY_V1_PHASE_POLICY_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Private research policy. Contexts are snapshots of actual receiver state, not
 * source-oracle coordinates. This helper owns no receiver state and has no global
 * mutable state. It makes no production integration or thread-safety claim: the
 * caller owns and serializes each policy state and reports every discontinuity. */
typedef struct {
    uint32_t symbols;
    uint32_t generation;
    int profile;
    int sps;
    int rf;
    int eligible;
    int confirmed;
    const void* owner;
} nxdn_boundary_v1_context;

typedef struct {
    int valid;
    nxdn_boundary_v1_context anchor;
} nxdn_boundary_v1_state;

typedef enum {
    NXDN_BOUNDARY_V1_BAD_ARGUMENT = 0,
    NXDN_BOUNDARY_V1_UNARMED,
    NXDN_BOUNDARY_V1_INELIGIBLE,
    NXDN_BOUNDARY_V1_UNCONFIRMED,
    NXDN_BOUNDARY_V1_CONTEXT_CHANGED,
    NXDN_BOUNDARY_V1_EXPIRED,
    NXDN_BOUNDARY_V1_CANONICAL,
    NXDN_BOUNDARY_V1_UNKNOWN_PATTERN,
    NXDN_BOUNDARY_V1_EXPECTED_WINDOW,
    NXDN_BOUNDARY_V1_OFF_PHASE
} nxdn_boundary_v1_reason;

typedef struct {
    int allow;
    int would_block;
    int canonical;
    int window; /* 0 outside; 1, 2, 3 for inclusive 9..11, 201..203, 393..395. */
    uint32_t age; /* Modular distance from pre-decision anchor; 0 if unarmed. */
    nxdn_boundary_v1_reason reason;
    int valid_before;
    int valid_after;
} nxdn_boundary_v1_decision;

void nxdn_boundary_v1_reset(nxdn_boundary_v1_state* state);

/* Returns 1 only when this frame arms a new end-of-body anchor. An unproved or
 * incomplete frame can retain an existing compatible, confirmed, unexpired
 * anchor, but never refreshes it. A newly proven frame may start unconfirmed.
 * Callers must separately reset on discontinuities hidden between snapshots. */
int nxdn_boundary_v1_note_frame(nxdn_boundary_v1_state* state,
                                const nxdn_boundary_v1_context* begin,
                                const nxdn_boundary_v1_context* end, int result);

/* pattern is a NUL-terminated string; only exact ten-character known words are
 * classified. Null or unknown patterns fail open. Lifetime invalidation runs
 * even when disabled. enabled changes only allow, never would_block or tracking.
 * Lifetime failure reasons take precedence over pattern reasons; canonical is
 * classified independently. */
nxdn_boundary_v1_decision nxdn_boundary_v1_decide(nxdn_boundary_v1_state* state,
                                                  const nxdn_boundary_v1_context* now,
                                                  const char* pattern, int enabled);

const char* nxdn_boundary_v1_reason_name(nxdn_boundary_v1_reason reason);

#ifdef __cplusplus
}
#endif
#endif
