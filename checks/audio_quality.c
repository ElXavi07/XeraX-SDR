// SPDX-License-Identifier: GPL-3.0-or-later
#include <dsd-neo/core/audio.h>
#include <dsd-neo/core/opts.h>
#include <dsd-neo/core/state.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "Audio quality failure at %d: %s\n", __LINE__, #x); return 1; } } while (0)
static dsd_opts opts;
static dsd_state state;
int main(void) {
    // Speech can start after a quiet first sub-block. Gain must follow the
    // current samples in either slot, independently of the other slot.
    opts.audio_gain = 25;
    for (int slot = 0; slot < 2; ++slot) {
        memset(&state, 0, sizeof state);
        state.aout_gain = state.aout_gainR = 20;
        float speech[160] = {0};
        for (int i = 20; i < 160; ++i) speech[i] = (i & 1) ? 12000 : -12000;
        agf(&opts, &state, speech, slot);
        CHECK(fabsf((slot ? state.aout_gainR : state.aout_gain) - 17.0f) < 0.001f);
        CHECK((slot ? state.aout_gain : state.aout_gainR) == 20);
        for (int i = 0; i < 160; ++i) CHECK(isfinite(speech[i]) && fabsf(speech[i]) <= 1);
    }
    // A manual analog boost must saturate, never wrap a loud sample's polarity.
    opts.audio_gainA = 100;
    short loud[] = {30000, -30000, 32767, -32768, 1000, -1000, 0};
    analog_gain(&opts, &state, loud, 7);
    const short expected[] = {32767, -32768, 32767, -32768, 5000, -5000, 0};
    CHECK(memcmp(loud, expected, sizeof loud) == 0);
    puts("Voice gain follows both slots; analog peaks saturate without wraparound");
    return 0;
}
