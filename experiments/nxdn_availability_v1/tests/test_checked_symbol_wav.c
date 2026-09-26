// SPDX-License-Identifier: GPL-3.0-or-later
#ifdef NDEBUG
#undef NDEBUG
#endif
#define main legacy_wav_eof_regressions
#include "../../../upstream/dsd-neo/tests/dsp/test_dsp_wav_input_eof.c"
#undef main
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #x); exit(1); } } while (0)
static void test_wav_spans(int sps, size_t length) {
    char path[DSD_TEST_PATH_MAX];
    int fd = dsd_test_mkstemp(path, sizeof(path), "checked_wav"); CHECK(fd >= 0); dsd_close(fd);
    SF_INFO info = {0}; info.samplerate = 48000; info.channels = 1; info.format = SF_FORMAT_WAV | SF_FORMAT_PCM_16;
    SNDFILE* f = sf_open(path, SFM_WRITE, &info); CHECK(f != NULL);
    short samples[40] = {0};
    CHECK(sf_write_short(f, samples, (sf_count_t)length) == (sf_count_t)length);
    CHECK(sf_close(f) == 0);
    static dsd_opts opts; static dsd_state state;
    DSD_MEMSET(&opts, 0, sizeof(opts)); DSD_MEMSET(&state, 0, sizeof(state));
    opts.audio_in_file_info = &info; opts.audio_in_file = sf_open(path, SFM_READ, &info);
    CHECK(opts.audio_in_file != NULL);
    opts.audio_in_type = AUDIO_IN_WAV; opts.audio_out_type = 1;
    opts.input_volume_multiplier = 1; opts.wav_sample_rate = 48000;
    state.samplesPerSymbol = sps; state.symbolCenter = dsd_opts_symbol_center(sps); state.jitter = -1;
    exitflag = 0; g_cleanup_calls = 0;
    size_t completed = length / (size_t)sps;
    for (size_t i = 0; i < completed; ++i) {
        float out = 99;
        CHECK(dsd_get_symbol_checked(&opts, &state, 1, &out) == 1 && out == 0);
        CHECK(state.symbolcnt == i + 1 && g_cleanup_calls == 0);
    }
    float out = 99;
    CHECK(dsd_get_symbol_checked(&opts, &state, 1, &out) == 0 && out == 0);
    CHECK(state.symbolcnt == completed && g_cleanup_calls == 1 && exitflag == 1);
    CHECK(opts.audio_in_file == NULL);
    CHECK(dsd_get_symbol_checked(&opts, &state, 1, &out) == 0 && state.symbolcnt == completed);
    CHECK(g_cleanup_calls == 1);
    CHECK(remove(path) == 0);
}
int main(void) {
    CHECK(legacy_wav_eof_regressions() == 0);
    for (int sps = 10; sps <= 20; sps += 10) {
        test_wav_spans(sps, 0); test_wav_spans(sps, (size_t)sps - 1);
        test_wav_spans(sps, (size_t)sps); test_wav_spans(sps, (size_t)sps + 1);
        test_wav_spans(sps, (size_t)sps * 2 - 1);
    }
    puts("checked WAV symbols: original EOF regression + finite SPS10/20 cases passed");
    return 0;
}
