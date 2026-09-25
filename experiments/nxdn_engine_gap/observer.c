// SPDX-License-Identifier: GPL-3.0-or-later
/* Finite continuous input into the actual engine loop. No protocol/reset stubs. */
#include "observer_api.h"
#include <dsd-neo/core/dibit.h>
#include <dsd-neo/core/init.h>
#include <dsd-neo/core/opts.h>
#include <dsd-neo/core/state.h>
#include <dsd-neo/core/synctype_ids.h>
#include <dsd-neo/io/rtl_stream_c.h>
#include <dsd-neo/protocol/nxdn/nxdn.h>
#include <dsd-neo/runtime/exitflag.h>
#include <dsd-neo/runtime/frame_sync_hooks.h>
#include <dsd-neo/runtime/rtl_stream_io_hooks.h>
#include <dsd-neo/runtime/rtl_stream_metrics_hooks.h>
#include "engine_hooks_install.h"
#include "nxdn_confirm.h"
#include "nxdn_test_support.h"
#include "symbol_test_support.h"
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { MAX_SAMPLES = 100000, MAX_EVENTS = 4096 };
static float wave[MAX_SAMPLES];
static uint32_t trace[MAX_SAMPLES];
static size_t length, provided, read_start, chunk, pop_count, frontier, skipped;
static unsigned errors, sequence, frame_count, dispatch_count, resets, crc_count, eof_reads;
static unsigned starts, tunes, rate_calls, reacquire_calls;
static int exhausted, observed, in_frame, current_frame = -1;
static char body[4096];
static size_t body_positions[4096];
static size_t body_count;

static void
prefix(const char* kind) {
    if (sequence >= MAX_EVENTS) { fprintf(stderr, "event bound exceeded\n"); exit(4); }
    printf("{\"seq\":%u,\"kind\":\"%s\",\"provided\":%zu,\"frontier\":%zu,\"pops\":%zu,"
           "\"eof\":%d,\"frame\":%d", sequence++, kind, provided, frontier, pop_count, exhausted, current_frame);
}

static void
snapshot(const dsd_state* s) {
    printf(",\"cache_pos\":%d,\"cache_len\":%d,\"read_start\":%zu,\"sync\":%d,\"last_sync\":%d,"
           "\"confirmed\":%d,\"streak\":%u,\"evidence\":%u,\"proved\":%d,\"verdict\":%d,"
           "\"profile_valid\":%d,\"profile_idx\":%d,\"profile_symbol\":%d,\"hunt_idx\":%d,"
           "\"hunt_counter\":%d,\"hunt_mark\":%d,\"hunt_entry\":%d,\"symbolcnt\":%d,\"pn95\":%d,"
           "\"carrier\":%d,\"rf_mod\":%d,\"sps\":%d,\"center\":%d,\"search_part_valid\":%d,"
           "\"ran\":%d,\"sacch_non_superframe\":%d,\"audio_indices\":[%d,%d,%d,%d]",
           s->rtl_symbol_cache_pos, s->rtl_symbol_cache_len, read_start, s->synctype, s->lastsynctype,
           s->nxdn_confirmed, (unsigned)s->nxdn_confirm_weak_streak, (unsigned)s->nxdn_confirm_frame_evidence,
           nxdn_confirm_frame_proved(s), s->sps_hunt_last_frame_verdict, s->profile_proof_valid,
           s->profile_proof_idx, s->profile_proof_symbolcnt, s->sps_hunt_idx, s->sps_hunt_counter,
           s->sps_hunt_symbolcnt_mark, s->sps_hunt_counter_at_entry, s->symbolcnt, s->nxdn_pn95_seed,
           s->carrier, s->rf_mod, s->samplesPerSymbol, s->symbolCenter,
           s->nxdn_search_part_valid, s->nxdn_last_ran, s->nxdn_sacch_non_superframe,
           s->audio_out_idx, s->audio_out_idx2, s->audio_out_idxR, s->audio_out_idx2R);
}

static void
mark(const char* kind, const dsd_state* s, int value) {
    prefix(kind); snapshot(s); printf(",\"value\":%d}\n", value);
}

int
xerax_record_sync(dsd_opts* opts, dsd_state* state) {
    mark("search_begin", state, 0);
    int result = getFrameSync(opts, state);
    mark("search_end", state, result);
    return result;
}

void
xerax_record_dispatch(dsd_opts* opts, dsd_state* state) {
    current_frame = (int)dispatch_count++;
    mark("dispatch_begin", state, 0);
    if (state->synctype != DSD_SYNC_NXDN_POS && state->synctype != DSD_SYNC_NXDN_NEG) { errors++; }
    processFrame(opts, state);
    mark("dispatch_end", state, 0);
    current_frame = -1;
}

int
xerax_record_frame(dsd_opts* opts, dsd_state* state) {
    frame_count++; body_count = 0; body[0] = 0;
    mark("frame_begin", state, 0);
    in_frame = 1;
    int result = nxdn_frame(opts, state);
    in_frame = 0;
    prefix("frame_end"); snapshot(state);
    printf(",\"value\":%d,\"body\":\"%s\",\"body_count\":%zu,\"body_positions\":[", result, body, body_count);
    for (size_t n = 0; n < body_count; n++) { printf("%s%zu", n ? "," : "", body_positions[n]); }
    printf("]}\n");
    return result;
}

void
noCarrier(dsd_opts* opts, dsd_state* state) {
    mark("reset_begin", state, 0);
    xerax_real_noCarrier(opts, state);
    resets++;
    mark("reset_end", state, 0);
}

/* Link-time observers: all permitted operations forward exactly once. */
int __real_getDibitSoft(dsd_opts* opts, dsd_state* state, dsd_dibit_soft_t* soft);
int __wrap_getDibitSoft(dsd_opts* opts, dsd_state* state, dsd_dibit_soft_t* soft);
int
__wrap_getDibitSoft(dsd_opts* opts, dsd_state* state, dsd_dibit_soft_t* soft) {
    int result = __real_getDibitSoft(opts, state, soft);
    if (in_frame) {
        if (body_count + 1U >= sizeof(body) || result < 0 || result > 3) { errors++; }
        else {
            body_positions[body_count] = read_start + (size_t)state->rtl_symbol_cache_pos;
            body[body_count++] = (char)('0' + result); body[body_count] = 0;
        }
    }
    return result;
}
int __wrap_rtl_stream_start(RtlSdrContext* ctx);
int __wrap_rtl_stream_tune(RtlSdrContext* ctx, uint32_t frequency);
int __wrap_rtl_stream_tune_tagged(RtlSdrContext* ctx, uint32_t frequency, uint64_t tag);
uint32_t __real_rtl_stream_output_rate(const RtlSdrContext* ctx);
uint32_t __wrap_rtl_stream_output_rate(const RtlSdrContext* ctx);
int __real_rtl_stream_request_fsk_reacquire(void);
int __wrap_rtl_stream_request_fsk_reacquire(void);
int __wrap_rtl_stream_start(RtlSdrContext* ctx) { (void)ctx; starts++; errors++; return -1; }
int __wrap_rtl_stream_tune(RtlSdrContext* ctx, uint32_t frequency) {
    (void)ctx; (void)frequency; tunes++; errors++; return -1;
}
int __wrap_rtl_stream_tune_tagged(RtlSdrContext* ctx, uint32_t frequency, uint64_t tag) {
    (void)ctx; (void)frequency; (void)tag; tunes++; errors++; return -1;
}
uint32_t
__wrap_rtl_stream_output_rate(const RtlSdrContext* ctx) {
    uint32_t result = __real_rtl_stream_output_rate(ctx);
    rate_calls++; prefix("backend_rate"); printf(",\"value\":%u}\n", result); return result;
}
int
__wrap_rtl_stream_request_fsk_reacquire(void) {
    int result = __real_rtl_stream_request_fsk_reacquire();
    reacquire_calls++; prefix("backend_reacquire"); printf(",\"value\":%d}\n", result); return result;
}

static int
provide(void* ctx, float* out, size_t count, int* got) {
    (void)ctx;
    if (!out || !got || !count) { errors++; return -1; }
    if (provided >= length) {
        exhausted = 1; eof_reads++; dsd_exitflag_store(1); *got = 0; return -1;
    }
    size_t want = count < chunk ? count : chunk;
    if (want > length - provided) { want = length - provided; }
    read_start = provided;
    memcpy(out, wave + provided, want * sizeof(float));
    provided += want; *got = (int)want; return 0;
}
static double power(const void* ctx) { (void)ctx; return 1.0; }
static int output_kind(void) { return RTL_STREAM_OUTPUT_FSK_DISCRIMINATOR; }
static unsigned output_rate(void) { return 48000; }
static uint32_t generation(void) { return 1; }
static int
profile(int* rate, int* levels, int* channel) {
    if (rate) { *rate = 2400; }
    if (levels) { *levels = 4; }
    if (channel) { *channel = RTL_STREAM_CHANNEL_PROFILE_6K25; }
    return 0;
}

static void
sample_observer(void* user, const dsd_state* state, uint32_t gen, int index, float sample) {
    (void)user;
    if (!state || gen != 1 || index < 0 || index >= state->rtl_symbol_cache_len) { errors++; return; }
    size_t absolute = read_start + (size_t)index;
    if (absolute >= length || pop_count >= MAX_SAMPLES || memcmp(&sample, wave + absolute, sizeof(sample))) {
        errors++; return;
    }
    if (absolute < frontier) { errors++; }
    else { skipped += absolute - frontier; }
    trace[pop_count++] = (uint32_t)absolute;
    frontier = absolute + 1;
}

static void
crc_observer(void* user, const dsd_state* state, const dsd_nxdn_test_crc_event* e) {
    (void)user;
    if (!e || e->info_bit_count > 80 || !in_frame) { errors++; return; }
    crc_count++; prefix("crc"); snapshot(state);
    printf(",\"channel\":%d,\"part\":%u,\"computed\":%u,\"received\":%u,\"soft_pass\":%d,"
           "\"fallback\":%d,\"bits\":\"", e->channel, (unsigned)e->frame_part, (unsigned)e->computed_crc,
           (unsigned)e->received_crc, e->soft_crc_pass, e->hard_fallback_used);
    for (size_t n = 0; n < e->info_bit_count; n++) { printf("%u", (unsigned)e->info_bits[n]); }
    printf("\"}\n");
}

static int
read_wave(const char* path) {
    FILE* file = fopen(path, "rb");
    if (!file) { return 1; }
    unsigned char bytes[4];
    for (;;) {
        size_t got = fread(bytes, 1, 4, file);
        if (!got) { break; }
        if (got != 4 || length >= MAX_SAMPLES) { fclose(file); return 1; }
        uint32_t bits = (uint32_t)bytes[0] | ((uint32_t)bytes[1] << 8) | ((uint32_t)bytes[2] << 16) | ((uint32_t)bytes[3] << 24);
        memcpy(wave + length, &bits, 4);
        if (!isfinite(wave[length++])) { fclose(file); return 1; }
    }
    int error = ferror(file);
    if (fclose(file)) { error = 1; }
    return error || !length;
}

static int
write_trace(const char* path) {
    FILE* file = fopen(path, "wb");
    if (!file) { return 1; }
    for (size_t n = 0; n < pop_count; n++) {
        uint32_t v = trace[n];
        unsigned char bytes[4] = {(unsigned char)v, (unsigned char)(v >> 8), (unsigned char)(v >> 16), (unsigned char)(v >> 24)};
        if (fwrite(bytes, 1, 4, file) != 4) { fclose(file); return 1; }
    }
    return fclose(file) != 0;
}

int
main(int argc, char** argv) {
    if (argc != 6 || (strcmp(argv[2], "0") && strcmp(argv[2], "1"))
        || (strcmp(argv[3], "37") && strcmp(argv[3], "512"))
        || (strcmp(argv[4], "0") && strcmp(argv[4], "1"))) { return 2; }
    if (read_wave(argv[1])) { return 3; }
    chunk = (size_t)atoi(argv[3]); observed = atoi(argv[4]);
    static dsd_opts opts;
    static dsd_state state;
    initOpts(&opts); initState(&state);
    opts.frame_dstar = opts.frame_x2tdma = opts.frame_p25p1 = opts.frame_p25p2 = 0;
    opts.frame_dmr = opts.frame_ysf = opts.frame_nxdn96 = opts.frame_dpmr = opts.frame_provoice = opts.frame_m17 = 0;
    opts.frame_nxdn48 = 1; opts.nxdn_fast_acquisition = atoi(argv[2]);
    opts.audio_in_type = AUDIO_IN_RTL; opts.audio_out = 0;
    opts.scanner_mode = opts.trunk_enable = opts.trunk_scan_enabled = opts.scan_voice_only = opts.scan_max_visit_ms = 0;
    opts.use_cosine_filter = 0; opts.msize = 1; opts.ssize = 128;
    state.rf_mod = 2; state.sps_hunt_idx = DSD_FRAME_SYNC_SPS_PROFILE_2400_4; state.nxdn_pn95_seed = 228;
    if (rtl_stream_create(&opts, &state.rtl_ctx) != 0 || !state.rtl_ctx) { freeState(&state); return 5; }
    dsd_exitflag_store(0); dsd_frame_sync_reset_mod_state();
    dsd_engine_frame_sync_hooks_install();
    dsd_rtl_stream_io_hooks_set((dsd_rtl_stream_io_hooks){.read = provide, .return_pwr = power});
    dsd_rtl_stream_metrics_hooks metrics = {.output_kind = output_kind, .output_rate_hz = output_rate,
        .symbol_profile = profile, .stream_generation = generation};
    dsd_rtl_stream_metrics_hooks_set(&metrics); dsd_rtl_stream_metrics_hook_symbol_cache_pending_reset();
    dsd_symbol_test_set_rtl_sample_observer(observed ? sample_observer : NULL, NULL);
    dsd_nxdn_test_set_crc_observer(observed ? crc_observer : NULL, NULL);
    prefix("configuration");
    printf(",\"audio_out\":%d,\"cosine_filter\":%d,\"scanner\":%d,\"trunk\":%d,\"trunk_scan\":%d,"
           "\"voice_gate\":%d,\"visit_ms\":%d,\"msize\":%d,\"ssize\":%d,\"nxdn48\":%d}\n",
           opts.audio_out, opts.use_cosine_filter, opts.scanner_mode, opts.trunk_enable, opts.trunk_scan_enabled,
           opts.scan_voice_only, opts.scan_max_visit_ms, opts.msize, opts.ssize, opts.frame_nxdn48);
    mark("initialized", &state, 0);
    xerax_run_live_loop(&opts, &state);
    mark("completed", &state, 0);
    dsd_symbol_test_set_rtl_sample_observer(NULL, NULL); dsd_nxdn_test_set_crc_observer(NULL, NULL);
    dsd_frame_sync_hooks_set((dsd_frame_sync_hooks){0});
    dsd_rtl_stream_io_hooks_set((dsd_rtl_stream_io_hooks){0}); dsd_rtl_stream_metrics_hooks_set(NULL);
    dsd_rtl_stream_metrics_hook_symbol_cache_pending_reset();
    if (rtl_stream_destroy(state.rtl_ctx)) { errors++; }
    state.rtl_ctx = NULL;
    if (opts.audio_out || opts.wav_out_f || opts.wav_out_fR || opts.wav_out_raw || opts.frame_log_f) { errors++; }
    freeState(&state);
    errors += (unsigned)write_trace(argv[5]);
    if (!exhausted || frame_count != dispatch_count) { errors++; }
    prefix("summary");
    printf(",\"samples\":%zu,\"skipped\":%zu,\"errors\":%u,\"frames\":%u,\"dispatches\":%u,\"resets\":%u,"
           "\"crcs\":%u,\"eof_reads\":%u,\"starts\":%u,\"tunes\":%u,\"rate_calls\":%u,\"reacquire_calls\":%u,"
           "\"observed\":%d,\"fast\":%d,\"chunk\":%zu,\"original_iq_samples\":null,\"pcm_latency\":null}\n",
           length, skipped, errors, frame_count, dispatch_count, resets, crc_count, eof_reads, starts, tunes,
           rate_calls, reacquire_calls, observed, opts.nxdn_fast_acquisition, chunk);
    return errors ? 1 : 0;
}
