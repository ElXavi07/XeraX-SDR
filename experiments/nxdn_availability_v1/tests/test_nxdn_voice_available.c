// SPDX-License-Identifier: GPL-3.0-or-later

#include <dsd-neo/core/audio.h>
#include <dsd-neo/core/opts.h>
#include <dsd-neo/core/opts_fwd.h>
#include <dsd-neo/core/safe_api.h>
#include <dsd-neo/core/state.h>
#include <dsd-neo/core/state_fwd.h>
#include <dsd-neo/core/vocoder.h>
#include <dsd-neo/protocol/nxdn/nxdn_voice.h>

#include <stdint.h>
#include <stdio.h>

static int g_hard_calls;
static int g_soft_calls;
static int g_play_ms_calls;
static int g_play_fm_calls;
static char g_last_hard[4][24];
static dsd_vocoder_soft_bit g_last_soft[4][24];
static dsd_opts g_opts;
static dsd_state g_state;
static int g_seen_slots[4];
static char g_seen_bits[4][4][24];
static uint8_t g_seen_reliability[4][4][24];

static int
expect_int(const char* label, int got, int want) {
    if (got != want) {
        DSD_FPRINTF(stderr, "%s: got %d want %d\n", label, got, want);
        return 1;
    }
    return 0;
}

static int
expect_float(const char* label, float got, float want) {
    float delta = got - want;
    if (delta < 0.0f) {
        delta = -delta;
    }
    if (delta > 1e-6f) {
        DSD_FPRINTF(stderr, "%s: got %.6f want %.6f\n", label, got, want);
        return 1;
    }
    return 0;
}

static void
reset_spies(void) {
    g_hard_calls = 0;
    g_soft_calls = 0;
    g_play_ms_calls = 0;
    g_play_fm_calls = 0;
    DSD_MEMSET(g_last_hard, 0, sizeof(g_last_hard));
    DSD_MEMSET(g_last_soft, 0, sizeof(g_last_soft));
    DSD_MEMSET(g_seen_slots, 0, sizeof(g_seen_slots));
    DSD_MEMSET(g_seen_bits, 0, sizeof(g_seen_bits));
    DSD_MEMSET(g_seen_reliability, 0, sizeof(g_seen_reliability));
}

static void
reset_decoder_objects(void) {
    DSD_MEMSET(&g_opts, 0, sizeof(g_opts));
    DSD_MEMSET(&g_state, 0, sizeof(g_state));
}

static void
fill_dibits(uint8_t dbuf[182], uint8_t reliab[182]) {
    for (int i = 0; i < 182; i++) {
        dbuf[i] = (uint8_t)(((i & 1) << 1) | ((i >> 1) & 1));
        reliab[i] = (uint8_t)(200 - i);
    }
}

void
processMbeFrame(dsd_opts* opts, dsd_state* state, char imbe_fr[8][23], char ambe_fr[4][24], char imbe7100_fr[7][24]) {
    (void)opts;
    (void)imbe_fr;
    (void)imbe7100_fr;
    g_hard_calls++;
    if (g_hard_calls <= 4) {
        g_seen_slots[g_hard_calls - 1] = state->nxdn_search_voice_index;
        DSD_MEMCPY(g_seen_bits[g_hard_calls - 1], ambe_fr, sizeof(g_seen_bits[0]));
    }
    DSD_MEMCPY(g_last_hard, ambe_fr, sizeof(g_last_hard));
    for (int i = 0; i < 160; i++) {
        state->audio_out_temp_buf[i] = (float)(g_hard_calls * 1000 + i);
    }
}

void
processMbeFrameSoft(dsd_opts* opts, dsd_state* state, dsd_vocoder_soft_bit imbe_fr[8][23],
                    dsd_vocoder_soft_bit ambe_fr[4][24], dsd_vocoder_soft_bit imbe7100_fr[7][24]) {
    (void)opts;
    (void)imbe_fr;
    (void)imbe7100_fr;
    g_soft_calls++;
    if (g_soft_calls <= 4) {
        g_seen_slots[g_soft_calls - 1] = state->nxdn_search_voice_index;
        for (int row = 0; row < 4; row++) {
            for (int col = 0; col < 24; col++) {
                g_seen_bits[g_soft_calls - 1][row][col] = (char)ambe_fr[row][col].bit;
                g_seen_reliability[g_soft_calls - 1][row][col] = ambe_fr[row][col].reliability;
            }
        }
    }
    DSD_MEMCPY(g_last_soft, ambe_fr, sizeof(g_last_soft));
    for (int i = 0; i < 160; i++) {
        state->audio_out_temp_buf[i] = (float)(g_soft_calls * 2000 + i);
    }
}

void
playSynthesizedVoiceMS(dsd_opts* opts, dsd_state* state) {
    (void)opts;
    (void)state;
    g_play_ms_calls++;
}

void
playSynthesizedVoiceFM(dsd_opts* opts, dsd_state* state) {
    (void)opts;
    (void)state;
    g_play_fm_calls++;
}

static int
test_hard_voice_modes(void) {
    int err = 0;
    uint8_t dbuf[182];
    uint8_t reliab[182];

    reset_decoder_objects();
    fill_dibits(dbuf, reliab);

    reset_spies();
    nxdn_voice(&g_opts, &g_state, 1, dbuf, NULL);
    err |= expect_int("voice 1 hard frames", g_hard_calls, 2);
    err |= expect_int("voice 1 short playback", g_play_ms_calls, 2);
    err |= expect_int("voice 1 float playback", g_play_fm_calls, 0);
    err |= expect_int("voice 1 final high bit", g_last_hard[0][23], (dbuf[74] >> 1) & 1);
    err |= expect_int("voice 1 final low bit", g_last_hard[0][5], dbuf[74] & 1);
    err |= expect_float("voice 1 copies final audio", g_state.f_l[7], 2007.0f);

    reset_spies();
    reset_decoder_objects();
    nxdn_voice(&g_opts, &g_state, 2, dbuf, NULL);
    err |= expect_int("voice 2 hard frames", g_hard_calls, 2);
    err |= expect_int("voice 2 starts at second half high bit", g_last_hard[0][23], (dbuf[146] >> 1) & 1);
    err |= expect_int("voice 2 starts at second half low bit", g_last_hard[0][5], dbuf[146] & 1);

    reset_spies();
    reset_decoder_objects();
    g_opts.floating_point = 1;
    nxdn_voice(&g_opts, &g_state, 3, dbuf, NULL);
    err |= expect_int("voice 3 hard frames", g_hard_calls, 4);
    err |= expect_int("voice 3 short playback", g_play_ms_calls, 0);
    err |= expect_int("voice 3 float playback", g_play_fm_calls, 4);
    err |= expect_float("voice 3 copies final audio", g_state.f_l[159], 4159.0f);

    reset_spies();
    nxdn_voice(&g_opts, &g_state, 0, dbuf, NULL);
    err |= expect_int("voice 0 does not decode", g_hard_calls, 0);
    err |= expect_int("voice 0 does not play", g_play_fm_calls, 0);

    return err;
}

static int
test_soft_reliability_mapping(void) {
    int err = 0;
    uint8_t dbuf[182];
    uint8_t reliab[182];

    reset_decoder_objects();
    fill_dibits(dbuf, reliab);

    reset_spies();
    nxdn_voice(&g_opts, &g_state, 1, dbuf, reliab);

    err |= expect_int("soft voice calls", g_soft_calls, 2);
    err |= expect_int("soft path bypasses hard decoder", g_hard_calls, 0);
    err |= expect_int("soft high bit", g_last_soft[0][23].bit, (dbuf[74] >> 1) & 1);
    err |= expect_int("soft high reliability", g_last_soft[0][23].reliability, reliab[74]);
    err |= expect_int("soft low bit", g_last_soft[0][5].bit, dbuf[74] & 1);
    err |= expect_int("soft low reliability", g_last_soft[0][5].reliability, reliab[74]);
    err |= expect_float("soft copies final audio", g_state.f_l[3], 4003.0f);

    return err;
}

static int
test_all_masks_and_original_slot_positions(void) {
    int err = 0;
    uint8_t data[182], reliability[182];
    for (int voice = 0; voice <= 3; voice++) {
        for (unsigned mask = 0; mask < 16U; mask++) {
            for (int soft = 0; soft <= 1; soft++) {
                for (int floating = 0; floating <= 1; floating++) {
                    reset_decoder_objects();
                    reset_spies();
                    fill_dibits(data, reliability);
                    g_opts.floating_point = floating;
                    g_state.nxdn_search_voice_index = 93;
                    g_state.nxdn_search.applied = 1;
                    for (int i = 0; i < 160; i++) {
                        g_state.f_l[i] = -27.0f;
                        g_state.audio_out_temp_buf[i] = -13.0f;
                    }
                    nxdn_voice_masked(&g_opts, &g_state, voice, data, soft ? reliability : NULL, (uint8_t)mask);
                    const unsigned selected = voice == 1 ? 3U : voice == 2 ? 12U : voice == 3 ? 15U : 0U;
                    int count = 0;
                    for (int slot = 0; slot < 4; slot++) {
                        if ((selected & mask & (1U << (unsigned)slot)) == 0U) {
                            continue;
                        }
                        err |= expect_int("masked absolute slot", g_seen_slots[count], slot);
                        char bits[4][24] = {{0}};
                        uint8_t rel[4][24] = {{0}};
                        /* Independent arithmetic permutation, not the production table. */
                        for (int p = 0; p < 72; p++) {
                            const int k = 18 * (p % 4) + p / 4;
                            const int row = k < 24 ? 0 : k < 47 ? 1 : k < 58 ? 2 : 3;
                            const int col = k < 24 ? 23 - k : k < 47 ? 46 - k : k < 58 ? 57 - k : 71 - k;
                            const int index = 38 + 36 * slot + p / 2;
                            bits[row][col] = (char)((data[index] >> (p % 2 == 0 ? 1U : 0U)) & 1U);
                            rel[row][col] = reliability[index];
                        }
                        for (int row = 0; row < 4; row++) {
                            for (int col = 0; col < 24; col++) {
                                err |= expect_int("masked exact matrix", g_seen_bits[count][row][col], bits[row][col]);
                                if (soft) {
                                    err |= expect_int("masked exact reliability", g_seen_reliability[count][row][col], rel[row][col]);
                                }
                            }
                        }
                        count++;
                    }
                    err |= expect_int("masked hard count", g_hard_calls, soft ? 0 : count);
                    err |= expect_int("masked soft count", g_soft_calls, soft ? count : 0);
                    err |= expect_int("masked short audio count", g_play_ms_calls, floating ? 0 : count);
                    err |= expect_int("masked float audio count", g_play_fm_calls, floating ? count : 0);
                    for (int i = 0; i < 160; i++) {
                        const float expected = count ? (float)(count * (soft ? 2000 : 1000) + i) : -27.0f;
                        err |= expect_float("masked no stale audio copy", g_state.f_l[i], expected);
                        if (count == 0) {
                            err |= expect_float("empty mask preserves vocoder output", g_state.audio_out_temp_buf[i], -13.0f);
                        }
                    }
                    if (count == 0) {
                        err |= expect_int("empty mask preserves slot state", g_state.nxdn_search_voice_index, 93);
                        err |= expect_int("empty mask preserves search state", g_state.nxdn_search.applied, 1);
                    } else {
                        err |= expect_int("present slot clears search applied", g_state.nxdn_search.applied, 0);
                    }
                }
            }
        }
    }
    return err;
}

int
main(void) {
    int err = 0;

    err |= test_hard_voice_modes();
    err |= test_soft_reliability_mapping();
    err |= test_all_masks_and_original_slot_positions();

    if (err == 0) {
        DSD_FPRINTF(stdout, "NXDN_VOICE_AVAILABLE: OK (legacy assertions and 256 mask/selector/path/audio cases)\n");
    }
    return err;
}
