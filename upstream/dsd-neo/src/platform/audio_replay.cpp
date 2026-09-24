// SPDX-License-Identifier: GPL-3.0-or-later
#include <dsd-neo/platform/audio_replay.h>
#include <algorithm>
#include <array>
#include <mutex>
#include <atomic>

namespace {
constexpr size_t capacity = 48000 * 60;
std::array<int16_t, capacity> ring{};
std::mutex guard;
size_t head = 0, count = 0;
std::atomic<bool> suppressed{false};
std::atomic<bool> rangeSuppressed{false};
std::atomic<uint64_t> received{0}, gaps{0};
std::atomic<uint64_t> nonzero{0}, output{0};
}
extern "C" void dsd_audio_replay_capture(const int16_t* pcm, size_t frames, int rate, int channels) {
    if (!pcm || !frames || frames > 480000 || rate < 8000 || rate > 192000 || channels < 1 || channels > 2) return;
    std::lock_guard<std::mutex> lock(guard);
    // The accepted 480k-frame maximum exceeds 32-bit size_t during multiplication.
    const size_t n = static_cast<size_t>(static_cast<uint64_t>(frames) * 48000 / static_cast<unsigned>(rate));
    auto mono = [&](size_t i) -> double {
        return channels == 1 ? pcm[i] : (static_cast<int>(pcm[i * 2]) + pcm[i * 2 + 1]) * 0.5;
    };
    for (size_t i = 0; i < n; ++i) {
        const double pos = static_cast<double>(i) * rate / 48000.0;
        const size_t left = static_cast<size_t>(pos);
        const size_t right = std::min(left + 1, frames - 1);
        const double alpha = pos - static_cast<double>(left);
        ring[head] = static_cast<int16_t>(mono(left) * (1.0 - alpha) + mono(right) * alpha);
        head = (head + 1) % capacity;
    }
    count = std::min(capacity, count + n);
    received.fetch_add(n, std::memory_order_relaxed);
    if (std::any_of(pcm, pcm + frames * static_cast<size_t>(channels), [](int16_t v) { return v != 0; }))
        nonzero.fetch_add(n, std::memory_order_relaxed);
}
extern "C" void dsd_audio_live_suppress(int enabled) { suppressed.store(enabled != 0); }
extern "C" void dsd_audio_range_suppress(int enabled) { rangeSuppressed.store(enabled != 0); }
extern "C" int dsd_audio_live_suppressed(void) { return suppressed.load() || rangeSuppressed.load(); }
extern "C" uint64_t dsd_audio_received_frames(void) { return received.load(); }
extern "C" uint64_t dsd_audio_nonzero_frames(void) { return nonzero.load(); }
extern "C" void dsd_audio_note_output(size_t frames, int rate) {
    if (rate > 0) output.fetch_add(static_cast<uint64_t>(frames) * 48000 / static_cast<unsigned>(rate));
}
extern "C" uint64_t dsd_audio_output_frames(void) { return output.load(); }
extern "C" void dsd_audio_note_gap(void) { if (!dsd_audio_live_suppressed()) ++gaps; }
extern "C" uint64_t dsd_audio_gap_count(void) { return gaps.load(); }
extern "C" size_t dsd_audio_replay_snapshot(int16_t* pcm, size_t max, int seconds) {
    if (!pcm || seconds <= 0 || seconds > 60) return 0;
    std::lock_guard<std::mutex> lock(guard);
    size_t n = std::min({count, max, static_cast<size_t>(seconds) * 48000});
    size_t start = (head + capacity - n) % capacity;
    for (size_t i = 0; i < n; ++i) pcm[i] = ring[(start + i) % capacity];
    return n;
}
extern "C" void dsd_audio_replay_clear(void) {
    std::lock_guard<std::mutex> lock(guard);
    ring.fill(0);
    count = head = 0;
}
extern "C" double dsd_audio_replay_seconds(void) {
    std::lock_guard<std::mutex> lock(guard);
    return static_cast<double>(count) / 48000;
}
