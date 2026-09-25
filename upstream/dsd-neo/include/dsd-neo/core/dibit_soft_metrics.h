// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef DSD_NEO_CORE_DIBIT_SOFT_METRICS_H
#define DSD_NEO_CORE_DIBIT_SOFT_METRICS_H

#include <float.h>
#include <math.h>

/* Compute both bit metrics from one set of distances. Keep the original
 * comparison order and float arithmetic: this is a work-sharing optimization,
 * not a change to confidence calibration or hard decisions. */
static inline void
dsd_dibit_soft_magnitudes(float symbol, const float ideal[4], int magnitude[2]) {
    float distance[4];
    float min_spacing = FLT_MAX;
    for (int i = 0; i < 4; ++i) {
        const float delta = symbol - ideal[i];
        distance[i] = delta * delta;
        for (int j = i + 1; j < 4; ++j) {
            const float spacing = fabsf(ideal[i] - ideal[j]);
            if (spacing > 1e-6f && spacing < min_spacing) {
                min_spacing = spacing;
            }
        }
    }
    if (min_spacing == FLT_MAX) {
        min_spacing = 2.0f;
    }
    const float scale = 255.0f / (min_spacing * min_spacing);
    float best0[2] = {FLT_MAX, FLT_MAX};
    float best1[2] = {FLT_MAX, FLT_MAX};
    for (int i = 0; i < 4; ++i) {
        float* msb = (i & 2) ? &best1[0] : &best0[0];
        float* lsb = (i & 1) ? &best1[1] : &best0[1];
        if (distance[i] < *msb) *msb = distance[i];
        if (distance[i] < *lsb) *lsb = distance[i];
    }
    for (int bit = 0; bit < 2; ++bit) {
        const int value = (int)lrintf(fabsf(best0[bit] - best1[bit]) * scale);
        magnitude[bit] = value < 0 ? 0 : value > 255 ? 255 : value;
    }
}

#endif
