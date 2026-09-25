// SPDX-License-Identifier: GPL-3.0-or-later
#include <dsd-neo/core/dibit_soft_metrics.h>
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>

// Frozen pre-4.3.1 reference; separate from the production shared-work path.
static int reference_bit(float symbol, const float ideal[4], int bit) {
    float best0 = FLT_MAX, best1 = FLT_MAX, spacing = FLT_MAX;
    for (int i = 0; i < 4; ++i) {
        float delta = symbol - ideal[i], distance = delta * delta;
        if ((i >> (1 - bit)) & 1) {
            if (distance < best1) best1 = distance;
        } else if (distance < best0) best0 = distance;
        for (int j = i + 1; j < 4; ++j) {
            float d = fabsf(ideal[i] - ideal[j]);
            if (d > 1e-6f && d < spacing) spacing = d;
        }
    }
    if (spacing == FLT_MAX) spacing = 2;
    float scale = 255.0f / (spacing * spacing);
    int value = (int)lrintf(fabsf(best0 - best1) * scale);
    return value < 0 ? 0 : value > 255 ? 255 : value;
}
#if defined(__GNUC__)
#define NOINLINE __attribute__((noinline))
#else
#define NOINLINE __declspec(noinline)
#endif
static NOINLINE void baseline(float x, const float ideal[4], int out[2]) {
    out[0] = reference_bit(x, ideal, 0); out[1] = reference_bit(x, ideal, 1);
}
static NOINLINE void candidate(float x, const float ideal[4], int out[2]) {
    dsd_dibit_soft_magnitudes(x, ideal, out);
}
struct Sample { float x; std::array<float, 4> ideal; };
static uint32_t seed = 431;
static uint32_t next() { seed ^= seed << 13; seed ^= seed >> 17; seed ^= seed << 5; return seed; }
int main(int argc, char** argv) {
    std::vector<Sample> samples;
    for (float scale : {0.001f, 1.0f, 8000.0f}) {
        for (float dc : {-0.7f, 0.0f, 0.4f}) {
            std::array<float, 4> levels{-3.1f, -0.9f, 1.2f, 2.9f};
            do {
                auto ideal = levels;
                for (float& v : ideal) v = (v + dc) * scale;
                for (int i = -2048; i <= 2048; ++i) samples.push_back({i * scale / 256.0f, ideal});
            } while (std::next_permutation(levels.begin(), levels.end()));
        }
    }
    for (int i = 0; i < 50000; ++i) {
        const float gain = 0.1f + (next() % 10000) / 100.0f;
        Sample s{(int(next() % 4096) - 2048) * gain / 256.0f, {}};
        s.ideal = {gain, gain * 3, -gain, -gain * 3}; samples.push_back(s);
    }
    for (float value : {0.0f, 1e-8f, -1e-8f, 1.0f, 8000.0f})
        samples.push_back({value, {value, value, value, value}});
    for (const auto& s : samples) {
        int a[2], b[2]; baseline(s.x, s.ideal.data(), a); candidate(s.x, s.ideal.data(), b);
        if (a[0] != b[0] || a[1] != b[1]) {
            std::fprintf(stderr, "Mismatch at %.9g: %d/%d != %d/%d\n", s.x, a[0], a[1], b[0], b[1]); return 1;
        }
    }
    const float ideal[4] = {1, 3, -1, -3}; int out[2];
    candidate(0, ideal, out); if (out[0] != 0 || out[1] != 255) return 2;
    candidate(1, ideal, out); if (out[0] != 255 || out[1] != 255) return 3;
    std::printf("Exact metric parity on %zu finite samples and independent boundary checks\n", samples.size());
    if (argc < 2 || std::strcmp(argv[1], "--benchmark")) return 0;
    using Kernel = void (*)(float, const float*, int*);
    auto measure = [&](Kernel kernel) {
        const auto start = std::chrono::steady_clock::now(); uint64_t sum = 0;
        for (int repeat = 0; repeat < 4; ++repeat) for (const auto& s : samples) {
            int v[2]; kernel(s.x, s.ideal.data(), v); sum += v[0] + v[1];
        }
        const double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
        return std::pair<double, uint64_t>(seconds, sum);
    };
    measure(baseline); measure(candidate); std::vector<double> ratios;
    for (int i = 0; i < 7; ++i) {
        auto a = measure(i % 2 ? candidate : baseline); auto b = measure(i % 2 ? baseline : candidate);
        if (a.second != b.second) return 4;
        if (i % 2) std::swap(a, b);
        ratios.push_back(a.first / b.first);
        std::printf("{\"repeat\":%d,\"baseline_seconds\":%.9f,\"candidate_seconds\":%.9f,\"pairs\":%zu,\"checksum\":%llu}\n",
            i, a.first, b.first, samples.size() * 4, (unsigned long long)a.second);
    }
    std::sort(ratios.begin(), ratios.end());
    std::printf("Median paired kernel speed ratio: %.4f\n", ratios[ratios.size() / 2]);
}
