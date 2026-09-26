// SPDX-License-Identifier: GPL-3.0-or-later
// Paced storage workload, not a radio/driver or whole-decoder benchmark.
#include "credit_history.h"
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <exception>
#include <fstream>
#include <iomanip>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

using namespace xerax::experiment;
using Clock = std::chrono::steady_clock;
using Micros = std::chrono::duration<double, std::micro>;
namespace {
constexpr std::uint32_t rate = 3072000;
constexpr std::uint64_t block_samples = rate / 100;
constexpr std::uint64_t snapshot_samples = rate / 4;
constexpr std::size_t mib = 1024U * 1024U;
struct Row { unsigned index; double call_us; double wake_late_us; bool missed_deadline; };
struct SnapRow { unsigned index; double call_us; double verify_us; int status; };

// Reproducible index-dependent opaque bytes. CF32 is a storage width here,
// not an assertion of valid numerical RF samples or signal statistics.
std::uint8_t pattern(std::uint64_t byte) {
    byte ^= byte >> 13U;
    byte *= UINT64_C(0x9e3779b97f4a7c15);
    return static_cast<std::uint8_t>((byte >> 48U) ^ (byte >> 24U) ^ byte);
}
void fill(std::vector<std::uint8_t>& bytes, std::uint64_t first_byte) {
    for (std::size_t i = 0; i < bytes.size(); ++i) bytes[i] = pattern(first_byte + i);
}
void verify(const SnapshotLease& lease, const Stream& stream, std::uint64_t first) {
    if (lease.info().stream.epoch != stream.epoch || lease.info().first_sample != first ||
        lease.info().end_sample != first + snapshot_samples ||
        lease.size() != snapshot_samples * stream.bytes_per_complex_sample)
        throw std::runtime_error("Snapshot metadata/length mismatch");
    const auto start = first * stream.bytes_per_complex_sample;
    const auto* data = lease.data();
    for (std::size_t i = 0; i < lease.size(); ++i)
        if (data[i] != pattern(start + i)) throw std::runtime_error("Snapshot byte mismatch");
}
void stats(const char* name, std::vector<double> values) {
    std::printf(",\"%s\":", name);
    if (values.empty()) { std::printf("null"); return; }
    std::sort(values.begin(), values.end());
    const auto percentile = [&](double p) {
        const auto rank = static_cast<std::size_t>(std::ceil(p * static_cast<double>(values.size())));
        return values[rank ? rank - 1U : 0U];
    };
    std::printf("{\"n\":%zu,\"p50\":%.6f,\"p95\":%.6f,\"p99\":%.6f,\"max\":%.6f}",
                values.size(), percentile(.50), percentile(.95), percentile(.99), values.back());
}
} // namespace

int main(int argc, char** argv) {
    try {
        std::string variant = "whole", format = "cf32", csv;
        unsigned seconds = 60, snapshot_hz = 10, hold_ms = 0;
        for (int i = 1; i < argc; i += 2) {
            if (i + 1 >= argc) throw std::invalid_argument("Options require values");
            const std::string key(argv[i]), value(argv[i + 1]);
            if (key == "--variant") variant = value;
            else if (key == "--format") format = value;
            else if (key == "--csv") csv = value;
            else {
                if (value.empty() || value.find_first_not_of("0123456789") != std::string::npos)
                    throw std::invalid_argument("Expected unsigned integer option");
                const auto n = std::stoul(value);
                if (n > 60000UL) throw std::invalid_argument("Numeric option too large");
                if (key == "--seconds") seconds = static_cast<unsigned>(n);
                else if (key == "--snapshot-hz") snapshot_hz = static_cast<unsigned>(n);
                else if (key == "--hold-ms") hold_ms = static_cast<unsigned>(n);
                else throw std::invalid_argument("Unknown option");
            }
        }
        if (format != "cu8" && format != "cf32") throw std::invalid_argument("Unknown format");
        if (variant != "none" && variant != "whole" && variant != "chunk64" && variant != "chunk256")
            throw std::invalid_argument("Unknown variant");
#ifndef XERAX_CHUNK_COPY
        if (variant == "chunk64" || variant == "chunk256")
            throw std::invalid_argument("Frozen baseline has no chunked-copy API");
#endif
        if (!seconds || seconds > 600 || !snapshot_hz || snapshot_hz > 100 || hold_ms > 10000)
            throw std::invalid_argument("Workload outside bounds");
        const std::uint32_t width = format == "cu8" ? 2U : 8U;
        const Stream stream{1, 1, rate, 451100000, width};
        CreditHistory history({8U * mib, 7U * mib, 1U, 15U * mib});
        if (history.begin_epoch(stream) != Status::Ok) throw std::runtime_error("Epoch rejected");
        std::vector<std::uint8_t> block(static_cast<std::size_t>(block_samples * width));
        std::uint64_t first = 0;
        for (unsigned i = 0; i < 30U; ++i) {
            fill(block, first * width);
            if (history.append(stream, first, block.data(), block.size()) != Status::Ok)
                throw std::runtime_error("Prefill rejected");
            first += block_samples;
        }
        std::atomic<std::uint64_t> latest{first};
        std::atomic<bool> stop{false};
        std::vector<Row> rows; rows.reserve(seconds * 100U);
        std::vector<SnapRow> snaps; snaps.reserve(seconds * snapshot_hz);
        std::exception_ptr producer_error, consumer_error;
        const auto base = Clock::now() + std::chrono::milliseconds(50);
        std::thread producer, consumer;
        try {
            producer = std::thread([&] {
                try {
                    for (unsigned i = 0; i < seconds * 100U && !stop.load(); ++i) {
                        fill(block, first * width); // preparation excluded from append-call duration
                        const auto due = base + std::chrono::milliseconds(10U * i);
                        std::this_thread::sleep_until(due);
                        const auto begin = Clock::now();
                        const auto result = history.append(stream, first, block.data(), block.size());
                        const auto end = Clock::now();
                        if (result != Status::Ok) throw std::runtime_error("Synthetic append rejected");
                        first += block_samples;
                        latest.store(first);
                        rows.push_back({i, Micros(end - begin).count(),
                                        std::max(0.0, Micros(begin - due).count()),
                                        end > due + std::chrono::milliseconds(10)});
                    }
                } catch (...) { producer_error = std::current_exception(); stop.store(true); }
            });
            if (variant != "none") consumer = std::thread([&] {
                try {
                    SnapshotLease active;
                    Clock::time_point release_at{};
                    for (unsigned i = 0; i < seconds * snapshot_hz && !stop.load(); ++i) {
                        const auto due = base + std::chrono::nanoseconds(
                            static_cast<std::int64_t>(i) * INT64_C(1000000000) / snapshot_hz);
                        std::this_thread::sleep_until(due);
                        if (active && Clock::now() >= release_at) active.reset();
                        const auto end_sample = latest.load();
                        const auto start_sample = end_sample - snapshot_samples;
                        const auto begin = Clock::now();
                        SnapshotLease result;
                        if (variant == "whole") result = history.snapshot(stream, start_sample, snapshot_samples);
#ifdef XERAX_CHUNK_COPY
                        else {
                            ChunkCopyOptions options;
                            options.chunk_bytes = (variant == "chunk64" ? 64U : 256U) * 1024U;
                            options.deadline = begin + std::chrono::milliseconds(50);
                            result = history.snapshot_chunked(stream, start_sample, snapshot_samples, options);
                        }
#endif
                        const auto copy_end = Clock::now();
                        const auto status = result.status();
                        if (result) verify(result, stream, start_sample);
                        const auto verified = Clock::now();
                        snaps.push_back({i, Micros(copy_end - begin).count(),
                                         Micros(verified - copy_end).count(), static_cast<int>(status)});
                        if (result) {
                            if (active) throw std::runtime_error("Single-slot pool overcommitted");
                            active = std::move(result);
                            release_at = verified + std::chrono::milliseconds(hold_ms);
                            if (!hold_ms) active.reset();
                        } else if (status != Status::Busy && status != Status::NotRetained
#ifdef XERAX_CHUNK_COPY
                                   && status != Status::DeadlineExpired
#endif
                        ) throw std::runtime_error("Unexpected snapshot error");
                    }
                } catch (...) { consumer_error = std::current_exception(); stop.store(true); }
            });
        } catch (...) {
            stop.store(true);
            if (producer.joinable()) producer.join();
            if (consumer.joinable()) consumer.join();
            throw;
        }
        producer.join();
        if (consumer.joinable()) consumer.join();
        if (producer_error) std::rethrow_exception(producer_error);
        if (consumer_error) std::rethrow_exception(consumer_error);
        if (rows.size() != seconds * 100U) throw std::runtime_error("Incomplete producer workload");
        const auto credits = history.credit_stats();
        if (credits.outstanding_count || credits.total_payload_bytes != 15U * mib)
            throw std::runtime_error("Credit leak or budget mismatch");
        std::vector<double> append, wake, copy, rejected, check;
        unsigned missed = 0, over_budget = 0, busy = 0, expired = 0, not_retained = 0;
        for (const auto& r : rows) {
            append.push_back(r.call_us); wake.push_back(r.wake_late_us);
            missed += r.missed_deadline ? 1U : 0U;
            over_budget += r.call_us > 10000.0 ? 1U : 0U;
        }
        for (const auto& s : snaps) {
            if (s.status == static_cast<int>(Status::Ok)) { copy.push_back(s.call_us); check.push_back(s.verify_us); }
            else {
                rejected.push_back(s.call_us);
                busy += s.status == static_cast<int>(Status::Busy) ? 1U : 0U;
                not_retained += s.status == static_cast<int>(Status::NotRetained) ? 1U : 0U;
#ifdef XERAX_CHUNK_COPY
                expired += s.status == static_cast<int>(Status::DeadlineExpired) ? 1U : 0U;
#endif
            }
        }
        if (!csv.empty()) {
            std::ofstream out(csv); if (!out) throw std::runtime_error("Cannot open trace");
            out << std::setprecision(12) << "kind,index,call_us,wake_late_us,missed_deadline,status,verify_us\n";
            for (const auto& r : rows) out << "append," << r.index << ',' << r.call_us << ',' << r.wake_late_us
                << ',' << r.missed_deadline << ",0,0\n";
            for (const auto& s : snaps) out << "snapshot," << s.index << ',' << s.call_us << ",0,0,"
                << s.status << ',' << s.verify_us << '\n';
            if (!out) throw std::runtime_error("Trace write failed");
        }
        std::printf("{\"schema\":1,\"scope\":\"paced opaque storage copies; no hardware or decoder\","
                    "\"variant\":\"%s\",\"format\":\"%s\",\"seconds\":%u,\"sample_rate_hz\":%u,"
                    "\"block_ms\":10,\"snapshot_ms\":250,\"snapshot_hz\":%u,\"hold_ms\":%u,"
                    "\"payload_bytes\":%zu,\"appends\":%zu,\"snapshot_attempts\":%zu,\"snapshot_ok\":%zu,"
                    "\"snapshot_busy\":%u,\"snapshot_deadline\":%u,\"snapshot_not_retained\":%u,"
                    "\"finish_after_next_scheduled_block\":%u,\"append_call_over_10ms\":%u,"
                    "\"byte_verification\":\"all accepted bytes; consumer work excluded from copy-call timer\","
                    "\"scheduler_settings_changed\":false,\"hardware_input_drops_measured\":false",
                    variant.c_str(), format.c_str(), seconds, rate, snapshot_hz, hold_ms,
                    credits.total_payload_bytes, rows.size(), snaps.size(), copy.size(), busy, expired,
                    not_retained, missed, over_budget);
        stats("append_us", append); stats("wake_lateness_us", wake); stats("snapshot_success_us", copy);
        stats("snapshot_rejected_us", rejected); stats("verification_us", check);
        std::printf("}\n");
        return 0;
    } catch (const std::exception& e) { std::fprintf(stderr, "IQ latency experiment failed: %s\n", e.what()); return 1; }
}
