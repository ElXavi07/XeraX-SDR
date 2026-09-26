/* SPDX-License-Identifier: GPL-3.0-or-later
 * Private, synchronous, single-receiver observation only. No receiver policy,
 * source oracle, replacement output, or production thread-safety claim. */
#include <dsd-neo/core/call_state.h>
#include <dsd-neo/core/key_presence.h>
#include <mbelib-neo/mbelib.h>
#include <inttypes.h>

/* Keep the frozen forwarding bodies; only their externally wrapped names move. */
#define __wrap_nxdn_voice routing_v2_nxdn_voice
#define __wrap_processMbeFrameSoft routing_v2_processMbeFrameSoft
#include "v2_observer_extra.inc"
#undef __wrap_nxdn_voice
#undef __wrap_processMbeFrameSoft

typedef struct {
    const dsd_state* state;
    const uint8_t* data;
    const uint8_t* reliability;
    int voice;
} routing_voice_context;

typedef struct {
    const dsd_state* state;
    int active, slot, voice;
    unsigned id, outer_fec, syntheses;
    int decode_success;
    const mbe_process_result* decode_result;
} routing_word_context;

static routing_voice_context routing_voice;
static routing_word_context routing_word;
static unsigned route_words, fec_hard_calls, fec_soft_calls;
static unsigned fec_outer_calls, fec_nested_calls, synthesis_calls, fec_call_count;
static unsigned fec_depth, fec_stack[64], routing_voice_depth;

static void
routing_snapshot(const dsd_state* state) {
    dsd_call_snapshot call = {0};
    const int present = dsd_call_state_get(state, 0U, &call);
    printf(",\"part_of_frame\":%d,\"cipher\":%u,\"search_ready\":%u,\"search_applied\":%u,"
           "\"manual_key\":%d,\"forced_cipher\":%d,\"keyloader\":%d,\"call\":",
           state->nxdn_part_of_frame, state->nxdn_cipher_type, (unsigned)state->nxdn_search.ready,
           (unsigned)state->nxdn_search.applied, dsd_key_scalar_present(state, 0), state->M, state->keyloader);
    if (present <= 0) {
        if (present < 0) { errors++; }
        printf("null");
        return;
    }
    printf("{\"present\":1,\"epoch\":%" PRIu64 ",\"phase\":%d,\"protocol\":%d,\"kind\":%d,"
           "\"source\":%" PRIu64 ",\"target\":%" PRIu64 ",\"policy_target\":%" PRIu64 ","
           "\"crypto\":%d,\"algid\":%u,\"kid\":%u,\"audio_permitted\":%u,"
           "\"media_active\":%u,\"end_reason\":%u}",
           call.epoch, (int)call.phase, call.protocol, (int)call.kind, call.ota_source_id,
           call.ota_target_id, call.policy_target_id, (int)call.crypto, (unsigned)call.algid,
           (unsigned)call.kid, (unsigned)call.audio_permitted, (unsigned)call.media_active,
           (unsigned)call.end_reason);
}

static void
routing_configuration(const dsd_opts* opts, const dsd_state* state) {
    (void)opts;
    printf(",\"routing_schema\":1,\"search_enabled\":%d,\"initial_manual_key\":%d,"
           "\"initial_forced_cipher\":%d,\"initial_cipher\":%u,\"initial_keyloader\":%d,"
           "\"initial_aes_key_loaded\":%d",
           dsd_nxdn_search_enabled(), dsd_key_scalar_present(state, 0), state->M,
           state->nxdn_cipher_type, state->keyloader, state->aes_key_loaded[0]);
}

static void
routing_final_check(void) {
    if (routing_word.active || routing_voice_depth || fec_depth) { errors++; }
}

static void
routing_summary(void) {
    printf(",\"route_words\":%u,\"fec_hard_calls\":%u,\"fec_soft_calls\":%u,"
           "\"fec_outer_calls\":%u,\"fec_nested_calls\":%u,\"synthesis_calls\":%u",
           route_words, fec_hard_calls, fec_soft_calls, fec_outer_calls, fec_nested_calls, synthesis_calls);
}

static void
routing_print_bits(const char* bits, size_t count) {
    if (!bits) { printf("null"); return; }
    printf("\"");
    for (size_t n = 0; n < count; n++) {
        const int bit = (int)bits[n];
        if (bit != 0 && bit != 1) { errors++; }
        /* An invalid value stays visible and fails the strict bit-string schema. */
        printf("%d", bit);
    }
    printf("\"");
}

static void
routing_print_result(const mbe_process_result* result) {
    if (!result) { printf("null"); return; }
    printf("{\"c0_errors\":%d,\"protected_errors\":%d,\"c4_errors\":%d,"
           "\"total_errors\":%d,\"flags\":%u}", result->c0_errors, result->protected_errors,
           result->c4_errors, result->total_errors, result->flags);
}

static void
routing_prefix(const char* kind) {
    prefix(kind);
    if (routing_word.state) { snapshot(routing_word.state); }
    else { errors++; }
    printf(",\"route_id\":");
    if (routing_word.active) { printf("%u", routing_word.id); }
    else { printf("null"); errors++; }
}

static void
routing_route_mark(const char* kind, const char* mode) {
    routing_prefix(kind);
    printf(",\"slot\":%d,\"voice\":%d,\"mode\":\"%s\",\"fec_outer\":%u,\"syntheses\":%u}\n",
           routing_word.slot, routing_word.voice, mode, routing_word.outer_fec, routing_word.syntheses);
}

static void
routing_begin_word(dsd_state* state, const char* mode) {
    if (routing_word.active || !in_frame || routing_voice.state != state || !routing_voice.data
        || state->nxdn_search_voice_index < 0 || state->nxdn_search_voice_index > 3) { errors++; }
    routing_word = (routing_word_context){.state = state, .active = 1,
        .slot = state->nxdn_search_voice_index, .voice = routing_voice.voice, .id = route_words++};
    routing_route_mark("route_begin", mode);
}

void __wrap_nxdn_voice(dsd_opts*, dsd_state*, int, uint8_t[182], const uint8_t*);
void
__wrap_nxdn_voice(dsd_opts* opts, dsd_state* state, int voice, uint8_t data[182], const uint8_t* reliability) {
    const routing_voice_context saved = routing_voice;
    if (routing_voice_depth) { errors++; }
    routing_voice_depth++;
    routing_voice = (routing_voice_context){.state = state, .data = data, .reliability = reliability, .voice = voice};
    routing_v2_nxdn_voice(opts, state, voice, data, reliability);
    routing_voice = saved;
    routing_voice_depth--;
}

void __wrap_processMbeFrameSoft(dsd_opts*, dsd_state*, dsd_vocoder_soft_bit[8][23],
    dsd_vocoder_soft_bit[4][24], dsd_vocoder_soft_bit[7][24]);
void
__wrap_processMbeFrameSoft(dsd_opts* opts, dsd_state* state, dsd_vocoder_soft_bit imbe[8][23],
    dsd_vocoder_soft_bit ambe[4][24], dsd_vocoder_soft_bit imbe7100[7][24]) {
    const routing_word_context saved = routing_word;
    routing_begin_word(state, "soft");
    routing_v2_processMbeFrameSoft(opts, state, imbe, ambe, imbe7100);
    routing_route_mark("route_end", "soft");
    routing_word = saved;
}

void __real_processMbeFrame(dsd_opts*, dsd_state*, char[8][23], char[4][24], char[7][24]);
void __wrap_processMbeFrame(dsd_opts*, dsd_state*, char[8][23], char[4][24], char[7][24]);
void
__wrap_processMbeFrame(dsd_opts* opts, dsd_state* state, char imbe[8][23], char ambe[4][24], char imbe7100[7][24]) {
    const routing_word_context saved = routing_word;
    routing_begin_word(state, "hard");
    v2_mbe_calls++;
    if (observed) { mark("mbe_begin", state, 0); }
    __real_processMbeFrame(opts, state, imbe, ambe, imbe7100);
    if (observed) { mark("mbe_end", state, 0); }
    routing_route_mark("route_end", "hard");
    routing_word = saved;
}

typedef struct {
    unsigned id, depth;
    int parent;
    const char* mode;
} routing_fec_context;

static routing_fec_context
routing_fec_begin(const char* mode) {
    routing_fec_context call = {.id = fec_call_count++, .depth = fec_depth + 1U, .parent = -1, .mode = mode};
    if (fec_depth && fec_depth <= sizeof(fec_stack) / sizeof(fec_stack[0])) {
        call.parent = (int)fec_stack[fec_depth - 1U];
    }
    if (fec_depth < sizeof(fec_stack) / sizeof(fec_stack[0])) { fec_stack[fec_depth] = call.id; }
    else { errors++; }
    if (!fec_depth) { fec_outer_calls++; routing_word.outer_fec++; routing_word.decode_success = 0; }
    else { fec_nested_calls++; }
    fec_depth++;
    if (!routing_word.active || !in_frame) { errors++; }
    return call;
}

static void
routing_fec_fields(const routing_fec_context* call) {
    printf(",\"call_id\":%u,\"parent_call_id\":", call->id);
    if (call->parent < 0) { printf("null"); }
    else { printf("%d", call->parent); }
    printf(",\"depth\":%u,\"outer\":%d,\"mode\":\"%s\"", call->depth, call->depth == 1U, call->mode);
}

static void
routing_fec_input(const routing_fec_context* call, const char bits[96], const uint8_t* reliability) {
    if (!observed) { return; }
    routing_prefix("fec_input"); routing_fec_fields(call);
    printf(",\"matrix96\":"); routing_print_bits(bits, 96U);
    printf(",\"reliability\":");
    if (!reliability) { printf("null"); }
    else {
        printf("[");
        for (size_t n = 0; n < 96U; n++) { printf("%s%u", n ? "," : "", (unsigned)reliability[n]); }
        printf("]");
    }
    const int valid = routing_voice.data && routing_word.slot >= 0 && routing_word.slot < 4;
    printf(",\"channel72\":");
    if (!valid) { printf("null"); errors++; }
    else {
        printf("\"");
        for (int n = 0; n < 36; n++) {
            const uint8_t dibit = routing_voice.data[38 + 36 * routing_word.slot + n];
            if (dibit > 3U) { errors++; }
            printf("%u%u", (unsigned)(dibit >> 1), (unsigned)(dibit & 1U));
        }
        printf("\"");
    }
    printf(",\"channel_dibits\":");
    if (!valid) { printf("null"); }
    else {
        printf("\"");
        for (int n = 0; n < 36; n++) { printf("%u", (unsigned)routing_voice.data[38 + 36 * routing_word.slot + n]); }
        printf("\"");
    }
    printf(",\"channel_reliability\":");
    if (!valid || !routing_voice.reliability) { printf("null"); }
    else {
        printf("[");
        for (int n = 0; n < 36; n++) {
            printf("%s%u", n ? "," : "", (unsigned)routing_voice.reliability[38 + 36 * routing_word.slot + n]);
        }
        printf("]");
    }
    printf("}\n");
}

static void
routing_fec_end(const routing_fec_context* call, int status, const char* output,
    const mbe_process_result* result, int unchanged) {
    routing_prefix("fec"); routing_fec_fields(call);
    printf(",\"status\":%d,\"bits49\":", status);
    routing_print_bits(status >= 0 ? output : NULL, 49U);
    printf(",\"result\":"); routing_print_result(status >= 0 ? result : NULL);
    printf(",\"input_unchanged\":%d}\n", unchanged);
    if (call->depth == 1U) {
        routing_word.decode_success = status >= 0;
        routing_word.decode_result = status >= 0 ? result : NULL;
    }
    if (!fec_depth || fec_depth != call->depth) { errors++; }
    if (fec_depth) { fec_depth--; }
}

int __real_mbe_decodeAmbe3600x2450Frame(const char[4][24], char[49], mbe_process_result*);
int __wrap_mbe_decodeAmbe3600x2450Frame(const char[4][24], char[49], mbe_process_result*);
int
__wrap_mbe_decodeAmbe3600x2450Frame(const char input[4][24], char output[49], mbe_process_result* result) {
    char before[96] = {0};
    fec_hard_calls++;
    const routing_fec_context call = routing_fec_begin("hard");
    if (input) {
        for (size_t r = 0; r < 4U; r++) {
            for (size_t c = 0; c < 24U; c++) { before[r * 24U + c] = input[r][c]; }
        }
    } else { errors++; }
    routing_fec_input(&call, before, NULL);
    /* Do not read output or the caller's uninitialized result before this call. */
    const int status = __real_mbe_decodeAmbe3600x2450Frame(input, output, result);
    int unchanged = input != NULL;
    if (input) {
        for (size_t r = 0; r < 4U; r++) {
            for (size_t c = 0; c < 24U; c++) { unchanged &= before[r * 24U + c] == input[r][c]; }
        }
    }
    routing_fec_end(&call, status, output, result, unchanged);
    return status;
}

int __real_mbe_decodeAmbe3600x2450SoftFrame(const mbe_soft_bit[4][24], char[49], mbe_process_result*);
int __wrap_mbe_decodeAmbe3600x2450SoftFrame(const mbe_soft_bit[4][24], char[49], mbe_process_result*);
int
__wrap_mbe_decodeAmbe3600x2450SoftFrame(const mbe_soft_bit input[4][24], char output[49], mbe_process_result* result) {
    char before[96] = {0};
    uint8_t reliability[96] = {0};
    fec_soft_calls++;
    const routing_fec_context call = routing_fec_begin("soft");
    if (input) {
        for (size_t r = 0; r < 4U; r++) {
            for (size_t c = 0; c < 24U; c++) {
                before[r * 24U + c] = (char)input[r][c].bit;
                reliability[r * 24U + c] = input[r][c].reliability;
            }
        }
    } else { errors++; }
    routing_fec_input(&call, before, reliability);
    const int status = __real_mbe_decodeAmbe3600x2450SoftFrame(input, output, result);
    int unchanged = input != NULL;
    if (input) {
        for (size_t r = 0; r < 4U; r++) {
            for (size_t c = 0; c < 24U; c++) {
                unchanged &= (uint8_t)before[r * 24U + c] == input[r][c].bit
                    && reliability[r * 24U + c] == input[r][c].reliability;
            }
        }
    }
    routing_fec_end(&call, status, output, result, unchanged);
    return status;
}

int __real_mbe_processAmbe2450Dataf(float*, mbe_process_result*, const char[49], mbe_parms*, mbe_parms*, mbe_parms*);
int __wrap_mbe_processAmbe2450Dataf(float*, mbe_process_result*, const char[49], mbe_parms*, mbe_parms*, mbe_parms*);
int
__wrap_mbe_processAmbe2450Dataf(float* output, mbe_process_result* result, const char input[49],
    mbe_parms* current, mbe_parms* previous, mbe_parms* enhanced) {
    const unsigned id = synthesis_calls++;
    routing_word.syntheses++;
    char before[49] = {0};
    if (input) { memcpy(before, input, sizeof(before)); }
    else { errors++; }
    /* Only the actual successfully returned decode context is known initialized. */
    const int have_before = routing_word.active && routing_word.decode_success && result
        && result == routing_word.decode_result;
    mbe_process_result result_before = {0};
    if (have_before) {
        result_before.c0_errors = result->c0_errors;
        result_before.protected_errors = result->protected_errors;
        result_before.c4_errors = result->c4_errors;
        result_before.total_errors = result->total_errors;
        result_before.flags = result->flags;
    } else { errors++; }
    const int status = __real_mbe_processAmbe2450Dataf(output, result, input, current, previous, enhanced);
    const int unchanged = input && memcmp(before, input, sizeof(before)) == 0;
    routing_prefix("synthesis");
    printf(",\"call_id\":%u,\"input49\":", id); routing_print_bits(input ? before : NULL, 49U);
    printf(",\"result_before\":"); routing_print_result(have_before ? &result_before : NULL);
    printf(",\"status\":%d,\"result_after\":", status);
    routing_print_result(status >= 0 ? result : NULL);
    printf(",\"input_unchanged\":%d}\n", unchanged);
    return status;
}
