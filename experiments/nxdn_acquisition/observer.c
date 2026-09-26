// SPDX-License-Identifier: GPL-3.0-or-later
/*
 * Copyright (C) 2026 by arancormonk <180709949+arancormonk@users.noreply.github.com>
 */

/* Research observer derived from test_frame_sync_nxdn_fsk_phase.c.
 * Measures delivered discriminator sample positions, NOT original complex IQ.
 * The generated payload is uncoded; sync is not a protocol-valid frame.
 * See docs/research/NXDN-ACQUISITION-PREREGISTRATION-2026-09-25.md.
 */

#include <dsd-neo/core/dibit.h>
#include <dsd-neo/core/opts.h>
#include <dsd-neo/core/state.h>
#include <dsd-neo/core/synctype_ids.h>
#include <dsd-neo/dsp/frame_sync.h>
#include <dsd-neo/io/rtl_stream_c.h>
#include <dsd-neo/runtime/rtl_stream_io_hooks.h>
#include <dsd-neo/runtime/rtl_stream_metrics_hooks.h>
#include <dsd-neo/runtime/exitflag.h>
#include "symbol_test_support.h"
#include <string.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "dsd-neo/core/opts_fwd.h"
#include "dsd-neo/core/safe_api.h"
#include "dsd-neo/core/state_fwd.h"
#include "frame_sync_state_buffers.h"

#define NXDN48_SPS       20
#define NXDN_FSW         "3131331131"
#define NXDN_FSW_LEN     10
#define NXDN_FRAME       192
#define NXDN_PAYLOAD_LEN (NXDN_FRAME - NXDN_FSW_LEN)
#define FRAME_COUNT      16
#define PREAMBLE_DIBITS  32

/* Mixed inner/outer payload: outer runs stay short so no window of it can look
   like an all-outer frame sync word. */
static const char kPayloadCycle[] = "0132230110322301";

static size_t g_ramp_samples = 8U;
static float* g_waveform;
static size_t g_waveform_len;
static size_t g_waveform_pos;
static size_t g_read_chunk = 512U;
static int g_waveform_exhausted;
static size_t g_read_start;
static int g_generation_mode;
static unsigned g_generation_calls;

static char g_dibits[PREAMBLE_DIBITS + (FRAME_COUNT * NXDN_FRAME) + 1];
static size_t g_dibit_count;

static float
level_for_dibit(char dibit) {
    switch (dibit) {
        case '0': return 8000.0f;
        case '1': return 24000.0f;
        case '2': return -8000.0f;
        case '3': return -24000.0f;
        default: break;
    }
    return 0.0f;
}

static void
build_dibit_stream(void) {
    size_t n = 0;
    for (size_t i = 0; i < PREAMBLE_DIBITS; i++) {
        g_dibits[n++] = (i % 2U) ? '3' : '1';
    }
    const size_t cycle_len = sizeof(kPayloadCycle) - 1U;
    for (size_t f = 0; f < FRAME_COUNT; f++) {
        for (size_t i = 0; i < NXDN_FSW_LEN; i++) {
            g_dibits[n++] = NXDN_FSW[i];
        }
        for (size_t i = 0; i < NXDN_PAYLOAD_LEN; i++) {
            g_dibits[n++] = kPayloadCycle[(f + i) % cycle_len];
        }
    }
    g_dibits[n] = '\0';
    g_dibit_count = n;
}

/* Ideal NRZ smoothed by a boxcar, so every symbol boundary becomes a ramp
   RAMP_SAMPLES wide. A square wave would decode the same at any phase. */
static int
build_waveform(size_t ramp_samples) {
    g_ramp_samples = ramp_samples;
    free(g_waveform);
    g_waveform = NULL;
    const size_t n = g_dibit_count * NXDN48_SPS;
    float* nrz = (float*)calloc(n, sizeof(float));
    g_waveform = (float*)calloc(n, sizeof(float));
    if (!nrz || !g_waveform) {
        free(nrz);
        free(g_waveform);
        g_waveform = NULL;
        return 0;
    }
    for (size_t d = 0; d < g_dibit_count; d++) {
        const float level = level_for_dibit(g_dibits[d]);
        for (size_t s = 0; s < NXDN48_SPS; s++) {
            nrz[(d * NXDN48_SPS) + s] = level;
        }
    }
    for (size_t i = 0; i < n; i++) {
        float sum = 0.0f;
        for (size_t k = 0; k < g_ramp_samples; k++) {
            long idx = (long)i + (long)k - (long)(g_ramp_samples / 2U);
            if (idx < 0) {
                idx = 0;
            }
            if (idx >= (long)n) {
                idx = (long)n - 1;
            }
            sum += nrz[idx];
        }
        g_waveform[i] = sum / (float)g_ramp_samples;
    }
    g_waveform_len = n;
    free(nrz);
    return 1;
}

static int
fake_rtl_read(void* rtl_ctx, float* out, size_t count, int* out_got) {
    (void)rtl_ctx;
    if (!out || !out_got || count == 0U) {
        return -1;
    }
    if (g_waveform_pos >= g_waveform_len) {
        g_waveform_exhausted = 1;
        dsd_exitflag_store(1);
        *out_got = 0;
        return -1;
    }
    size_t want = (count < g_read_chunk) ? count : g_read_chunk;
    if (want > (g_waveform_len - g_waveform_pos)) {
        want = g_waveform_len - g_waveform_pos;
    }
    g_read_start = g_waveform_pos;
    for (size_t i = 0; i < want; i++) {
        out[i] = g_waveform[g_waveform_pos++];
    }
    *out_got = (int)want;
    return 0;
}

static double
fake_rtl_pwr(const void* rtl_ctx) {
    (void)rtl_ctx;
    return 0.0;
}

static int
fake_output_kind(void) {
    return RTL_STREAM_OUTPUT_FSK_DISCRIMINATOR;
}

static unsigned int
fake_output_rate_hz(void) {
    return 48000U;
}

static int
fake_symbol_profile(int* out_symbol_rate_hz, int* out_levels, int* out_channel_profile) {
    if (out_symbol_rate_hz) {
        *out_symbol_rate_hz = 2400;
    }
    if (out_levels) {
        *out_levels = 4;
    }
    if (out_channel_profile) {
        *out_channel_profile = RTL_STREAM_CHANNEL_PROFILE_6K25;
    }
    return 0;
}

static uint32_t
fake_stream_generation(void) {
    g_generation_calls++;
    if (g_generation_mode == 1 || (g_generation_mode == 2 && g_generation_calls > 1U)) {
        return 2U;
    }
    return 1U;
}

typedef struct {
    uint32_t pops[PREAMBLE_DIBITS * NXDN48_SPS + FRAME_COUNT * NXDN_FRAME * NXDN48_SPS];
    size_t count, frontier, skipped, errors, initial;
} trace_t;

typedef struct {
    int sync_code, cache_pos, cache_len;
    size_t provider_end, consumed_end, pop_count, frame_index, landmark;
    char payload[NXDN_PAYLOAD_LEN + 1];
} frame_t;

typedef struct {
    frame_t frames[2];
    trace_t trace;
} result_t;

static void
observe(void* user, const dsd_state* state, uint32_t generation, int index, float sample) {
    trace_t* trace = (trace_t*)user;
    if (!trace || !state || generation != 1U || index < 0 || index >= state->rtl_symbol_cache_len) {
        if (trace) { trace->errors++; }
        return;
    }
    const size_t source = g_read_start + (size_t)index;
    if (source >= g_waveform_len || memcmp(&sample, &g_waveform[source], sizeof(sample)) != 0
        || trace->count >= sizeof(trace->pops) / sizeof(trace->pops[0])) {
        trace->errors++;
        return;
    }
    const size_t expected = trace->count ? trace->frontier : trace->initial;
    if (source < expected) { trace->errors++; }
    else { trace->skipped += source - expected; }
    trace->pops[trace->count++] = (uint32_t)source;
    trace->frontier = source + 1U;
}

typedef struct { int calls, index; uint32_t generation; float sample; } control_t;
static void
control_observe(void* user, const dsd_state* state, uint32_t generation, int index, float sample) {
    control_t* control = (control_t*)user;
    (void)state;
    control->calls++;
    control->index = index;
    control->generation = generation;
    control->sample = sample;
}

/* Direct mapping negatives, not RF/noise false-positive tests. Explicit checks
 * survive Release/NDEBUG and the independent Python validator has mutations. */
static int
lineage_controls(int* checks) {
    static dsd_state state;
    int failures = 0;
    dsd_rtl_stream_metrics_hooks metrics = {.stream_generation = fake_stream_generation};
    dsd_rtl_stream_metrics_hooks_set(&metrics);
    for (int test = 0; test < 8; test++) {
        memset(&state, 0, sizeof(state));
        control_t control = {0};
        float out = -99.0f;
        state.rtl_symbol_cache_len = 2;
        state.rtl_symbol_cache[0] = 123.0f;
        state.rtl_symbol_cache[1] = 456.0f;
        g_generation_mode = test == 2 ? 1 : (test == 3 ? 2 : 0);
        g_generation_calls = 0;
        dsd_rtl_stream_metrics_hook_symbol_cache_pending_reset();
        dsd_symbol_test_set_rtl_sample_observer(control_observe, &control);
        if (test == 0) { dsd_symbol_test_set_rtl_sample_observer(NULL, &control); }
        if (test == 4) { state.rtl_symbol_cache_len = 0; }
        if (test == 7) { state.rtl_symbol_cache_pos = 1; }
        int rc = dsd_symbol_test_rtl_cache_pop(test == 6 ? NULL : &state, 1U, test == 5 ? NULL : &out);
        int ok;
        if (test == 2 || test == 3) {
            ok = rc == 2 && control.calls == 0 && state.rtl_symbol_cache_pos == 0
                 && state.rtl_symbol_cache_len == 0 && out == -99.0f;
        } else if (test == 4 || test == 5 || test == 6) {
            ok = rc == 0 && control.calls == 0 && out == -99.0f;
        } else if (test == 0) {
            ok = rc == 1 && control.calls == 0 && out == 123.0f;
        } else {
            const int index = test == 7 ? 1 : 0;
            ok = rc == 1 && control.calls == 1 && control.index == index && control.generation == 1U
                 && control.sample == (index ? 456.0f : 123.0f) && out == control.sample;
        }
        (*checks)++;
        if (!ok) { fprintf(stderr, "lineage control %d failed\n", test); failures++; }
        dsd_symbol_test_set_rtl_sample_observer(NULL, NULL);
    }
    g_generation_mode = 0;
    dsd_rtl_stream_metrics_hooks_set(NULL);
    dsd_rtl_stream_metrics_hook_symbol_cache_pending_reset();
    return failures;
}

static int
run_case(int offset, size_t chunk, int enabled, result_t* result) {
    static dsd_opts opts;
    static dsd_state state;
    static int context;
    memset(result, 0, sizeof(*result));
    result->trace.initial = (size_t)offset;
    g_waveform_pos = (size_t)offset;
    g_read_start = (size_t)offset;
    g_waveform_exhausted = 0;
    g_read_chunk = chunk;
    g_generation_mode = 0;
    dsd_exitflag_store(0);
    dsd_frame_sync_reset_mod_state();
    memset(&opts, 0, sizeof(opts));
    memset(&state, 0, sizeof(state));
    if (!init_state_buffers(&state)) { return 1; }
    opts.audio_in_type = AUDIO_IN_RTL;
    opts.frame_nxdn48 = 1;
    opts.msize = 1;
    opts.ssize = 128;
    state.rf_mod = 2;
    state.sps_hunt_idx = DSD_FRAME_SYNC_SPS_PROFILE_2400_4;
    state.rtl_ctx = (struct RtlSdrContext*)&context;
    dsd_rtl_stream_io_hooks_set((dsd_rtl_stream_io_hooks){.read = fake_rtl_read, .return_pwr = fake_rtl_pwr});
    dsd_rtl_stream_metrics_hooks metrics = {
        .output_kind = fake_output_kind, .output_rate_hz = fake_output_rate_hz,
        .symbol_profile = fake_symbol_profile, .stream_generation = fake_stream_generation};
    dsd_rtl_stream_metrics_hooks_set(&metrics);
    dsd_rtl_stream_metrics_hook_symbol_cache_pending_reset();
    dsd_symbol_test_set_rtl_sample_observer(enabled ? observe : NULL, &result->trace);
    int failures = 0;
    for (size_t f = 0; f < 2; f++) {
        frame_t* frame = &result->frames[f];
        frame->sync_code = DSD_SYNC_NONE;
        for (int attempt = 0; attempt < (f == 0 ? 4 : 1) && !g_waveform_exhausted; attempt++) {
            frame->sync_code = getFrameSync(&opts, &state);
            if (frame->sync_code == DSD_SYNC_NXDN_POS) { break; }
        }
        /* Snapshot before payload reading; provider_end includes future cache. */
        frame->provider_end = g_waveform_pos;
        frame->cache_pos = state.rtl_symbol_cache_pos;
        frame->cache_len = state.rtl_symbol_cache_len;
        frame->consumed_end = result->trace.frontier;
        frame->pop_count = result->trace.count;
        if (enabled && frame->consumed_end >= PREAMBLE_DIBITS * NXDN48_SPS) {
            frame->frame_index = (frame->consumed_end - PREAMBLE_DIBITS * NXDN48_SPS) / (NXDN_FRAME * NXDN48_SPS);
            frame->landmark = PREAMBLE_DIBITS * NXDN48_SPS + frame->frame_index * NXDN_FRAME * NXDN48_SPS;
        }
        if (frame->sync_code != DSD_SYNC_NXDN_POS) { failures++; continue; }
        state.synctype = frame->sync_code;
        for (size_t n = 0; n < NXDN_PAYLOAD_LEN; n++) {
            dsd_dibit_soft_t soft;
            int value = getDibitSoft(&opts, &state, &soft);
            if (value < 0 || value > 3) { failures++; break; }
            frame->payload[n] = (char)('0' + value);
        }
    }
    dsd_symbol_test_set_rtl_sample_observer(NULL, NULL);
    dsd_rtl_stream_io_hooks_set((dsd_rtl_stream_io_hooks){0});
    dsd_rtl_stream_metrics_hooks_set(NULL);
    dsd_rtl_stream_metrics_hook_symbol_cache_pending_reset();
    dsd_exitflag_store(0);
    free_state_buffers(&state);
    return failures + (result->trace.errors != 0);
}

static void
print_frame(const frame_t* frame, int observed) {
    printf("{\"sync_code\":%d,\"provider_end\":%zu,\"cache_pos\":%d,\"cache_len\":%d,\"payload\":\"%s\"",
           frame->sync_code, frame->provider_end, frame->cache_pos, frame->cache_len, frame->payload);
    if (observed) {
        printf(",\"consumed_end\":%zu,\"pop_count\":%zu,\"frame_index\":%zu,\"landmark\":%zu",
               frame->consumed_end, frame->pop_count, frame->frame_index, frame->landmark);
    }
    printf("}");
}

static int
write_trace(const char* directory, const char* id, const trace_t* trace) {
    char path[4096];
    int length = snprintf(path, sizeof(path), "%s/%s.u32le", directory, id);
    if (length < 0 || (size_t)length >= sizeof(path)) { return 1; }
    FILE* file = fopen(path, "wb");
    if (!file) { perror(path); return 1; }
    int failure = 0;
    for (size_t n = 0; n < trace->count; n++) {
        uint32_t v = trace->pops[n];
        unsigned char bytes[4] = {(unsigned char)v, (unsigned char)(v >> 8),
                                  (unsigned char)(v >> 16), (unsigned char)(v >> 24)};
        if (fwrite(bytes, 1, sizeof(bytes), file) != sizeof(bytes)) { failure = 1; break; }
    }
    if (fclose(file) != 0) { failure = 1; }
    return failure;
}

int
main(int argc, char** argv) {
    if (argc != 2) { fprintf(stderr, "usage: observer <existing artifact directory>\n"); return 2; }
    int controls = 0, failures = lineage_controls(&controls), cases = 0;
    build_dibit_stream();
    static result_t baseline, observed;
    static const size_t ramps[] = {8, 14}, chunks[] = {1, 37, 512};
    for (size_t r = 0; r < 2; r++) {
        if (!build_waveform(ramps[r])) { fprintf(stderr, "allocation failed\n"); return 2; }
        for (int offset = 0; offset < NXDN48_SPS; offset++) {
            for (size_t c = 0; c < 3; c++) {
                char id[64];
                snprintf(id, sizeof(id), "r%zu-o%d-c%zu", ramps[r], offset, chunks[c]);
                failures += run_case(offset, chunks[c], 0, &baseline);
                failures += run_case(offset, chunks[c], 1, &observed);
                failures += write_trace(argv[1], id, &observed.trace);
                for (size_t f = 0; f < 2; f++) {
                    const frame_t* b = &baseline.frames[f];
                    const frame_t* o = &observed.frames[f];
                    if (b->sync_code != o->sync_code || b->provider_end != o->provider_end
                        || b->cache_pos != o->cache_pos || b->cache_len != o->cache_len
                        || strcmp(b->payload, o->payload) != 0 || o->frame_index >= FRAME_COUNT) { failures++; }
                    for (size_t n = 0; n < NXDN_PAYLOAD_LEN; n++) {
                        if (o->payload[n] != kPayloadCycle[(o->frame_index + n) % (sizeof(kPayloadCycle) - 1)]) {
                            failures++; break;
                        }
                    }
                }
                printf("{\"schema\":1,\"kind\":\"case\",\"id\":\"%s\",\"ramp\":%zu,\"offset\":%d,\"chunk\":%zu,"
                       "\"domain\":\"discriminator_samples\",\"rate_hz\":48000,\"waveform_samples\":%zu,"
                       "\"pop_trace\":\"%s.u32le\",\"baseline\":{\"frames\":[", id, ramps[r], offset, chunks[c], g_waveform_len, id);
                print_frame(&baseline.frames[0], 0); printf(","); print_frame(&baseline.frames[1], 0);
                printf("],\"callback_count\":%zu},\"observed\":{\"frames\":[", baseline.trace.count);
                print_frame(&observed.frames[0], 1); printf(","); print_frame(&observed.frames[1], 1);
                printf("],\"callback_count\":%zu,\"skipped_samples\":%zu,\"lineage_errors\":%zu},"
                       "\"original_iq_samples\":null,\"valid_frame_latency\":null,\"pcm_latency\":null}\n",
                       observed.trace.count, observed.trace.skipped, observed.trace.errors);
                cases++;
            }
        }
    }
    free(g_waveform);
    printf("{\"schema\":1,\"kind\":\"summary\",\"domain\":\"discriminator_samples\",\"rate_hz\":48000,"
           "\"cases\":%d,\"lineage_control_checks\":%d,\"failures\":%d,\"original_iq_samples\":null,"
           "\"valid_frame_latency\":null,\"pcm_latency\":null}\n", cases, controls, failures);
    return failures ? 1 : 0;
}
