// SPDX-License-Identifier: GPL-3.0-or-later
// Private-source inclusion exercises the exact production payload transformations.
// This is a payload test: RF acquisition, FEC and audible vocoder output are separate.
#include "../upstream/dsd-neo/src/core/vocoder/dsd_mbe.c"
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "Voice privacy failure at %d\n", __LINE__); return 1; } } while (0)
static void bits(const uint8_t* bytes, char* out, int n) {
    for (int i = 0; i < n; ++i) out[i] = (char)((bytes[i / 8] >> (7 - i % 8)) & 1);
}
int main(void) {
    // Independent PyCryptodome 3.23.0 ARC4 fixtures, discard 256 octets;
    // key 0102030405 with P25 MI 1020304050607080 or DMR MI 10203040.
    const uint8_t plain[] = {0x11,0x22,0x33,0x44,0x55,0x66,0x77,0x88,0x99,0xaa,0xbb};
    const uint8_t p25_cipher[] = {0xc8,0xd6,0x79,0x9e,0x1f,0xa7,0x1b,0x65,0x77,0x54,0x06};
    const uint8_t dmr_cipher[] = {0xe5,0x48,0x13,0x40,0x83,0x83,0x31};
    static dsd_state state;
    mbe_frame_ctx_t frame = {0};
    char expected[88]; bits(plain, expected, 88);
    state.R = state.RR = 0x0102030405ULL;
    state.payload_miP = state.payload_miN = 0x1020304050607080ULL;
    state.dropL = 256;
    bits(p25_cipher, frame.imbe_d, 88);
    mbe_apply_p25p1_rc4(&state, frame.imbe_d);
    CHECK(memcmp(expected, frame.imbe_d, 88) == 0 && state.dropL == 267);
    state.synctype = DSD_SYNC_P25P2_POS;
    state.payload_algid = state.payload_algidR = 0xaa;
    state.dropL = state.dropR = 256;
    bits(p25_cipher, frame.ambe_d, 49);
    mbeslot_left_apply_p25p2_rc4(&state, &frame);
    CHECK(memcmp(expected, frame.ambe_d, 49) == 0 && state.dropL == 263 && state.dropR == 256);
    bits(p25_cipher, frame.ambe_d, 49);
    mbeslot_right_apply_p25p2_rc4(&state, &frame);
    CHECK(memcmp(expected, frame.ambe_d, 49) == 0 && state.dropR == 263);
    // DMR's 49th fixture plaintext bit is zero.
    expected[48] = 0;
    state.payload_algid = state.payload_algidR = 0x21;
    state.payload_mi = state.payload_miR = 0x10203040;
    state.dropL = state.dropR = 256;
    bits(dmr_cipher, frame.ambe_d, 49);
    mbeslot_left_apply_rc4(&state, &frame);
    CHECK(memcmp(expected, frame.ambe_d, 49) == 0 && state.dropL == 263 && state.dropR == 256);
    bits(dmr_cipher, frame.ambe_d, 49);
    mbeslot_right_apply_rc4(&state, &frame);
    CHECK(memcmp(expected, frame.ambe_d, 49) == 0 && state.dropR == 263);
    state.R = 0; state.scalar_key_present[0] = 0;
    bits(dmr_cipher, frame.ambe_d, 49); char unchanged[49]; memcpy(unchanged, frame.ambe_d, 49);
    mbeslot_left_apply_rc4(&state, &frame);
    CHECK(memcmp(unchanged, frame.ambe_d, 49) == 0 && state.dropL == 263);
    // Published pinned-upstream NXDN LFSR fixture, applied through the native
    // voice routine with configured scrambler 0x1234, producing alternating bits.
    const char nxdn_cipher[49] = {1,0,0,0,0,1,1,0,1,1,1,0,0,0,1,0,0,1,0,0,0,0,1,1,0,
                                 0,0,1,1,0,0,0,1,1,0,1,1,1,1,1,0,0,0,0,0,1,1,1,1};
    state.R = 0x1234; state.payload_miN = 0;
    memcpy(frame.ambe_d, nxdn_cipher, 49);
    mbe_apply_nxdn_cipher1(&state, frame.ambe_d);
    for (int i = 0; i < 49; ++i) CHECK(frame.ambe_d[i] == ((i * 3 + 1) & 1));
    CHECK(state.payload_miN == 0x3bde);
    state.R = 0; state.payload_miN = 0; memcpy(frame.ambe_d, nxdn_cipher, 49);
    mbe_apply_nxdn_cipher1(&state, frame.ambe_d);
    CHECK(memcmp(frame.ambe_d, nxdn_cipher, 49) == 0);
    puts("Native P25 Phase 1/2 ADP, both DMR slots and NXDN payload fixtures passed");
    return 0;
}
