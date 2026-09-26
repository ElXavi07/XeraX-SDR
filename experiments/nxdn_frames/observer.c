// SPDX-License-Identifier: GPL-3.0-or-later
/*
 * Copyright (C) 2026 by arancormonk <180709949+arancormonk@users.noreply.github.com>
 */

/* Complete control-frame research observer derived from the frozen uncoded
 * acquisition observer and its upstream phase fixture.
 * Measures delivered discriminator sample positions, NOT original complex IQ.
 * Channel inputs come from an independent pinned encoder. CRC acceptance
 * and historical confirmation are recorded as different observations.
 * See docs/research/NXDN-FRAMES-PREREGISTRATION-2026-09-25.md.
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
#include "nxdn_test_support.h"
#include "nxdn_confirm.h"
#include "side_effect_sinks.h"
#include <dsd-neo/protocol/nxdn/nxdn.h>
#include <dsd-neo/protocol/nxdn/nxdn_deperm.h>
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
#define FRAME_COUNT      4
#define TRAILER_DIBITS   32
#define MAX_SAMPLES      ((PREAMBLE_DIBITS + FRAME_COUNT * NXDN_FRAME + TRAILER_DIBITS) * NXDN48_SPS)
#define PREAMBLE_DIBITS  32

/* Frozen complete encoded vectors; their payload also contains the declared
   sync-like window at dibit 170. Do not tune that window out of the fixture. */
static uint8_t g_vectors[3][192];

static size_t g_ramp_samples = 8U;
static float* g_waveform;
static size_t g_waveform_len;
static size_t g_waveform_pos;
static size_t g_read_chunk = 512U;
static int g_waveform_exhausted;
static size_t g_read_start;
static int g_generation_mode;
static unsigned g_generation_calls;

static char g_dibits[PREAMBLE_DIBITS + (FRAME_COUNT * NXDN_FRAME) + TRAILER_DIBITS + 1];
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
build_dibit_stream(int scenario) {
    size_t n = 0;
    for (size_t i = 0; i < PREAMBLE_DIBITS; i++) { g_dibits[n++] = (i & 1U) ? '3' : '1'; }
    for (size_t frame = 0; frame < FRAME_COUNT; frame++) {
        int variant = scenario == 1 ? 1 : (scenario == 2 ? 2 : 0);
        if (scenario == 3 && frame >= 2U) { variant = frame == 2U ? 1 : 2; }
        for (size_t i = 0; i < 192U; i++) { g_dibits[n++] = (char)('0' + g_vectors[variant][i]); }
    }
    for (size_t i = 0; i < TRAILER_DIBITS; i++) { g_dibits[n++] = '0'; }
    if (scenario == 4) {
        for (size_t i = PREAMBLE_DIBITS + NXDN_FSW_LEN; i < n; i++) { g_dibits[i] = '0'; }
    }
    if (scenario == 6) {
        uint32_t seed = 0x413288FBU;
        for (size_t i = 0; i < n; i++) {
            seed ^= seed << 13; seed ^= seed >> 17; seed ^= seed << 5;
            g_dibits[i] = (char)('0' + (seed >> 30));
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
    uint32_t pops[MAX_SAMPLES];
    size_t count, frontier, skipped, errors, initial;
} trace_t;
typedef struct {
    dsd_nxdn_test_crc_event event;
    int frame_call;
    size_t consumed_end, pop_count;
} crc_t;
typedef struct {
    int sync_code, cache_sync_pos, cache_sync_len, cache_end_pos, cache_end_len;
    int result, confirmed, last_sync, voice_after, source_truncated;
    size_t provider_sync, provider_end, dispatch_begin, dispatch_end, crc_begin, crc_end;
    size_t sync_consumed, end_consumed, pop_sync, pop_end;
} frame_t;
typedef struct {
    frame_t frames[16];
    crc_t events[48];
    size_t frame_count, event_count;
    trace_t trace;
    xerax_side_effect_observations effects;
    int current_frame, errors, exhausted;
} result_t;

static void
observe_sample(void* user, const dsd_state* state, uint32_t generation, int index, float sample) {
    result_t* result = (result_t*)user;
    trace_t* trace = &result->trace;
    if (!state || generation != 1U || index < 0 || index >= state->rtl_symbol_cache_len) { trace->errors++; return; }
    size_t source = g_read_start + (size_t)index;
    if (source >= g_waveform_len || memcmp(&sample, &g_waveform[source], sizeof(sample)) != 0
        || trace->count >= MAX_SAMPLES) { trace->errors++; return; }
    size_t expected = trace->count ? trace->frontier : trace->initial;
    if (source < expected) { trace->errors++; }
    else { trace->skipped += source - expected; }
    trace->pops[trace->count++] = (uint32_t)source;
    trace->frontier = source + 1U;
}

static void
observe_crc(void* user, const dsd_state* state, const dsd_nxdn_test_crc_event* event) {
    result_t* result = (result_t*)user;
    (void)state;
    if (!event || result->event_count >= 48U || event->info_bit_count > 80U) { result->errors++; return; }
    crc_t* record = &result->events[result->event_count++];
    record->event = *event;
    record->frame_call = result->current_frame;
    record->consumed_end = result->trace.frontier;
    record->pop_count = result->trace.count;
}

static int
run_case(int offset, size_t chunk, int enabled, result_t* result) {
    static dsd_opts opts;
    static dsd_state state;
    static int context;
    memset(result, 0, sizeof(*result));
    memset(&xerax_effects, 0, sizeof(xerax_effects));
    result->trace.initial = (size_t)offset;
    g_waveform_pos = g_read_start = (size_t)offset;
    g_waveform_exhausted = 0;
    g_read_chunk = chunk;
    g_generation_mode = 0;
    dsd_exitflag_store(0);
    dsd_frame_sync_reset_mod_state();
    memset(&opts, 0, sizeof(opts));
    memset(&state, 0, sizeof(state));
    if (!init_state_buffers(&state)) { result->errors++; return 1; }
    opts.audio_in_type = AUDIO_IN_RTL;
    opts.frame_nxdn48 = 1;
    opts.msize = 1;
    opts.ssize = 128;
    state.rf_mod = 2;
    state.sps_hunt_idx = DSD_FRAME_SYNC_SPS_PROFILE_2400_4;
    state.rtl_ctx = (struct RtlSdrContext*)&context;
    state.nxdn_pn95_seed = 228;
    dsd_rtl_stream_io_hooks_set((dsd_rtl_stream_io_hooks){.read = fake_rtl_read, .return_pwr = fake_rtl_pwr});
    dsd_rtl_stream_metrics_hooks metrics = {
        .output_kind = fake_output_kind, .output_rate_hz = fake_output_rate_hz,
        .symbol_profile = fake_symbol_profile, .stream_generation = fake_stream_generation};
    dsd_rtl_stream_metrics_hooks_set(&metrics);
    dsd_rtl_stream_metrics_hook_symbol_cache_pending_reset();
    dsd_symbol_test_set_rtl_sample_observer(enabled ? observe_sample : NULL, result);
    dsd_nxdn_test_set_crc_observer(enabled ? observe_crc : NULL, result);
    /* The source is finite. A separate search bound also catches an accidental
     * failure to make input progress without inventing a successful frame. */
    for (size_t attempt = 0; attempt < 32U && !g_waveform_exhausted; attempt++) {
        int sync = getFrameSync(&opts, &state);
        if (sync == DSD_SYNC_NONE) { continue; }
        if ((sync != DSD_SYNC_NXDN_POS && sync != DSD_SYNC_NXDN_NEG) || result->frame_count >= 16U) {
            fprintf(stderr, "research unsupported sync=%d frame_count=%zu\n", sync, result->frame_count);
            result->errors++; break;
        }
        result->current_frame = (int)result->frame_count;
        frame_t* frame = &result->frames[result->frame_count++];
        frame->sync_code = sync;
        frame->provider_sync = g_waveform_pos;
        frame->cache_sync_pos = state.rtl_symbol_cache_pos;
        frame->cache_sync_len = state.rtl_symbol_cache_len;
        frame->sync_consumed = result->trace.frontier;
        frame->pop_sync = result->trace.count;
        frame->dispatch_begin = xerax_effects.count;
        frame->crc_begin = result->event_count;
        state.synctype = sync;
        frame->result = nxdn_frame(&opts, &state);
        frame->source_truncated = g_waveform_exhausted;
        frame->provider_end = g_waveform_pos;
        frame->cache_end_pos = state.rtl_symbol_cache_pos;
        frame->cache_end_len = state.rtl_symbol_cache_len;
        frame->end_consumed = result->trace.frontier;
        frame->pop_end = result->trace.count;
        frame->crc_end = result->event_count;
        frame->dispatch_end = xerax_effects.count;
        frame->voice_after = xerax_effects.voice_requests;
        frame->confirmed = nxdn_confirm_is_confirmed(&state);
        frame->last_sync = state.lastsynctype;
    }
    result->exhausted = g_waveform_exhausted;
    if (!result->exhausted) { result->errors++; }
    result->effects = xerax_effects;
    result->errors += xerax_effects.errors;
    dsd_symbol_test_set_rtl_sample_observer(NULL, NULL);
    dsd_nxdn_test_set_crc_observer(NULL, NULL);
    dsd_rtl_stream_io_hooks_set((dsd_rtl_stream_io_hooks){0});
    dsd_rtl_stream_metrics_hooks_set(NULL);
    dsd_rtl_stream_metrics_hook_symbol_cache_pending_reset();
    dsd_exitflag_store(0);
    free_state_buffers(&state);
    return result->errors + (result->trace.errors != 0);
}

static void
run_direct(int variant, result_t* result) {
    static dsd_opts opts;
    static dsd_state state;
    memset(result, 0, sizeof(*result));
    memset(&opts, 0, sizeof(opts));
    memset(&state, 0, sizeof(state));
    memset(&xerax_effects, 0, sizeof(xerax_effects));
    result->current_frame = -1;
    if (!init_state_buffers(&state)) { result->errors++; return; }
    opts.frame_nxdn48 = 1;
    state.synctype = DSD_SYNC_NXDN_POS;
    state.nxdn_sacch_non_superframe = 1;
    uint8_t body[182], bits[364], reliability[144];
    memcpy(body, g_vectors[variant] + 10, sizeof(body));
    nxdn_descramble_with_seed(body, 182, 228);
    for (size_t n = 0; n < 182; n++) { bits[n * 2] = body[n] >> 1; bits[n * 2 + 1] = body[n] & 1U; }
    memset(reliability, 255, sizeof(reliability));
    dsd_nxdn_test_set_crc_observer(observe_crc, result);
    nxdn_confirm_begin_frame(&state);
    nxdn_deperm_sacch_soft(&opts, &state, bits + 16, reliability);
    nxdn_deperm_facch_soft(&opts, &state, bits + 76, reliability, 1);
    nxdn_deperm_facch_soft(&opts, &state, bits + 220, reliability, 2);
    nxdn_confirm_end_frame(&state);
    dsd_nxdn_test_set_crc_observer(NULL, NULL);
    result->effects = xerax_effects;
    result->errors += xerax_effects.errors;
    free_state_buffers(&state);
}

static void
print_crc(const crc_t* crc) {
    const dsd_nxdn_test_crc_event* e = &crc->event;
    printf("{\"frame_call\":%d,\"channel\":%d,\"part\":%u,\"computed\":%u,\"received\":%u,"
           "\"soft_pass\":%d,\"fallback\":%d,\"bits\":\"", crc->frame_call, (int)e->channel,
           (unsigned)e->frame_part, (unsigned)e->computed_crc, (unsigned)e->received_crc,
           e->soft_crc_pass, e->hard_fallback_used);
    for (size_t n = 0; n < e->info_bit_count; n++) { putchar((int)('0' + e->info_bits[n])); }
    printf("\",\"consumed_end\":%zu,\"pop_count\":%zu}", crc->consumed_end, crc->pop_count);
}

static void
print_run(const result_t* r, int observed) {
    printf("{\"frames\":[");
    for (size_t n = 0; n < r->frame_count; n++) {
        const frame_t* f = &r->frames[n];
        if (n) { putchar(','); }
        printf("{\"sync_code\":%d,\"provider_sync\":%zu,\"cache_sync_pos\":%d,\"cache_sync_len\":%d,"
               "\"provider_end\":%zu,\"cache_end_pos\":%d,\"cache_end_len\":%d,\"result\":%d,"
               "\"confirmed\":%d,\"last_sync\":%d,\"dispatch_begin\":%zu,\"dispatch_end\":%zu,"
               "\"voice_after\":%d,\"source_truncated\":%d,\"crc_begin\":%zu,\"crc_end\":%zu,\"pop_sync\":%zu,\"pop_end\":%zu,",
               f->sync_code, f->provider_sync, f->cache_sync_pos, f->cache_sync_len,
               f->provider_end, f->cache_end_pos, f->cache_end_len, f->result, f->confirmed,
               f->last_sync, f->dispatch_begin, f->dispatch_end, f->voice_after, f->source_truncated, f->crc_begin,
               f->crc_end, f->pop_sync, f->pop_end);
        if (observed) { printf("\"sync_consumed\":%zu,\"end_consumed\":%zu}", f->sync_consumed, f->end_consumed); }
        else { printf("\"sync_consumed\":null,\"end_consumed\":null}"); }
    }
    printf("],\"events\":[");
    for (size_t n = 0; n < r->event_count; n++) { if (n) { putchar(','); } print_crc(&r->events[n]); }
    printf("],\"dispatches\":[");
    for (size_t n = 0; n < r->effects.count; n++) {
        if (n) { putchar(','); }
        printf("{\"bits\":\"%s\",\"length\":%zu}", r->effects.content[n].bits, r->effects.content[n].length);
    }
    printf("],\"voice_requests\":%d,\"other_side_effects\":%d,\"errors\":%d,\"pop_count\":%zu,"
           "\"skipped_samples\":%zu,\"lineage_errors\":%zu,\"source_frontier\":%zu,\"exhausted\":%d}",
           r->effects.voice_requests, r->effects.other_side_effects, r->errors, r->trace.count,
           r->trace.skipped, r->trace.errors, r->trace.frontier, r->exhausted);
}

static int
write_trace(const char* directory, const char* id, const trace_t* trace) {
    char path[4096];
    int length = snprintf(path, sizeof(path), "%s/%s.u32le", directory, id);
    if (length < 0 || (size_t)length >= sizeof(path)) { return 1; }
    FILE* out = fopen(path, "wb");
    if (!out) { perror(path); return 1; }
    int failure = 0;
    for (size_t n = 0; n < trace->count; n++) {
        uint32_t v = trace->pops[n];
        unsigned char bytes[4] = {(unsigned char)v, (unsigned char)(v >> 8),
                                  (unsigned char)(v >> 16), (unsigned char)(v >> 24)};
        if (fwrite(bytes, 1, 4, out) != 4U) { failure = 1; break; }
    }
    if (fclose(out)) { failure = 1; }
    return failure;
}

int
main(int argc, char** argv) {
    if (argc != 3) { fprintf(stderr, "usage: frame_observer <vector dir> <existing artifact dir>\n"); return 2; }
    static const char* variants[] = {"valid", "wrong_all_crc", "wrong_lich"};
    static const char* scenarios[] = {"valid", "bad_crc", "bad_lich", "mixed", "one_fsw", "zero", "random"};
    for (int n = 0; n < 3; n++) {
        char path[4096];
        int length = snprintf(path, sizeof(path), "%s/%s.dibits", argv[1], variants[n]);
        if (length < 0 || (size_t)length >= sizeof(path)) { return 2; }
        FILE* in = fopen(path, "rb");
        if (!in) { perror(path); return 2; }
        size_t got = fread(g_vectors[n], 1, 192, in);
        int extra = fgetc(in);
        int error = ferror(in);
        if (fclose(in) || got != 192U || extra != EOF || error) { return 2; }
        for (size_t i = 0; i < 192; i++) { if (g_vectors[n][i] > 3U) { return 2; } }
    }
    int failures = 0, cases = 0;
    static result_t baseline, observed;
    for (int n = 0; n < 3; n++) {
        run_direct(n, &observed);
        failures += observed.errors;
        printf("{\"schema\":2,\"kind\":\"direct\",\"variant\":\"%s\",\"events\":[", variants[n]);
        for (size_t i = 0; i < observed.event_count; i++) { if (i) { putchar(','); } print_crc(&observed.events[i]); }
        printf("],\"errors\":%d,\"original_iq_samples\":null,\"pcm_latency\":null}\n", observed.errors);
    }
    static const size_t ramps[] = {8, 14}, chunks[] = {1, 37, 512};
    for (int scenario = 0; scenario < 7; scenario++) {
        build_dibit_stream(scenario);
        for (size_t r = 0; r < 2; r++) {
            if (!build_waveform(ramps[r])) { return 2; }
            if (scenario == 5) { memset(g_waveform, 0, g_waveform_len * sizeof(float)); }
            for (int off = 0; off < (scenario == 0 ? 20 : 1); off++) {
                for (size_t c = 0; c < 3; c++) {
                    char id[80];
                    snprintf(id, sizeof(id), "%s-r%zu-o%d-c%zu", scenarios[scenario], ramps[r], off, chunks[c]);
                    failures += run_case(off, chunks[c], 0, &baseline);
                    failures += run_case(off, chunks[c], 1, &observed);
                    failures += write_trace(argv[2], id, &observed.trace);
                    printf("{\"schema\":2,\"kind\":\"case\",\"id\":\"%s\",\"scenario\":\"%s\","
                           "\"ramp\":%zu,\"offset\":%d,\"chunk\":%zu,\"domain\":\"discriminator_samples\","
                           "\"rate_hz\":48000,\"waveform_samples\":%zu,\"pop_trace\":\"%s.u32le\",\"baseline\":",
                           id, scenarios[scenario], ramps[r], off, chunks[c], g_waveform_len, id);
                    print_run(&baseline, 0); printf(",\"observed\":"); print_run(&observed, 1);
                    printf(",\"original_iq_samples\":null,\"pcm_latency\":null}\n");
                    cases++;
                }
            }
        }
    }
    free(g_waveform);
    printf("{\"schema\":2,\"kind\":\"summary\",\"cases\":%d,\"direct_cases\":3,\"failures\":%d,"
           "\"domain\":\"discriminator_samples\",\"rate_hz\":48000,\"original_iq_samples\":null,\"pcm_latency\":null}\n",
           cases, failures);
    return failures ? 1 : 0;
}
