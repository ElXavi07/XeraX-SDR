// SPDX-License-Identifier: GPL-3.0-or-later
#ifdef NDEBUG
#undef NDEBUG
#endif
#define main legacy_rtl_cache_regressions
#include "../../../upstream/dsd-neo/tests/dsp/test_rtl_symbol_cache_generation.c"
#undef main
#include <dsd-neo/runtime/exitflag.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #x); exit(1); } } while (0)
static size_t finite_length, finite_delivered;
static int finite_read(void* ctx, float* out, size_t capacity, int* got) {
    CHECK(ctx != NULL && capacity > 0);
    size_t n = finite_length - finite_delivered;
    if (n > capacity) n = capacity;
    for (size_t i = 0; i < n; ++i) out[i] = 0.0f;
    finite_delivered += n;
    *got = (int)n;
    return n ? 0 : -1;
}
static void test_finite_span(int sps, int symbol_rate) {
    static dsd_opts opts;
    static dsd_state state;
    static int fake_context;
    const size_t sizes[] = {0, (size_t)sps - 1, (size_t)sps, (size_t)sps + 1, (size_t)sps * 2 - 1};
    for (size_t test = 0; test < sizeof(sizes)/sizeof(sizes[0]); ++test) {
        reset_stream_fixture(); reset_decoder_fixture(&opts, &state, &fake_context);
        exitflag = 0;
        finite_length = sizes[test]; finite_delivered = 0;
        g_output_kind = symbol_rate ? RTL_STREAM_OUTPUT_SYMBOL_CQPSK : RTL_STREAM_OUTPUT_FSK_DISCRIMINATOR;
        g_symbol_rate_hz = sps == 20 ? 2400 : 4800;
        g_channel_profile = sps == 20 ? RTL_STREAM_CHANNEL_PROFILE_6K25 : RTL_STREAM_CHANNEL_PROFILE_12K5;
        state.rf_mod = symbol_rate ? 1 : 0;
        state.sps_hunt_idx = sps == 20 ? DSD_FRAME_SYNC_SPS_PROFILE_2400_4 : DSD_FRAME_SYNC_SPS_PROFILE_4800_4;
        state.jitter = -1;
        dsd_rtl_stream_io_hooks_set((dsd_rtl_stream_io_hooks){.read=finite_read, .return_pwr=fake_rtl_pwr});
        dsd_rtl_stream_metrics_hooks metrics = {.output_kind=fake_output_kind, .output_rate_hz=fake_output_rate_hz,
            .symbol_profile=fake_symbol_profile, .stream_generation=fake_stream_generation};
        dsd_rtl_stream_metrics_hooks_set(&metrics);
        const size_t span = symbol_rate ? 1U : (size_t)sps;
        size_t completed = finite_length / span;
        for (size_t i = 0; i < completed; ++i) {
            float out = 99;
            CHECK(dsd_get_symbol_checked(&opts, &state, 1, &out) == 1 && out == 0);
            CHECK(state.symbolcnt == i + 1 && g_cleanup_calls == 0);
            if (!symbol_rate) CHECK(state.samplesPerSymbol == sps);
        }
        float out = 99;
        CHECK(dsd_get_symbol_checked(&opts, &state, 1, &out) == 0 && out == 0);
        CHECK(state.symbolcnt == completed && finite_delivered == finite_length);
        CHECK(dsd_rtl_stream_metrics_hook_symbol_cache_pending() == 0 && g_cleanup_calls == 1);
        /* Existing fixture shutdown is a counter-only stub. Set actual stop
         * state explicitly before proving a later call cannot manufacture input. */
        exitflag = 1;
        CHECK(dsd_get_symbol_checked(&opts, &state, 1, &out) == 0 && out == 0);
        CHECK(state.symbolcnt == completed);
    }
}
int main(void) {
    CHECK(legacy_rtl_cache_regressions() == 0);
    test_finite_span(10, 0); test_finite_span(20, 0); test_finite_span(10, 1);
    dsd_rtl_stream_io_hooks_set((dsd_rtl_stream_io_hooks){0});
    dsd_rtl_stream_metrics_hooks_set(NULL);
    dsd_rtl_stream_metrics_hook_symbol_cache_pending_reset();
    puts("checked live symbol: original cache regressions + finite SPS10/20/direct-symbol cases passed");
    return 0;
}
