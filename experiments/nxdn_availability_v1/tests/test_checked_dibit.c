// SPDX-License-Identifier: GPL-3.0-or-later
#define main legacy_dibit_regressions
#include "../../../upstream/dsd-neo/tests/core/test_dibit_symbol_bin_soft.c"
#undef main
#include <dsd-neo/dsp/symbol.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #x); exit(1); } } while (0)
static int checked_available = 1, checked_reads;
/* Deliberately independent of the numeric value/counter. Simulate the original
 * replay EOF commit too, to catch accidental counter-based validity inference. */
int dsd_get_symbol_checked(dsd_opts* opts, dsd_state* state, int sync, float* out) {
    checked_reads++;
    state->symbolcnt++;
    *out = checked_available ? getSymbol(opts, state, sync) : 0.0f;
    return checked_available;
}
static void test_checked_read(void) {
    static dsd_opts opts; static dsd_state state; static dsd_state before;
    DSD_MEMSET(&opts, 0, sizeof(opts)); DSD_MEMSET(&state, 0, sizeof(state));
    CHECK(init_state_buffers(&state)); set_standard_thresholds(&state);
    state.synctype = DSD_SYNC_NXDN_POS; state.rf_mod = 0;
    opts.audio_in_type = AUDIO_IN_SYMBOL_BIN; opts.ssize = 1;
    opts.symbol_out_f = tmpfile(); CHECK(opts.symbol_out_f != NULL);
    checked_available = 1; checked_reads = 0;
    for (int word = 0; word < 4; ++word) {
        g_next_dibit = word; int dibit = -1; dsd_dibit_soft_t soft;
        CHECK(dsd_get_dibit_soft_checked(&opts, &state, &dibit, &soft) == 1);
        CHECK(dibit == word && soft.reliability == 255);
        CHECK(llr_matches_bit(soft.llr[0], (word >> 1) & 1) && llr_matches_bit(soft.llr[1], word & 1));
        CHECK(state.dmr_soft_p[-1].llr[0] == soft.llr[0] && state.dmr_soft_p[-1].llr[1] == soft.llr[1]);
    }
    CHECK(checked_reads == 4);
    long capture_pos = ftell(opts.symbol_out_f); CHECK(capture_pos > 0);
    checked_available = 0;
    DSD_MEMCPY(&before, &state, sizeof(state));
    int dibit = 99; dsd_dibit_soft_t soft; DSD_MEMSET(&soft, 0xA5, sizeof(soft));
    CHECK(dsd_get_dibit_soft_checked(&opts, &state, &dibit, &soft) == 0);
    CHECK(dibit == 0 && soft.reliability == 0 && soft.llr[0] == 0 && soft.llr[1] == 0);
    CHECK(checked_reads == 5 && state.symbolcnt == before.symbolcnt + 1);
    state.symbolcnt = before.symbolcnt;
    CHECK(memcmp(&before, &state, sizeof(state)) == 0); /* no stale ring/slicer/capture state */
    CHECK(ftell(opts.symbol_out_f) == capture_pos);
    /* The real use_symbol/print_datascope resets symbolcnt to zero. Availability
     * must survive this reset and still commit exactly one valid dibit. */
    checked_available = 1; opts.datascope = 1; opts.scoperate = 1;
    state.symbolcnt = 4801; int* ptr = state.dibit_buf_p;
    CHECK(dsd_get_dibit_soft_checked(&opts, &state, &dibit, &soft) == 1);
    CHECK(state.symbolcnt == 0 && state.dibit_buf_p == ptr + 1 && dibit == g_next_dibit);
    CHECK(checked_reads == 6);
    CHECK(dsd_get_dibit_soft_checked(NULL, &state, &dibit, &soft) == 0 && dibit == 0);
    CHECK(dsd_get_dibit_soft_checked(&opts, NULL, &dibit, &soft) == 0);
    CHECK(dsd_get_dibit_soft_checked(&opts, &state, NULL, &soft) == 0);
    CHECK(checked_reads == 6);
    opts.datascope = 0;
    CHECK(dsd_get_dibit_soft_checked(&opts, &state, &dibit, NULL) == 1);
    CHECK(fclose(opts.symbol_out_f) == 0); free_state_buffers(&state);
}
int main(void) {
    CHECK(legacy_dibit_regressions() == 0);
    test_checked_read();
    puts("checked dibit: original regressions + no-stale-state and actual datascope reset passed");
    return 0;
}
