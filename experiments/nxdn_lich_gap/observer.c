// SPDX-License-Identifier: GPL-3.0-or-later
/* Real frame/FEC/CRC, finite independent dibit input; no radio, sync search or voice. */
#include <dsd-neo/core/dibit.h>
#include <dsd-neo/core/opts.h>
#include <dsd-neo/core/state.h>
#include <dsd-neo/core/synctype_ids.h>
#include <dsd-neo/protocol/nxdn/nxdn.h>
#include "nxdn_confirm.h"
#include "nxdn_test_support.h"
#include "../nxdn_frames/side_effect_sinks.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint8_t vectors[2][6][192];
static const uint8_t* input;
static size_t position;
static int errors;
static dsd_nxdn_test_crc_event events[3];
static size_t event_count;
static const char vector_kinds[] = "WSCPUD";

int
getDibitSoft(dsd_opts* opts, dsd_state* state, dsd_dibit_soft_t* soft) {
    (void)opts; (void)state;
    if (soft) { memset(soft, 0, sizeof(*soft)); soft->reliability = 255; }
    if (position >= 192U) { errors++; return 0; }
    return input[position++];
}

static void
observe(void* user, const dsd_state* state, const dsd_nxdn_test_crc_event* event) {
    (void)user; (void)state;
    if (!event || event_count >= 3U) { errors++; return; }
    events[event_count++] = *event;
}

static void
print_events(void) {
    printf("[");
    for (size_t n = 0; n < event_count; n++) {
        const dsd_nxdn_test_crc_event* event = &events[n];
        if (n) { printf(","); }
        printf("{\"channel\":%d,\"part\":%u,\"computed\":%u,\"received\":%u,"
               "\"soft_pass\":%d,\"fallback\":%d,\"bits\":\"",
               event->channel, (unsigned)event->frame_part, (unsigned)event->computed_crc,
               (unsigned)event->received_crc, event->soft_crc_pass, event->hard_fallback_used);
        for (size_t b = 0; b < event->info_bit_count; b++) { printf("%u", (unsigned)event->info_bits[b]); }
        printf("\"}");
    }
    printf("]");
}

static void
run_sequence(int payload, int enabled, const char* name, const char* sequence) {
    static dsd_opts opts;
    static dsd_state state;
    memset(&opts, 0, sizeof(opts));
    memset(&state, 0, sizeof(state));
    memset(&xerax_effects, 0, sizeof(xerax_effects));
    opts.frame_nxdn48 = 1;
    opts.scanner_mode = 1;
    state.nxdn_pn95_seed = 228;
    state.nxdn_last_ran = -1;
    dsd_nxdn_test_set_crc_observer(enabled ? observe : NULL, NULL);
    for (size_t step = 0; sequence[step]; step++) {
        const char kind = sequence[step];
        position = 10U; event_count = 0;
        memset(events, 0, sizeof(events));
        state.last_cc_sync_time = 123;
        state.last_cc_sync_time_m = 7.0;
        state.synctype = state.lastsynctype = DSD_SYNC_NXDN_POS;
        opts.trunk_enable = kind == 'D';
        int result = -1;
        if (kind == 'R') {
            nxdn_confirm_reset(&state);
        } else {
            const char* found = strchr(vector_kinds, kind);
            if (!found) { errors++; return; }
            input = vectors[payload][found - vector_kinds];
            result = nxdn_frame(&opts, &state);
        }
        printf("{\"payload\":%d,\"observed\":%d,\"sequence\":\"%s\",\"step\":%zu,"
               "\"kind\":\"%c\",\"consumed\":%zu,\"result\":%d,\"confirmed\":%d,"
               "\"streak\":%u,\"evidence\":%u,\"proved\":%d,\"carrier\":%d,"
               "\"clock_changed\":%d,\"mono_changed\":%d,\"voice\":%d,\"content\":%zu,"
               "\"errors\":%d,\"read_dibits\":\"",
               payload, enabled, name, step, kind, position - 10U, result, state.nxdn_confirmed,
               (unsigned)state.nxdn_confirm_weak_streak, (unsigned)state.nxdn_confirm_frame_evidence,
               nxdn_confirm_frame_proved(&state), state.carrier,
               state.last_cc_sync_time != 123, state.last_cc_sync_time_m != 7.0,
               xerax_effects.voice_requests, xerax_effects.count, errors + xerax_effects.errors);
        if (kind != 'R') {
            for (size_t d = 10; d < position; d++) { printf("%u", (unsigned)input[d]); }
        }
        printf("\",\"events\":");
        print_events(); printf("}\n");
    }
    dsd_nxdn_test_set_crc_observer(NULL, NULL);
}

int
main(int argc, char** argv) {
    if (argc != 2) { fprintf(stderr, "usage: observer VECTOR_DIRECTORY\n"); return 2; }
    for (int payload = 0; payload < 2; payload++) {
        for (size_t kind = 0; kind < 6U; kind++) {
            char filename[4096];
            if (snprintf(filename, sizeof(filename), "%s/%d-%c.dibits", argv[1], payload, "WSCPUD"[kind]) < 0) { return 3; }
            FILE* file = fopen(filename, "rb");
            if (!file) { return 3; }
            const size_t count = fread(vectors[payload][kind], 1, 192, file);
            const int extra = fgetc(file);
            fclose(file);
            if (count != 192 || extra != EOF) { return 3; }
            for (size_t d = 0; d < 192; d++) { if (vectors[payload][kind][d] > 3) { return 3; } }
        }
    }
    static const char* const names[] = {
        "adjacent_weak", "parity_gap", "unsupported_gap", "direction_gap", "crc_gap", "strong_parity",
        "reset_weak", "reset_strong", "adjacent_strong", "rejected_before_weak", "confirmed_crc_gap"};
    static const char* const sequences[] = {"WW", "WPWW", "WUWW", "WDWW", "WCWW", "SPW", "WRWW", "SRWW", "SS", "PPWW", "SCW"};
    for (int payload = 0; payload < 2; payload++) {
        for (int enabled = 0; enabled < 2; enabled++) {
            for (size_t n = 0; n < sizeof(names) / sizeof(names[0]); n++) {
                run_sequence(payload, enabled, names[n], sequences[n]);
            }
        }
    }
    return errors ? 1 : 0;
}
