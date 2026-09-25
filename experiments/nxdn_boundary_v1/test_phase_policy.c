// SPDX-License-Identifier: GPL-3.0-or-later
#include "phase_policy.h"

#include <stdio.h>
#include <string.h>

/* Explicit checks survive NDEBUG. This exercises only pure policy, not a native
 * decoder, stream provider, source-truth oracle or production integration. */
static int failures;
static int owner_a;
static int owner_b;

#define CHECK(condition) do { \
    if (!(condition)) { \
        fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #condition); \
        ++failures; \
    } \
} while (0)

static nxdn_boundary_v1_context
context(uint32_t symbols) {
    const nxdn_boundary_v1_context result = {symbols, 7U, 1, 20, 2, 1, 1, &owner_a};
    return result;
}

static nxdn_boundary_v1_state
armed(uint32_t endpoint) {
    nxdn_boundary_v1_state state = {0};
    nxdn_boundary_v1_context begin = context(endpoint - 182U);
    nxdn_boundary_v1_context end = context(endpoint);
    CHECK(nxdn_boundary_v1_note_frame(&state, &begin, &end, 2) == 1);
    CHECK(state.valid == 1 && state.anchor.symbols == endpoint);
    return state;
}

static void
test_windows_and_expiry(void) {
    static const struct { uint32_t age; int window; int block; int valid; } cases[] = {
        {0, 0, 1, 1}, {8, 0, 1, 1}, {9, 1, 0, 1}, {10, 1, 0, 1}, {11, 1, 0, 1},
        {12, 0, 1, 1}, {125, 0, 1, 1}, {147, 0, 1, 1}, {200, 0, 1, 1},
        {201, 2, 0, 1}, {202, 2, 0, 1}, {203, 2, 0, 1}, {204, 0, 1, 1},
        {317, 0, 1, 1}, {339, 0, 1, 1}, {392, 0, 1, 1}, {393, 3, 0, 1},
        {394, 3, 0, 1}, {395, 3, 0, 1}, {396, 0, 0, 0}, {UINT32_MAX, 0, 0, 0}
    };
    for (unsigned int i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
        nxdn_boundary_v1_state state = armed(1000U);
        nxdn_boundary_v1_context now = context(1000U + cases[i].age);
        nxdn_boundary_v1_decision d = nxdn_boundary_v1_decide(&state, &now, "3331331111", 1);
        CHECK(d.age == cases[i].age && d.window == cases[i].window);
        CHECK(d.would_block == cases[i].block && d.allow == !cases[i].block);
        CHECK(d.valid_before == 1 && d.valid_after == cases[i].valid);
        CHECK(d.canonical == 0);
        CHECK(d.reason == (!cases[i].valid ? NXDN_BOUNDARY_V1_EXPIRED
                           : cases[i].block ? NXDN_BOUNDARY_V1_OFF_PHASE : NXDN_BOUNDARY_V1_EXPECTED_WINDOW));
    }
    nxdn_boundary_v1_state state = armed(1000U);
    nxdn_boundary_v1_context now = context(1396U);
    (void)nxdn_boundary_v1_decide(&state, &now, "3331331111", 0);
    now.symbols = 1010U; /* Returning to an old coordinate cannot revive an expired stamp. */
    nxdn_boundary_v1_decision d = nxdn_boundary_v1_decide(&state, &now, "3331331111", 1);
    CHECK(d.allow == 1 && d.valid_before == 0 && d.valid_after == 0 && d.age == 0);
}

static void
test_pattern_scope_and_disabled_neutrality(void) {
    static const char* const canonical[] = {"3131331131", "1313113313"};
    static const char* const relaxed[] = {"3331331131", "3131331111", "3331331111", "3131311131",
                                        "1113113313", "1313113333", "1113113333", "1313133313"};
    static const char* const unknown[] = {"", "313133113", "31313311311", "0000000000", "313133113x", NULL};
    nxdn_boundary_v1_context now = context(1147U);
    for (unsigned int i = 0; i < sizeof(canonical) / sizeof(canonical[0]); ++i) {
        nxdn_boundary_v1_state state = armed(1000U);
        nxdn_boundary_v1_decision d = nxdn_boundary_v1_decide(&state, &now, canonical[i], 1);
        CHECK(d.allow == 1 && d.would_block == 0 && d.canonical == 1 && d.window == 0);
        CHECK(d.reason == NXDN_BOUNDARY_V1_CANONICAL && state.anchor.symbols == 1000U);
        now.confirmed = 0;
        d = nxdn_boundary_v1_decide(&state, &now, canonical[i], 1);
        CHECK(d.allow == 1 && d.canonical == 1 && d.valid_after == 0);
        now.confirmed = 1;
    }
    for (unsigned int i = 0; i < sizeof(relaxed) / sizeof(relaxed[0]); ++i) {
        nxdn_boundary_v1_state baseline = armed(1000U), candidate = baseline;
        nxdn_boundary_v1_decision a = nxdn_boundary_v1_decide(&baseline, &now, relaxed[i], 0);
        nxdn_boundary_v1_decision b = nxdn_boundary_v1_decide(&candidate, &now, relaxed[i], 1);
        CHECK(a.allow == 1 && b.allow == 0 && a.would_block == 1 && b.would_block == 1);
        CHECK(a.age == b.age && a.window == b.window && a.reason == b.reason && a.canonical == b.canonical);
        CHECK(a.valid_before == b.valid_before && a.valid_after == b.valid_after);
        CHECK(baseline.valid == candidate.valid && baseline.anchor.symbols == candidate.anchor.symbols);
        now.symbols = 1202U;
        b = nxdn_boundary_v1_decide(&candidate, &now, relaxed[i], 1);
        CHECK(b.allow == 1 && b.would_block == 0 && b.window == 2);
        now.symbols = 1147U;
    }
    for (unsigned int i = 0; i < sizeof(unknown) / sizeof(unknown[0]); ++i) {
        nxdn_boundary_v1_state state = armed(1000U);
        nxdn_boundary_v1_decision d = nxdn_boundary_v1_decide(&state, &now, unknown[i], 1);
        CHECK(d.allow == 1 && d.would_block == 0 && d.canonical == 0 && d.valid_after == 1);
        CHECK(d.reason == NXDN_BOUNDARY_V1_UNKNOWN_PATTERN);
    }
}

static void
test_arming_and_nonrefresh(void) {
    const int bad_results[] = {-1, 0, 1, 3};
    nxdn_boundary_v1_context begin = context(1000U), end = context(1182U);
    for (unsigned int i = 0; i < sizeof(bad_results) / sizeof(bad_results[0]); ++i) {
        nxdn_boundary_v1_state state = {0};
        CHECK(nxdn_boundary_v1_note_frame(&state, &begin, &end, bad_results[i]) == 0 && state.valid == 0);
        state = armed(900U);
        CHECK(nxdn_boundary_v1_note_frame(&state, &begin, &end, bad_results[i]) == 0);
        CHECK(state.valid == 1 && state.anchor.symbols == 900U);
    }
    const uint32_t lengths[] = {0U, 8U, 109U, 181U, 183U, UINT32_MAX};
    for (unsigned int i = 0; i < sizeof(lengths) / sizeof(lengths[0]); ++i) {
        nxdn_boundary_v1_state state = {0};
        end.symbols = begin.symbols + lengths[i];
        CHECK(nxdn_boundary_v1_note_frame(&state, &begin, &end, 2) == 0 && state.valid == 0);
    }
    end.symbols = 1182U;
    begin.confirmed = 0;
    nxdn_boundary_v1_state state = {0};
    CHECK(nxdn_boundary_v1_note_frame(&state, &begin, &end, 2) == 1); /* First proof. */
    CHECK(state.anchor.symbols == 1182U);
    begin.confirmed = 1;
    begin.symbols = 1192U;
    end.symbols = 1374U;
    CHECK(nxdn_boundary_v1_note_frame(&state, &begin, &end, 1) == 0);
    CHECK(state.anchor.symbols == 1182U);
    CHECK(nxdn_boundary_v1_note_frame(&state, &begin, &end, 2) == 1);
    CHECK(state.anchor.symbols == 1374U);
}

static void
change_context(nxdn_boundary_v1_context* c, int which) {
    switch (which) {
        case 0: c->owner = &owner_b; break;
        case 1: c->generation++; break;
        case 2: c->profile++; break;
        case 3: c->sps++; break;
        case 4: c->rf++; break;
        case 5: c->eligible = 0; break;
        case 6: c->confirmed = 0; break;
    }
}

static void
test_context_invalidation(void) {
    for (int which = 0; which < 7; ++which) {
        nxdn_boundary_v1_state state = armed(1000U);
        nxdn_boundary_v1_context now = context(1147U);
        change_context(&now, which);
        nxdn_boundary_v1_decision d = nxdn_boundary_v1_decide(&state, &now, "3331331111", 0);
        CHECK(d.allow == 1 && d.would_block == 0 && d.valid_before == 1 && d.valid_after == 0);
        CHECK(d.reason == (which == 5 ? NXDN_BOUNDARY_V1_INELIGIBLE
                           : which == 6 ? NXDN_BOUNDARY_V1_UNCONFIRMED : NXDN_BOUNDARY_V1_CONTEXT_CHANGED));
        now = context(1150U);
        d = nxdn_boundary_v1_decide(&state, &now, "3331331111", 1);
        CHECK(d.allow == 1 && d.valid_after == 0); /* Away and back is not revival. */

        nxdn_boundary_v1_context begin = context(1100U), end = context(1282U);
        change_context(&end, which);
        state = armed(1000U);
        CHECK(nxdn_boundary_v1_note_frame(&state, &begin, &end, 2) == 0 && state.valid == 0);
        if (which != 6) {
            begin = end;
            begin.symbols = 1100U;
            end = context(1282U);
            state = armed(1000U);
            CHECK(nxdn_boundary_v1_note_frame(&state, &begin, &end, 2) == 0 && state.valid == 0);
        }
    }
    /* A whole proven frame on a new compatible context replaces an old stamp. */
    nxdn_boundary_v1_state state = armed(1000U);
    nxdn_boundary_v1_context begin = context(1100U), end = context(1282U);
    begin.generation = end.generation = 8U;
    CHECK(nxdn_boundary_v1_note_frame(&state, &begin, &end, 2) == 1);
    CHECK(state.anchor.generation == 8U && state.anchor.symbols == 1282U);
    /* A lost-confirmation endpoint cannot preserve an old stamp without new proof. */
    begin = context(1292U); end = context(1474U);
    begin.generation = end.generation = 8U;
    begin.confirmed = 0;
    CHECK(nxdn_boundary_v1_note_frame(&state, &begin, &end, 1) == 0 && state.valid == 0);
}

static void
test_reset_expiry_and_rollover(void) {
    nxdn_boundary_v1_state state = armed(1000U);
    nxdn_boundary_v1_reset(&state);
    nxdn_boundary_v1_context now = context(1147U);
    nxdn_boundary_v1_decision d = nxdn_boundary_v1_decide(&state, &now, "3331331111", 1);
    CHECK(d.allow == 1 && d.reason == NXDN_BOUNDARY_V1_UNARMED && d.valid_before == 0);

    state = armed(1000U);
    now.symbols = 999U;
    d = nxdn_boundary_v1_decide(&state, &now, "3331331111", 1);
    CHECK(d.age == UINT32_MAX && d.reason == NXDN_BOUNDARY_V1_EXPIRED && state.valid == 0);

    const uint32_t anchor = UINT32_MAX - 100U;
    state = armed(anchor);
    now.symbols = anchor + 202U;
    d = nxdn_boundary_v1_decide(&state, &now, "3331331111", 1);
    CHECK(d.age == 202U && d.window == 2 && d.allow == 1 && state.valid == 1);
    now.symbols = anchor + 340U;
    d = nxdn_boundary_v1_decide(&state, &now, "3331331111", 1);
    CHECK(d.age == 340U && d.would_block == 1 && state.valid == 1);

    nxdn_boundary_v1_context begin = context(UINT32_MAX - 90U), end = context(91U);
    nxdn_boundary_v1_reset(&state);
    CHECK(nxdn_boundary_v1_note_frame(&state, &begin, &end, 2) == 1 && state.anchor.symbols == 91U);

    state = armed(1000U);
    begin = context(1214U); end = context(1396U);
    CHECK(nxdn_boundary_v1_note_frame(&state, &begin, &end, 1) == 0 && state.valid == 0);
    /* New proof after the old lifetime expires is still new proof. */
    CHECK(nxdn_boundary_v1_note_frame(&state, &begin, &end, 2) == 1 && state.anchor.symbols == 1396U);
}

static void
test_gap_does_not_refresh(void) {
    nxdn_boundary_v1_state state = armed(800U);
    nxdn_boundary_v1_context begin = context(810U), end = context(818U);
    CHECK(nxdn_boundary_v1_note_frame(&state, &begin, &end, 1) == 0);
    CHECK(state.valid == 1 && state.anchor.symbols == 800U);
    nxdn_boundary_v1_context now = context(948U);
    nxdn_boundary_v1_decision d = nxdn_boundary_v1_decide(&state, &now, "3331331111", 1);
    CHECK(d.would_block == 1 && d.age == 148U);
    now.symbols = 1003U;
    d = nxdn_boundary_v1_decide(&state, &now, "3131331131", 1);
    CHECK(d.allow == 1 && d.window == 2 && state.anchor.symbols == 800U);
    now.symbols = 1140U;
    d = nxdn_boundary_v1_decide(&state, &now, "3331331111", 1);
    CHECK(d.would_block == 1 && state.anchor.symbols == 800U);
    now.symbols = 1195U;
    d = nxdn_boundary_v1_decide(&state, &now, "3131331131", 1);
    CHECK(d.allow == 1 && d.window == 3 && state.anchor.symbols == 800U);
    now.symbols = 1196U;
    d = nxdn_boundary_v1_decide(&state, &now, "3331331111", 1);
    CHECK(d.allow == 1 && d.reason == NXDN_BOUNDARY_V1_EXPIRED && state.valid == 0);
}

static void
test_null_arguments(void) {
    nxdn_boundary_v1_state state = armed(1000U);
    nxdn_boundary_v1_context c = context(1147U);
    nxdn_boundary_v1_decision d = nxdn_boundary_v1_decide(NULL, &c, "3331331111", 1);
    CHECK(d.allow == 1 && d.reason == NXDN_BOUNDARY_V1_BAD_ARGUMENT);
    d = nxdn_boundary_v1_decide(&state, NULL, "3131331131", 1);
    CHECK(d.allow == 1 && d.canonical == 1 && d.valid_after == 0);
    state = armed(1000U);
    CHECK(nxdn_boundary_v1_note_frame(&state, NULL, &c, 2) == 0 && state.valid == 0);
    state = armed(1000U);
    CHECK(nxdn_boundary_v1_note_frame(&state, &c, NULL, 2) == 0 && state.valid == 0);
    CHECK(nxdn_boundary_v1_note_frame(NULL, &c, &c, 2) == 0);
    nxdn_boundary_v1_reset(NULL);
    CHECK(strcmp(nxdn_boundary_v1_reason_name(NXDN_BOUNDARY_V1_OFF_PHASE), "off_phase") == 0);
    CHECK(strcmp(nxdn_boundary_v1_reason_name((nxdn_boundary_v1_reason)999), "unknown_reason") == 0);
}

int
main(void) {
    test_windows_and_expiry();
    test_pattern_scope_and_disabled_neutrality();
    test_arming_and_nonrefresh();
    test_context_invalidation();
    test_reset_expiry_and_rollover();
    test_gap_does_not_refresh();
    test_null_arguments();
    if (failures) {
        fprintf(stderr, "%d boundary policy checks failed\n", failures);
        return 1;
    }
    puts("NXDN boundary v1 pure policy checks passed");
    return 0;
}
