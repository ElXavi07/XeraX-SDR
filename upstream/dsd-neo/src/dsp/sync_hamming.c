// SPDX-License-Identifier: GPL-3.0-or-later
/*
 * Copyright (C) 2026 by arancormonk <180709949+arancormonk@users.noreply.github.com>
 */

/*
 * Frame-sync Hamming distance helpers.
 *
 * False-alarm probability derivation
 * ----------------------------------
 * Let N be the sync-pattern length in dibits. Under the null hypothesis of
 * uniformly random 4-ary symbols, each received dibit matches the expected
 * pattern position independently with probability 1/4, so the Hamming
 * distance H is Binomial(N, 3/4):
 *
 *   P(H = k) = C(N,k) * (3/4)^k * (1/4)^(N-k)
 *
 * For a single-pattern threshold test "declare sync if H <= t" the per-trial
 * false-alarm probability is the CDF
 *
 *   Pfa_single(N, t) = sum_{k=0..t} P(H = k).
 *
 * Tabulated values (N = 24, the P25/DMR sync length):
 *
 *   t = 0: Pfa ≈ 3.55e-15
 *   t = 2: Pfa ≈ 9.08e-12
 *   t = 4: Pfa ≈ 3.26e-9
 *   t = 6: Pfa ≈ 3.9e-7
 *   t = 8: Pfa ≈ 2.02e-5
 *
 * The `_with_remaps` helper evaluates ten candidate transforms (identity,
 * invert, bit-swap, xor-0x3, 90° rotation — each against the normal and
 * inverted reference pattern) and returns the minimum. Under the Bonferroni
 * union bound this multiplies the effective per-trial false-alarm rate by at
 * most the number of candidates (<= 10), so any application threshold should
 * use the adjusted bound
 *
 *   Pfa_effective ≤ 10 * Pfa_single(N, t).
 *
 * The remap transforms are not independent (e.g. rotation and inversion share
 * orbit structure on Z/4Z), so the actual factor is smaller; 10 is a safe
 * upper bound.
 *
 * The null alphabet must match the caller
 * --------------------------------------
 * Ordinary FSK synchronization sign-slices observations into '1'/'3'.
 * For an equally likely, independent binary null and a pattern using those
 * values, H is Binomial(N, 1/2), not Binomial(N, 3/4). For N=24, t=4 the
 * single-pattern probability is 0.000771939754486 per window. At 4800
 * symbols/s that is about 3.705 raw candidates/s before confirmation.
 * The four-ary example above applies only to a genuinely four-level null.
 * Remap candidates can have different probabilities under a restricted
 * alphabet; use the sum of their appropriate probabilities as a union bound.
 *
 * Sliding windows are dependent, but linearity of expectation still gives
 * Rs * Pfa expected raw candidates/s for the stated stationary null. It
 * does not give an independent-arrival waiting-time distribution. Filtered
 * RF noise may also violate independent/equiprobable symbol assumptions.
 * Neither model is a false valid-frame or false-call rate: confirmation,
 * CRC/FEC, framing, and protocol checks must be measured end to end.
 * Keep thresholds unchanged until both acquisition and negative controls
 * have been measured using the actual slicer and sample path.
 */

#include <dsd-neo/dsp/sync_hamming.h>

enum {
    DSD_SYNC_REMAP_COUNT = 5,
    DSD_SYNC_REFERENCE_COUNT = 2,
};

static int
dsd_sync_decode_dibit(char dibit_char) {
    int d = (unsigned char)dibit_char;
    if (d >= '0' && d <= '3') {
        d -= '0';
    }
    return d;
}

static int
dsd_sync_invert_dibit(int d) {
    switch (d) {
        case 0: return 2;
        case 1: return 3;
        case 2: return 0;
        default: return 1;
    }
}

static int
dsd_sync_rotate_dibit(int d) {
    /* 90° rotation (cyclic remap 0->1->3->2->0). */
    switch (d & 0x3) {
        case 0: return 1;
        case 1: return 3;
        case 2: return 0;
        default: return 2; /* d==3 */
    }
}

static void
dsd_sync_fill_remaps(int d, int remaps[DSD_SYNC_REMAP_COUNT]) {
    remaps[0] = d;
    remaps[1] = dsd_sync_invert_dibit(d);
    remaps[2] = ((d & 1) << 1) | ((d & 2) >> 1); /* swap bit order */
    remaps[3] = d ^ 0x3;                         /* bitwise not in 2-bit space */
    remaps[4] = dsd_sync_rotate_dibit(d);
}

static int
dsd_sync_min_hamming(int hamming[DSD_SYNC_REMAP_COUNT][DSD_SYNC_REFERENCE_COUNT]) {
    int best = hamming[0][0];
    for (int remap = 0; remap < DSD_SYNC_REMAP_COUNT; remap++) {
        for (int ref = 0; ref < DSD_SYNC_REFERENCE_COUNT; ref++) {
            if (hamming[remap][ref] < best) {
                best = hamming[remap][ref];
            }
        }
    }
    return best;
}

int
dsd_sync_hamming_distance(const char* buf, const char* pat, int len) {
    int ham = 0;
    for (int i = 0; i < len; i++) {
        int d = dsd_sync_decode_dibit(buf[i]);
        int expect = (unsigned char)pat[i] - '0';
        if (d != expect) {
            ham++;
        }
    }
    return ham;
}

int
dsd_qpsk_sync_hamming_with_remaps(const char* buf, const char* pat_norm, const char* pat_inv, int len) {
    int hamming[DSD_SYNC_REMAP_COUNT][DSD_SYNC_REFERENCE_COUNT] = {{0}};
    for (int k = 0; k < len; k++) {
        int remaps[DSD_SYNC_REMAP_COUNT];
        const int expected[DSD_SYNC_REFERENCE_COUNT] = {pat_norm[k] - '0', pat_inv[k] - '0'};
        int d = dsd_sync_decode_dibit(buf[k]);

        dsd_sync_fill_remaps(d, remaps);
        for (int remap = 0; remap < DSD_SYNC_REMAP_COUNT; remap++) {
            hamming[remap][0] += (remaps[remap] != expected[0]);
            hamming[remap][1] += (remaps[remap] != expected[1]);
        }
    }
    return dsd_sync_min_hamming(hamming);
}
