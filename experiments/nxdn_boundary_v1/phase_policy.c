// SPDX-License-Identifier: GPL-3.0-or-later
#include "phase_policy.h"

#include <string.h>

static int
same_context(const nxdn_boundary_v1_context* a, const nxdn_boundary_v1_context* b) {
    return a->owner == b->owner && a->generation == b->generation && a->profile == b->profile
           && a->sps == b->sps && a->rf == b->rf;
}

void
nxdn_boundary_v1_reset(nxdn_boundary_v1_state* state) {
    if (state) {
        *state = (nxdn_boundary_v1_state){0};
    }
}

/* UNARMED is also returned for an initially absent stamp. Other non-pattern
 * reasons describe the invalidation that occurred in this call. */
static nxdn_boundary_v1_reason
validate_lifetime(nxdn_boundary_v1_state* state, const nxdn_boundary_v1_context* now) {
    if (!state || !now) {
        nxdn_boundary_v1_reset(state);
        return NXDN_BOUNDARY_V1_BAD_ARGUMENT;
    }
    if (!state->valid) {
        return NXDN_BOUNDARY_V1_UNARMED;
    }
    nxdn_boundary_v1_reason reason = NXDN_BOUNDARY_V1_UNARMED;
    if (!now->eligible) {
        reason = NXDN_BOUNDARY_V1_INELIGIBLE;
    } else if (!now->confirmed) {
        reason = NXDN_BOUNDARY_V1_UNCONFIRMED;
    } else if (!same_context(&state->anchor, now)) {
        reason = NXDN_BOUNDARY_V1_CONTEXT_CHANGED;
    } else if ((uint32_t)(now->symbols - state->anchor.symbols) > 395U) {
        reason = NXDN_BOUNDARY_V1_EXPIRED;
    } else {
        return NXDN_BOUNDARY_V1_EXPECTED_WINDOW; /* Lifetime valid, not a phase verdict. */
    }
    nxdn_boundary_v1_reset(state);
    return reason;
}

int
nxdn_boundary_v1_note_frame(nxdn_boundary_v1_state* state, const nxdn_boundary_v1_context* begin,
                            const nxdn_boundary_v1_context* end, int result) {
    if (!state || !begin || !end) {
        nxdn_boundary_v1_reset(state);
        return 0;
    }

    /* Check both endpoints before deciding whether an old stamp may survive.
     * New proof below is independent of any prior stamp or confirmation. */
    (void)validate_lifetime(state, begin);
    (void)validate_lifetime(state, end);
    if (!begin->eligible || !end->eligible || !end->confirmed || !same_context(begin, end)) {
        nxdn_boundary_v1_reset(state);
        return 0;
    }
    if (result != 2 || (uint32_t)(end->symbols - begin->symbols) != 182U) {
        return 0;
    }

    state->anchor = *end;
    state->valid = 1;
    return 1;
}

static int
phase_window(uint32_t age) {
    if (age >= 9U && age <= 11U) {
        return 1;
    }
    if (age >= 201U && age <= 203U) {
        return 2;
    }
    if (age >= 393U && age <= 395U) {
        return 3;
    }
    return 0;
}

static int
pattern_kind(const char* pattern) {
    static const char* const relaxed[] = {
        "3331331131", "3131331111", "3331331111", "3131311131",
        "1113113313", "1313113333", "1113113333", "1313133313"
    };
    if (!pattern) {
        return 0;
    }
    if (strcmp(pattern, "3131331131") == 0 || strcmp(pattern, "1313113313") == 0) {
        return 1;
    }
    for (unsigned int i = 0; i < sizeof(relaxed) / sizeof(relaxed[0]); ++i) {
        if (strcmp(pattern, relaxed[i]) == 0) {
            return 2;
        }
    }
    return 0;
}

nxdn_boundary_v1_decision
nxdn_boundary_v1_decide(nxdn_boundary_v1_state* state, const nxdn_boundary_v1_context* now,
                         const char* pattern, int enabled) {
    const int kind = pattern_kind(pattern);
    nxdn_boundary_v1_decision decision = {0};
    decision.allow = 1;
    decision.canonical = kind == 1;
    decision.valid_before = state && state->valid != 0;
    if (decision.valid_before && now) {
        decision.age = (uint32_t)(now->symbols - state->anchor.symbols);
    }
    decision.reason = validate_lifetime(state, now);
    decision.valid_after = state && state->valid != 0;
    if (!decision.valid_after) {
        return decision;
    }

    decision.window = phase_window(decision.age);
    if (kind == 1) {
        decision.reason = NXDN_BOUNDARY_V1_CANONICAL;
    } else if (kind == 0) {
        decision.reason = NXDN_BOUNDARY_V1_UNKNOWN_PATTERN;
    } else if (decision.window != 0) {
        decision.reason = NXDN_BOUNDARY_V1_EXPECTED_WINDOW;
    } else {
        decision.reason = NXDN_BOUNDARY_V1_OFF_PHASE;
        decision.would_block = 1;
        decision.allow = enabled == 0;
    }
    return decision;
}

const char*
nxdn_boundary_v1_reason_name(nxdn_boundary_v1_reason reason) {
    switch (reason) {
        case NXDN_BOUNDARY_V1_BAD_ARGUMENT: return "bad_argument";
        case NXDN_BOUNDARY_V1_UNARMED: return "unarmed";
        case NXDN_BOUNDARY_V1_INELIGIBLE: return "ineligible";
        case NXDN_BOUNDARY_V1_UNCONFIRMED: return "unconfirmed";
        case NXDN_BOUNDARY_V1_CONTEXT_CHANGED: return "context_changed";
        case NXDN_BOUNDARY_V1_EXPIRED: return "expired";
        case NXDN_BOUNDARY_V1_CANONICAL: return "canonical";
        case NXDN_BOUNDARY_V1_UNKNOWN_PATTERN: return "unknown_pattern";
        case NXDN_BOUNDARY_V1_EXPECTED_WINDOW: return "expected_window";
        case NXDN_BOUNDARY_V1_OFF_PHASE: return "off_phase";
        default: return "unknown_reason";
    }
}
