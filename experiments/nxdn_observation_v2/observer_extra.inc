/* Included only in the generated private recorder after its common mark(). */
#include <dsd-neo/core/audio.h>
#include <dsd-neo/core/vocoder.h>
#include <dsd-neo/protocol/nxdn/nxdn_voice.h>

typedef struct {
    size_t before, after;
    int eof_before, eof_after;
    unsigned symbol_before, symbol_after;
} v2_call;
static v2_call v2_calls[4096];
static unsigned v2_lich_events, v2_scch_events, v2_voice_calls, v2_mbe_calls, v2_audio_calls;

static size_t
v2_consumed(const dsd_state* state) {
    return exhausted ? length : read_start + (size_t)state->rtl_symbol_cache_pos;
}

static void
v2_dump_body_calls(void) {
    printf(",\"body_calls\":[");
    for (size_t n = 0; n < body_count; n++) {
        const v2_call* c = &v2_calls[n];
        printf("%s{\"before\":%zu,\"after\":%zu,\"eof_before\":%d,\"eof_after\":%d,"
               "\"symbol_before\":%u,\"symbol_after\":%u}", n ? "," : "", c->before, c->after,
               c->eof_before, c->eof_after, c->symbol_before, c->symbol_after);
    }
    printf("]");
}

void
xerax_v2_lich(const dsd_state* state, const char* reason, int result,
    int full, int lich, int received, int computed, int voice, int scch,
    int pich_tch, int idas, int sacch, int facch) {
    v2_lich_events++;
    if (!in_frame) { errors++; }
    if (!observed) { return; }
    prefix("lich"); snapshot(state);
    printf(",\"result\":%d,\"reason\":\"%s\",\"full_lich\":%d,\"lich\":%d,"
           "\"parity_received\":%d,\"parity_computed\":%d,\"voice\":%d,\"scch\":%d,"
           "\"pich_tch\":%d,\"idas\":%d,\"sacch\":%d,\"facch\":%d}\n",
           result, reason, full, lich, received, computed, voice, scch, pich_tch, idas, sacch, facch);
}

void
xerax_v2_scch(const dsd_state* state, const uint8_t* bits, unsigned computed,
    unsigned received, int soft_pass, int direction) {
    v2_scch_events++;
    if (!in_frame || !bits) { errors++; return; }
    if (!observed) { return; }
    prefix("scch"); snapshot(state);
    printf(",\"computed\":%u,\"received\":%u,\"soft_pass\":%d,\"fallback\":%d,\"direction\":%d,\"bits\":\"",
           computed, received, soft_pass, !soft_pass, direction);
    for (int n = 0; n < 25; n++) { printf("%u", (unsigned)bits[n]); }
    printf("\",\"check_bits\":\"");
    for (int n = 25; n < 32; n++) { printf("%u", (unsigned)bits[n]); }
    printf("\"}\n");
}

void __real_nxdn_voice(dsd_opts*, dsd_state*, int, uint8_t[182], const uint8_t*);
void __wrap_nxdn_voice(dsd_opts*, dsd_state*, int, uint8_t[182], const uint8_t*);
void
__wrap_nxdn_voice(dsd_opts* opts, dsd_state* state, int voice, uint8_t data[182], const uint8_t* reliability) {
    v2_voice_calls++;
    if (!in_frame) { errors++; }
    if (observed) { mark("voice_begin", state, voice); }
    __real_nxdn_voice(opts, state, voice, data, reliability);
    if (observed) { mark("voice_end", state, voice); }
}

void __real_processMbeFrameSoft(dsd_opts*, dsd_state*, dsd_vocoder_soft_bit[8][23],
    dsd_vocoder_soft_bit[4][24], dsd_vocoder_soft_bit[7][24]);
void __wrap_processMbeFrameSoft(dsd_opts*, dsd_state*, dsd_vocoder_soft_bit[8][23],
    dsd_vocoder_soft_bit[4][24], dsd_vocoder_soft_bit[7][24]);
void
__wrap_processMbeFrameSoft(dsd_opts* opts, dsd_state* state, dsd_vocoder_soft_bit imbe[8][23],
    dsd_vocoder_soft_bit ambe[4][24], dsd_vocoder_soft_bit imbe7100[7][24]) {
    v2_mbe_calls++;
    if (!in_frame) { errors++; }
    if (observed) { mark("mbe_begin", state, 0); }
    __real_processMbeFrameSoft(opts, state, imbe, ambe, imbe7100);
    if (observed) { mark("mbe_end", state, 0); }
}

void __real_processAudio(const dsd_opts*, dsd_state*);
void __wrap_processAudio(const dsd_opts*, dsd_state*);
void
__wrap_processAudio(const dsd_opts* opts, dsd_state* state) {
    v2_audio_calls++;
    if (!in_frame) { errors++; }
    if (observed) { mark("audio_begin", state, 0); }
    __real_processAudio(opts, state);
    if (!observed) { return; }
    unsigned finite = 0, nonzero = 0, short_nonzero = 0, short_peak = 0;
    uint32_t checksum = UINT32_C(2166136261);
    double peak = 0.0, energy = 0.0;
    for (size_t n = 0; n < 160; n++) {
        double sample = state->audio_out_temp_buf[n];
        if (isfinite(sample)) {
            finite++; nonzero += sample != 0.0;
            double absolute = fabs(sample);
            if (absolute > peak) { peak = absolute; }
            energy += sample * sample;
        }
        int16_t pcm = state->s_l[n];
        unsigned magnitude = (unsigned)(pcm < 0 ? -(int)pcm : (int)pcm);
        short_nonzero += pcm != 0;
        if (magnitude > short_peak) { short_peak = magnitude; }
        uint16_t bits = (uint16_t)pcm;
        checksum = (checksum ^ (bits & 255U)) * UINT32_C(16777619);
        checksum = (checksum ^ (bits >> 8)) * UINT32_C(16777619);
    }
    prefix("audio_end"); snapshot(state);
    printf(",\"value\":0,\"pcm_domain\":\"internal_post_gain_float160_and_staged_short160\","
           "\"float_finite\":%u,\"float_nonzero\":%u,\"float_peak\":%.17g,\"float_energy\":%.17g,"
           "\"short_nonzero\":%u,\"short_peak\":%u,\"short_checksum\":%u}\n",
           finite, nonzero, peak, energy, short_nonzero, short_peak, (unsigned)checksum);
}
