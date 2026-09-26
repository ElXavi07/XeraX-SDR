// SPDX-License-Identifier: GPL-3.0-or-later
/* Registered absolute-entry recovery study. Original observation functions,
 * encoded vectors, waveform and instrumented/uninstrumented inner runs remain
 * unchanged. The outer executable selects the public session policy. */
#include <dsd-neo/core/opts.h>
#include <dsd-neo/dsp/frame_sync.h>
#ifndef XERAX_ENTRY_OPTION
#define XERAX_ENTRY_OPTION 0
#endif
static int entry_sync(dsd_opts* opts, dsd_state* state) {
    opts->nxdn_fast_acquisition = XERAX_ENTRY_OPTION;
    return getFrameSync(opts, state);
}
#define getFrameSync entry_sync
#define main frozen_frame_observer_main
int frozen_frame_observer_main(int argc, char** argv);
#include "../nxdn_frames/observer.c"
#undef main
#undef getFrameSync
static const int k_entry_offsets[20] = {
    0, 7, 19, 640, 641, 719, 839, 840, 999, 1240, 1599, 1600, 2440, 2559,
    2560, 3199, 3200, 4000, 4479, 4480
};

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
            for (size_t entry = 0; entry < (scenario == 0 ? 20U : 1U); entry++) {
                const int off = scenario == 0 ? k_entry_offsets[entry] : 0;
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
