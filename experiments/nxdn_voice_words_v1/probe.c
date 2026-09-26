/* SPDX-License-Identifier: GPL-3.0-or-later
 * A channel-word probe, with no synthesis, receiver, radio or privacy path. */
#include <dsd-neo/core/ambe_interleave.h>
#include <mbelib-neo/mbelib.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

enum { WORDS = 8266, BASE_WORDS = 73, BYTES_PER_WORD = 9 };
static unsigned char corpus[WORDS][BYTES_PER_WORD];
static unsigned sequence;

static int
read_input(const char* path) {
    FILE* file = fopen(path, "rb");
    if (!file) { return 1; }
    const size_t got = fread(corpus, 1, sizeof(corpus), file);
    const int extra = fgetc(file);
    const int bad = got != sizeof(corpus) || extra != EOF || ferror(file);
    return fclose(file) != 0 || bad;
}

static unsigned
bit(const unsigned char* bytes, unsigned index) {
    return (bytes[index / 8U] >> (7U - index % 8U)) & 1U;
}

static void
decode(unsigned word, int mutation, int soft) {
    unsigned char input[9];
    memcpy(input, corpus[word], sizeof(input));
    if (mutation >= 0) { input[(unsigned)mutation / 8U] ^= (unsigned char)(128U >> ((unsigned)mutation % 8U)); }
    char hard_frame[4][24] = {{0}};
    mbe_soft_bit soft_frame[4][24] = {{{0}}};
    for (unsigned i = 0; i < DSD_AMBE_2450_DIBITS; ++i) {
        const dsd_ambe_2450_dibit_map_entry* m = &dsd_ambe_2450_dibit_map[i];
        hard_frame[m->high_row][m->high_col] = (char)bit(input, i * 2U);
        hard_frame[m->low_row][m->low_col] = (char)bit(input, i * 2U + 1U);
        soft_frame[m->high_row][m->high_col].bit = (uint8_t)bit(input, i * 2U);
        soft_frame[m->high_row][m->high_col].reliability = 255;
        soft_frame[m->low_row][m->low_col].bit = (uint8_t)bit(input, i * 2U + 1U);
        soft_frame[m->low_row][m->low_col].reliability = 255;
    }
    char before_hard[4][24];
    mbe_soft_bit before_soft[4][24];
    memcpy(before_hard, hard_frame, sizeof(hard_frame));
    memcpy(before_soft, soft_frame, sizeof(soft_frame));
    char decoded[49];
    memset(decoded, -1, sizeof(decoded));
    mbe_process_result result = {0};
    const int status = soft
        ? mbe_decodeAmbe3600x2450SoftFrame((const mbe_soft_bit (*)[24])soft_frame, decoded, &result)
        : mbe_decodeAmbe3600x2450Frame((const char (*)[24])hard_frame, decoded, &result);
    const int unchanged = !memcmp(before_hard, hard_frame, sizeof(hard_frame))
        && !memcmp(before_soft, soft_frame, sizeof(soft_frame));
    printf("{\"seq\":%u,\"word\":%u,\"mutation\":%d,\"mode\":\"%s\",\"input\":\"",
           sequence++, word, mutation, soft ? "soft" : "hard");
    for (unsigned i = 0; i < 9; ++i) { printf("%02x", (unsigned)input[i]); }
    printf("\",\"status\":%d,\"bits\":[", status);
    for (unsigned i = 0; i < 49; ++i) { printf("%s%d", i ? "," : "", (int)decoded[i]); }
    printf("],\"input_unchanged\":%d,\"c0_errors\":%d,\"protected_errors\":%d,\"c4_errors\":%d,"
           "\"total_errors\":%d,\"flags\":%u}\n", unchanged, result.c0_errors, result.protected_errors,
           result.c4_errors, result.total_errors, result.flags);
}

int
main(int argc, char** argv) {
    if (argc != 2) { return 2; }
    if (read_input(argv[1])) { return 3; }
    for (unsigned word = 0; word < WORDS; ++word) {
        decode(word, -1, 0); decode(word, -1, 1);
    }
    for (unsigned word = 0; word < BASE_WORDS; ++word) {
        for (int mutation = 0; mutation < 72; ++mutation) {
            decode(word, mutation, 0); decode(word, mutation, 1);
        }
    }
    return sequence == 27044U && fflush(stdout) == 0 && !ferror(stdout) ? 0 : 4;
}
