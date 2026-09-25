// SPDX-License-Identifier: GPL-3.0-or-later
/* Single-receiver research adapter. No installed target links this module. */
#include "phase_runtime.h"
#include <dsd-neo/core/constants.h>
#include <dsd-neo/core/opts.h>
#include <dsd-neo/core/state.h>
#include <stdio.h>

#ifndef XERAX_BOUNDARY_ENABLED
#error Boundary baseline/candidate identity must be explicit
#endif
static nxdn_boundary_v1_state phase;
static FILE* log_file;
static const void* receiver;
static unsigned sequence, frames, matches, resets, arms, vetoes, errors;

static void
prefix(const char* kind) {
    if (log_file) {
        fprintf(log_file, "{\"seq\":%u,\"kind\":\"%s\"", sequence++, kind);
    }
}

static void
context_json(const nxdn_boundary_v1_context* ctx) {
    fprintf(log_file, "{\"symbols\":%u,\"generation\":%u,\"profile\":%d,\"sps\":%d,\"rf\":%d,"
                     "\"eligible\":%d,\"confirmed\":%d,\"owner\":%d}",
            (unsigned)ctx->symbols, (unsigned)ctx->generation, ctx->profile, ctx->sps, ctx->rf,
            ctx->eligible, ctx->confirmed, ctx->owner == receiver ? 1 : 2);
}

static void
anchor_json(void) {
    fprintf(log_file, ",\"anchor\":");
    if (phase.valid) { context_json(&phase.anchor); }
    else { fprintf(log_file, "null"); }
}

int
nxdn_boundary_runtime_open(const char* path) {
    log_file = fopen(path, "wb");
    if (!log_file) { return 1; }
    nxdn_boundary_v1_reset(&phase);
    receiver = NULL;
    sequence = frames = matches = resets = arms = vetoes = errors = 0;
    prefix("configuration");
    fprintf(log_file, ",\"enabled\":%d}\n", XERAX_BOUNDARY_ENABLED);
    return 0;
}

int
nxdn_boundary_runtime_close(void) {
    if (!log_file) { return 1; }
    prefix("summary");
    fprintf(log_file, ",\"enabled\":%d,\"frames\":%u,\"matches\":%u,\"resets\":%u,\"arms\":%u,"
                     "\"vetoes\":%u,\"errors\":%u}\n", XERAX_BOUNDARY_ENABLED,
            frames, matches, resets, arms, vetoes, errors);
    int bad = ferror(log_file) || errors != 0;
    if (fclose(log_file)) { bad = 1; }
    log_file = NULL;
    return bad;
}

void
nxdn_boundary_runtime_reset(const char* reason) {
    const int before = phase.valid;
    nxdn_boundary_v1_reset(&phase);
    if (!log_file) { return; }
    resets++;
    prefix("reset");
    fprintf(log_file, ",\"reason\":\"%s\",\"valid_before\":%d,\"valid_after\":0}\n", reason, before);
}

nxdn_boundary_v1_context
nxdn_boundary_runtime_context(const dsd_opts* opts, const dsd_state* state) {
    if (!receiver) { receiver = state; }
    if (receiver != state) { errors++; }
    const int eligible = opts->audio_in_type == AUDIO_IN_RTL && opts->frame_nxdn48 == 1
        && !opts->frame_nxdn96 && !opts->frame_dpmr && !opts->frame_dmr && !opts->frame_p25p1
        && !opts->frame_p25p2 && !opts->frame_dstar && !opts->frame_x2tdma && !opts->frame_provoice
        && !opts->frame_ysf && !opts->frame_m17 && !opts->use_cosine_filter && !opts->datascope
        && !opts->scanner_mode && !opts->trunk_enable && !opts->trunk_scan_enabled
        && state->samplesPerSymbol == 20 && state->rf_mod == 2;
    return (nxdn_boundary_v1_context){.symbols = (uint32_t)state->symbolcnt,
        .generation = state->rtl_symbol_cache_generation, .profile = state->sps_hunt_idx,
        .sps = state->samplesPerSymbol, .rf = state->rf_mod, .eligible = eligible,
        .confirmed = state->nxdn_confirmed != 0, .owner = state};
}

void
nxdn_boundary_runtime_frame(const nxdn_boundary_v1_context* begin,
                             const dsd_opts* opts, const dsd_state* state, int result) {
    const nxdn_boundary_v1_context end = nxdn_boundary_runtime_context(opts, state);
    const int before = phase.valid;
    const int armed = nxdn_boundary_v1_note_frame(&phase, begin, &end, result);
    arms += (unsigned)armed;
    if (!log_file) { errors++; return; }
    prefix("frame");
    fprintf(log_file, ",\"frame\":%u,\"begin\":", frames++); context_json(begin);
    fprintf(log_file, ",\"end\":"); context_json(&end);
    fprintf(log_file, ",\"result\":%d,\"armed\":%d,\"valid_before\":%d,\"valid_after\":%d",
            result, armed, before, phase.valid);
    anchor_json(); fprintf(log_file, "}\n");
}

int
nxdn_boundary_runtime_allow(const dsd_opts* opts, const dsd_state* state, const char* pattern) {
    const nxdn_boundary_v1_context now = nxdn_boundary_runtime_context(opts, state);
    const nxdn_boundary_v1_decision d = nxdn_boundary_v1_decide(&phase, &now, pattern, XERAX_BOUNDARY_ENABLED);
    matches++; vetoes += (unsigned)!d.allow;
    if (!log_file) { errors++; return d.allow; }
    prefix("match");
    fprintf(log_file, ",\"next_frame\":%u,\"context\":", frames); context_json(&now);
    fprintf(log_file, ",\"pattern\":\"%s\",\"decision\":{\"allow\":%d,\"would_block\":%d,"
        "\"canonical\":%d,\"window\":%d,\"age\":%u,\"reason\":\"%s\",\"valid_before\":%d,\"valid_after\":%d}",
        pattern, d.allow, d.would_block, d.canonical, d.window, (unsigned)d.age,
        nxdn_boundary_v1_reason_name(d.reason), d.valid_before, d.valid_after);
    anchor_json(); fprintf(log_file, "}\n");
    return d.allow;
}
