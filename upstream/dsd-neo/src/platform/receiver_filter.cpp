// SPDX-License-Identifier: GPL-3.0-or-later
#include <dsd-neo/platform/receiver_filter.h>
#include <dsd-neo/platform/analog_tones.h>
#include <algorithm>
#include <cmath>
#include <mutex>
#include <vector>
namespace {
std::mutex mutex;
std::vector<dsd_receiver_filter> rules;
dsd_receiver_filter find(uint64_t frequency) {
    std::lock_guard<std::mutex> lock(mutex);
    for (const auto& rule : rules) if (rule.frequency == frequency) return rule;
    return {0, 0, -1, 0, -1, 0, 0};
}
}
extern "C" void dsd_receiver_filters_set(const dsd_receiver_filter* data, size_t count) {
    std::lock_guard<std::mutex> lock(mutex);
    rules.clear();
    if (data) rules.assign(data, data + std::min(count, size_t(500)));
}
extern "C" int dsd_receiver_analog_allowed(uint64_t frequency) {
    const auto rule = find(frequency);
    if (rule.ctcss <= 0 && rule.dcs < 0) return 1;
    dsd_analog_tones tones{}; dsd_analog_tones_get(&tones);
    if (rule.ctcss > 0) return tones.ctcss_hz > 0 && std::abs(tones.ctcss_hz - rule.ctcss) < 0.5;
    return (rule.inverse ? tones.dcs_inverse_code : tones.dcs_code) == rule.dcs;
}
extern "C" int dsd_receiver_digital_allowed(uint64_t frequency, int dmr, int color, int slot, uint32_t tg) {
    const auto rule = find(frequency);
    if (rule.talkgroup && tg != rule.talkgroup) return 0;
    if (dmr && ((rule.color >= 0 && color != rule.color) || (rule.slot && slot != rule.slot))) return 0;
    return 1;
}
