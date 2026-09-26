// SPDX-License-Identifier: GPL-3.0-or-later
/* Private availability tests. Retain the original replay regressions with
 * assertions active even in release builds; no receiver or waveform replay. */
#ifdef NDEBUG
#undef NDEBUG
#endif
#define main legacy_replay_regressions
#define openAudioInput original_openAudioInput_stub
#include "../../../upstream/dsd-neo/tests/dsp/test_dsp_symbol_replay.c"
#undef openAudioInput
#undef main

static int g_open_result = -1;
int openAudioInput(dsd_opts* opts) { (void)opts; return g_open_result; }
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #x); exit(1); } } while (0)

static void fixture(dsd_opts* opts, dsd_state* state, int kind) {
    init_symbol_replay_fixture(opts, state);
    opts->audio_in_type = kind;
    opts->audio_out_type = 1;
    exitflag = 0;
    g_cleanup_calls = 0;
    g_open_result = -1;
}

static FILE* bytes_file(const void* data, size_t n) {
    FILE* f = tmpfile();
    CHECK(f != NULL);
    if (n) CHECK(fwrite(data, 1, n, f) == n);
    rewind(f);
    return f;
}

static void test_checked_records(void) {
    static dsd_opts opts;
    static dsd_state state;
    unsigned char header[16] = {'D','S','D','N','S','Y','M','2',2,10,0,0,0,0,0,0};
    unsigned char zero[10] = {0};
    float out;
    /* A legacy zero byte is a real record, not an unavailable placeholder. */
    fixture(&opts, &state, AUDIO_IN_SYMBOL_BIN);
    opts.symbolfile = bytes_file(zero, 1);
    state.symbolcnt = UINT32_MAX;
    out = 99;
    CHECK(dsd_get_symbol_checked(&opts, &state, 1, &out) == 1);
    CHECK(symbol_level_matches(out, 0));
    CHECK(state.symbolcnt == 0 && state.symbolc == 0);
    out = 99;
    CHECK(dsd_get_symbol_checked(&opts, &state, 1, &out) == 0);
    CHECK(out == 0 && state.symbolcnt == 1 && opts.symbolfile == NULL);
    CHECK(g_cleanup_calls == 1 && exitflag == 1);
    CHECK(dsd_get_symbol_checked(&opts, &state, 1, &out) == 0);
    CHECK(state.symbolcnt == 1 && g_cleanup_calls == 1);

    for (size_t n = 0; n <= 10; ++n) {
        fixture(&opts, &state, AUDIO_IN_SYMBOL_BIN);
        opts.symbolfile = tmpfile(); CHECK(opts.symbolfile != NULL);
        CHECK(fwrite(header, 1, 16, opts.symbolfile) == 16);
        CHECK(fwrite(zero, 1, n, opts.symbolfile) == n);
        rewind(opts.symbolfile); out = 99;
        CHECK(dsd_get_symbol_checked(&opts, &state, 1, &out) == (n == 10));
        CHECK(out == 0 && state.symbolcnt == 1);
        CHECK(state.symbol_replay_soft_records == (n == 10));
        CHECK(g_cleanup_calls == (n != 10));
        if (n == 10) {
            CHECK(state.symbol_replay_has_soft == 1);
            CHECK(state.symbol_replay_soft.reliability == 0);
            CHECK(state.symbol_replay_soft.llr[0] == 0 && state.symbol_replay_soft.llr[1] == 0);
        }
        if (opts.symbolfile) fclose(opts.symbolfile);
    }
    /* Recognized but truncated/unsupported headers are not legacy bytes. */
    for (size_t n = 8; n < 16; ++n) {
        fixture(&opts, &state, AUDIO_IN_SYMBOL_BIN);
        opts.symbolfile = bytes_file(header, n); out = 99;
        CHECK(dsd_get_symbol_checked(&opts, &state, 1, &out) == 0);
        CHECK(out == 0 && state.symbolcnt == 1 && g_cleanup_calls == 1);
        CHECK(opts.symbolfile == NULL);
    }
    for (int field = 8; field <= 9; ++field) {
        fixture(&opts, &state, AUDIO_IN_SYMBOL_BIN);
        header[field]++;
        opts.symbolfile = bytes_file(header, 16); out = 99;
        CHECK(dsd_get_symbol_checked(&opts, &state, 1, &out) == 0);
        CHECK(out == 0 && state.symbolcnt == 1 && g_cleanup_calls == 1);
        header[field]--;
    }
    /* Complete float records, including zero, have explicit success; short
     * records keep the old EOF commit/count while returning unavailable. */
    for (size_t n = 0; n <= sizeof(float); ++n) {
        fixture(&opts, &state, AUDIO_IN_SYMBOL_FLT);
        opts.symbolfile = bytes_file(zero, n); out = 99;
        CHECK(dsd_get_symbol_checked(&opts, &state, 1, &out) == (n == sizeof(float)));
        CHECK(out == 0 && state.symbolcnt == 1);
        CHECK(exitflag == (n != sizeof(float)));
        fclose(opts.symbolfile);
    }
    fixture(&opts, &state, AUDIO_IN_SYMBOL_FLT);
    float nonzero = 0.25f;
    opts.symbolfile = bytes_file(&nonzero, sizeof(nonzero));
    CHECK(dsd_get_symbol_checked(&opts, &state, 1, &out) == 1 && out == 2500.0f);
    fclose(opts.symbolfile);
    fixture(&opts, &state, AUDIO_IN_SYMBOL_BIN);
    out = 99;
    CHECK(dsd_get_symbol_checked(&opts, &state, 1, &out) == 0 && out == 0);
    CHECK(state.symbolcnt == 1 && g_cleanup_calls == 0); /* legacy -1 commit */
    fixture(&opts, &state, AUDIO_IN_SYMBOL_FLT);
    CHECK(dsd_get_symbol_checked(&opts, &state, 1, &out) == 0 && out == 0);
    CHECK(state.symbolcnt == 0);
    out = 99;
    CHECK(dsd_get_symbol_checked(NULL, &state, 1, &out) == 0 && out == 0);
    CHECK(dsd_get_symbol_checked(&opts, NULL, 1, &out) == 0);
    CHECK(dsd_get_symbol_checked(&opts, &state, 1, NULL) == 0);
}

static void test_checked_looping(void) {
    static dsd_opts opts;
    static dsd_state state;
    for (int kind = 0; kind < 4; ++kind) {
        char path[DSD_TEST_PATH_MAX];
        int fd = dsd_test_mkstemp(path, sizeof(path), "checked_symbol_loop"); CHECK(fd >= 0);
        FILE* f = fdopen(fd, "wb"); CHECK(f != NULL);
        if (kind >= 2) write_soft_header(f);
        if (kind == 1) CHECK(fputc(0, f) != EOF);
        if (kind == 3) write_soft_record(f, 0, 0, 0, 0, 0.0f);
        CHECK(fclose(f) == 0);
        fixture(&opts, &state, AUDIO_IN_SYMBOL_BIN);
        state.debug_mode = 1;
        DSD_SNPRINTF(opts.audio_in_dev, sizeof(opts.audio_in_dev), "%s", path);
        opts.symbolfile = dsd_fopen_existing_regular_file(path, "rb"); CHECK(opts.symbolfile != NULL);
        for (int i = 0; i < 2; ++i) {
            float out = 99;
            CHECK(dsd_get_symbol_checked(&opts, &state, 1, &out) == (kind & 1));
            CHECK(state.symbolcnt == (uint32_t)(i + 1));
            CHECK(g_cleanup_calls == 0 && exitflag == 0);
            CHECK((kind & 1) || out == 0);
        }
        if (opts.symbolfile) fclose(opts.symbolfile);
        CHECK(remove(path) == 0);
    }
    /* Reopen failure is bounded and remains unavailable. */
    fixture(&opts, &state, AUDIO_IN_SYMBOL_BIN);
    state.debug_mode = 1;
    DSD_SNPRINTF(opts.audio_in_dev, sizeof(opts.audio_in_dev), "%s", "missing-checked-symbol-replay.bin");
    opts.symbolfile = bytes_file(NULL, 0);
    float out = 99;
    CHECK(dsd_get_symbol_checked(&opts, &state, 1, &out) == 0 && out == 0);
    CHECK(opts.symbolfile == NULL && state.symbolcnt == 1);
}

static void test_checked_frontend_transition(void) {
    static dsd_opts opts;
    static dsd_state state;
    fixture(&opts, &state, AUDIO_IN_SYMBOL_BIN);
    opts.audio_out_type = 0;
    opts.frontend_kind = DSD_FRONTEND_TERMINAL;
    opts.symbolfile = bytes_file(NULL, 0);
    g_open_result = 0;
    float out = 99;
    CHECK(dsd_get_symbol_checked(&opts, &state, 1, &out) == 0 && out == 0);
    CHECK(opts.audio_in_type == AUDIO_IN_PULSE && state.symbolcnt == 1);
    CHECK(g_cleanup_calls == 0 && exitflag == 0);
    g_open_result = -1;
}

int main(void) {
    CHECK(legacy_replay_regressions() == 0);
    test_checked_records();
    test_checked_looping();
    test_checked_frontend_transition();
    puts("checked symbol replay: original regressions + finite records/loop/transition passed");
    return 0;
}
