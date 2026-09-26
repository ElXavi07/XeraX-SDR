// SPDX-License-Identifier: GPL-3.0-or-later
// Schema 2 observations. The measured schema 1 harness stays unchanged.
#include "credit_history.h"
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

using namespace xerax::experiment;
using Clock = std::chrono::steady_clock;
using Micros = std::chrono::duration<double, std::micro>;
namespace {
constexpr std::uint32_t rate = 3072000;
constexpr std::uint64_t block_samples = rate / 100, snapshot_samples = rate / 4;
constexpr std::size_t mib = 1024U * 1024U;
struct Row {
    unsigned index = 0;
    std::uint64_t first = 0, end = 0;
    double due = 0, wake = 0, begin = 0, finish = 0, verified = 0, released = 0;
    bool has_verified = false, has_released = false;
    int status = -1;
    const char* verification = "not_applicable";
    const char* release_kind = "not_applicable";
};
struct Failure {
    bool present = false;
    std::string worker, message, field;
    std::uint64_t first = 0, end = 0, expected = 0, actual = 0, offset = 0;
    bool values = false, byte_offset = false;
};
struct VerifyError : std::runtime_error {
    std::string field;
    std::uint64_t expected, actual, offset;
    bool byte;
    VerifyError(const char* name, std::uint64_t wanted, std::uint64_t got, bool is_byte = false,
                std::uint64_t at = 0)
        : std::runtime_error("Snapshot verification failed"), field(name), expected(wanted),
          actual(got), offset(at), byte(is_byte) {}
};
void quoted(std::ostream& out, const std::string& value) {
    out << '"';
    for (const unsigned char c : value) {
        if (c == '"' || c == '\\') out << '\\' << static_cast<char>(c);
        else if (c < 32U) {
            char escaped[7]; std::snprintf(escaped, sizeof escaped, "\\u%04x", static_cast<unsigned>(c));
            out << escaped;
        } else out << static_cast<char>(c);
    }
    out << '"';
}
std::uint8_t pattern(std::uint64_t byte) {
    byte ^= byte >> 13U; byte *= UINT64_C(0x9e3779b97f4a7c15);
    return static_cast<std::uint8_t>((byte >> 48U) ^ (byte >> 24U) ^ byte);
}
void fill(std::vector<std::uint8_t>& data, std::uint64_t first) {
    for (std::size_t i = 0; i < data.size(); ++i) data[i] = pattern(first + i);
}
void verify(const SnapshotLease& lease, const Stream& stream, std::uint64_t first,
            const std::string& injection) {
    // Fault injection corrupts the verifier's local observation, never immutable
    // leased storage or the library. Only test runs opt in to this branch.
    if (injection == "verify-exception") throw std::runtime_error("Injected verifier exception before verification");
    auto info = lease.info();
    if (injection == "stream") ++info.stream.stream_id;
    if (injection == "epoch") ++info.stream.epoch;
    if (injection == "rate") ++info.stream.sample_rate_hz;
    if (injection == "frequency") ++info.stream.center_frequency_hz;
    if (injection == "width") ++info.stream.bytes_per_complex_sample;
    if (injection == "first") ++info.first_sample;
    if (injection == "end") ++info.end_sample;
    if (injection == "size") ++info.byte_count;
    const auto check = [](const char* field, std::uint64_t expected, std::uint64_t actual) {
        if (expected != actual) throw VerifyError(field, expected, actual);
    };
    check("stream_id", stream.stream_id, info.stream.stream_id);
    check("epoch", stream.epoch, info.stream.epoch);
    check("sample_rate_hz", stream.sample_rate_hz, info.stream.sample_rate_hz);
    check("center_frequency_hz", stream.center_frequency_hz, info.stream.center_frequency_hz);
    check("bytes_per_complex_sample", stream.bytes_per_complex_sample, info.stream.bytes_per_complex_sample);
    check("first_sample", first, info.first_sample);
    check("end_sample", first + snapshot_samples, info.end_sample);
    check("byte_count", snapshot_samples * stream.bytes_per_complex_sample, info.byte_count);
    check("lease_size", info.byte_count, lease.size());
    const auto* data = lease.data();
    if (!data) throw std::runtime_error("Accepted snapshot has no data");
    for (std::size_t i = 0; i < lease.size(); ++i) {
        const auto expected = pattern(first * stream.bytes_per_complex_sample + i);
        auto actual = data[i];
        if (injection == "byte" && i == 17U) actual ^= 1U;
        if (actual != expected) throw VerifyError("byte", expected, actual, true, i);
    }
}
void write_failure(std::ostream& out, const Failure& f) {
    out << "{\"worker\":"; quoted(out, f.worker);
    out << ",\"message\":"; quoted(out, f.message);
    out << ",\"first_sample\":" << f.first << ",\"end_sample\":" << f.end << ",\"field\":";
    if (f.field.empty()) out << "null"; else quoted(out, f.field);
    out << ",\"expected\":"; if (f.values) out << f.expected; else out << "null";
    out << ",\"actual\":"; if (f.values) out << f.actual; else out << "null";
    out << ",\"byte_offset\":"; if (f.byte_offset) out << f.offset; else out << "null";
    out << '}';
}
void write_trace(const std::string& path, const std::vector<Row>& appends, const std::vector<Row>& snaps) {
    std::ofstream out(path);
    if (!out) throw std::runtime_error("Cannot open observation trace");
    out << std::setprecision(12)
        << "kind,index,first_sample,end_sample,due_us,wake_us,begin_us,end_us,verified_us,released_us,status,verification,release_kind\n";
    const auto rows = [&](const char* kind, const std::vector<Row>& data) {
        for (const auto& r : data) {
            out << kind << ',' << r.index << ',' << r.first << ',' << r.end << ',' << r.due << ',' << r.wake
                << ',' << r.begin << ',' << r.finish << ',';
            if (r.has_verified) out << r.verified;
            out << ','; if (r.has_released) out << r.released;
            out << ',' << r.status << ',' << r.verification << ',' << r.release_kind << '\n';
        }
    };
    rows("append", appends); rows("snapshot", snaps);
    out.flush();
    if (!out) throw std::runtime_error("Observation trace write failed");
}
} // namespace

int main(int argc, char** argv) {
    try {
        std::string variant = "whole", format = "cf32", csv, injection = "none";
        unsigned seconds = 1, hz = 4, hold_ms = 0;
        for (int i = 1; i < argc; i += 2) {
            if (i + 1 >= argc) throw std::invalid_argument("Options require values");
            const std::string key(argv[i]), value(argv[i + 1]);
            if (key == "--variant") variant = value;
            else if (key == "--format") format = value;
            else if (key == "--csv") csv = value;
            else if (key == "--inject") injection = value;
            else {
                if (value.empty() || value.find_first_not_of("0123456789") != std::string::npos)
                    throw std::invalid_argument("Expected unsigned integer");
                const auto n = std::stoul(value);
                if (n > 10000UL) throw std::invalid_argument("Option too large");
                if (key == "--seconds") seconds = static_cast<unsigned>(n);
                else if (key == "--snapshot-hz") hz = static_cast<unsigned>(n);
                else if (key == "--hold-ms") hold_ms = static_cast<unsigned>(n);
                else throw std::invalid_argument("Unknown option");
            }
        }
        if (csv.empty()) throw std::invalid_argument("A --csv path is required to preserve evidence");
        if ((format != "cu8" && format != "cf32") || !seconds || seconds > 600 || !hz || hz > 100)
            throw std::invalid_argument("Unsupported workload");
        if (variant != "none" && variant != "whole" && variant != "chunk64" && variant != "chunk256")
            throw std::invalid_argument("Unsupported variant");
#ifndef XERAX_CHUNK_COPY
        if (variant == "chunk64" || variant == "chunk256")
            throw std::invalid_argument("Frozen baseline has no chunked-copy API");
#endif
        const std::vector<std::string> injections{"none", "byte", "stream", "epoch", "rate", "frequency",
            "width", "first", "end", "size", "append", "consumer-exception", "verify-exception", "overcommit"};
        if (std::find(injections.begin(), injections.end(), injection) == injections.end() ||
            (variant == "none" && injection != "none" && injection != "append"))
            throw std::invalid_argument("Unsupported fault injection");
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
        std::vector<Row> appends, snaps;
        appends.reserve(seconds * 100U); snaps.reserve(seconds * hz);
        Failure producer_failure, consumer_failure, control_failure;
        const auto base = Clock::now() + std::chrono::milliseconds(50);
        const auto stamp = [&base](Clock::time_point point) { return Micros(point - base).count(); };
        std::thread producer, consumer;
        try {
            producer = std::thread([&] {
                Row row;
                try {
                    for (unsigned i = 0; i < seconds * 100U && !stop.load(); ++i) {
                        fill(block, first * width);
                        const auto due = base + std::chrono::milliseconds(10U * i);
                        std::this_thread::sleep_until(due);
                        row = {}; row.index = i; row.first = first + ((injection == "append" && i == 3U) ? 1U : 0U);
                        row.end = row.first + block_samples; row.due = stamp(due); row.wake = stamp(Clock::now());
                        row.begin = stamp(Clock::now());
                        const auto result = history.append(stream, row.first, block.data(), block.size());
                        row.finish = stamp(Clock::now()); row.status = static_cast<int>(result);
                        appends.push_back(row); // Retain the rejecting operation, too.
                        if (result != Status::Ok) throw std::runtime_error("Synthetic append rejected");
                        first += block_samples; latest.store(first);
                    }
                } catch (const std::exception& e) {
                    producer_failure = {true, "producer", e.what(), "append_status", row.first, row.end,
                        0, static_cast<std::uint64_t>(row.status < 0 ? 0 : row.status), 0, row.status >= 0, false};
                    stop.store(true);
                } catch (...) {
                    producer_failure.present = true; producer_failure.worker = "producer";
                    producer_failure.message = "Nonstandard producer exception"; stop.store(true);
                }
            });
            if (variant != "none") consumer = std::thread([&] {
                SnapshotLease active;
                std::size_t active_row = 0;
                Clock::time_point release_at{};
                const auto release = [&](const char* why) {
                    if (active) {
                        active.reset(); snaps[active_row].released = stamp(Clock::now());
                        snaps[active_row].has_released = true;
                        snaps[active_row].release_kind = why;
                    }
                };
                try {
                    bool injected = false;
                    for (unsigned i = 0; i < seconds * hz && !stop.load(); ++i) {
                        const auto due = base + std::chrono::nanoseconds(static_cast<std::int64_t>(i) * INT64_C(1000000000) / hz);
                        std::this_thread::sleep_until(due);
                        Row row; row.index = i; row.due = stamp(due); row.wake = stamp(Clock::now());
                        if (active && Clock::now() >= release_at) release("tick");
                        row.end = latest.load(); row.first = row.end - snapshot_samples;
                        row.begin = stamp(Clock::now());
                        SnapshotLease result;
                        if (variant == "whole") result = history.snapshot(stream, row.first, snapshot_samples);
#ifdef XERAX_CHUNK_COPY
                        else {
                            ChunkCopyOptions options;
                            options.chunk_bytes = (variant == "chunk64" ? 64U : 256U) * 1024U;
                            options.deadline = Clock::now() + std::chrono::milliseconds(50);
                            result = history.snapshot_chunked(stream, row.first, snapshot_samples, options);
                        }
#endif
                        row.finish = stamp(Clock::now()); row.status = static_cast<int>(result.status());
                        row.verification = result ? "pending" : "not_applicable";
                        snaps.push_back(row);
                        auto& recorded = snaps.back();
                        if (result) {
                            try {
                                const auto fault = injected ? std::string("none") : injection;
                                verify(result, stream, row.first, fault); injected = true;
                                recorded.verified = stamp(Clock::now()); recorded.has_verified = true; recorded.verification = "ok";
                                if (fault == "consumer-exception") throw std::runtime_error("Injected consumer exception after verification");
                                if (active || fault == "overcommit") throw std::runtime_error("Single-slot pool overcommitted (injected if requested)");
                            } catch (const VerifyError& e) {
                                recorded.verified = stamp(Clock::now()); recorded.has_verified = true; recorded.verification = "failed";
                                result.reset(); recorded.released = stamp(Clock::now()); recorded.has_released = true; recorded.release_kind = "failure";
                                consumer_failure = {true, "consumer", e.what(), e.field, row.first, row.end,
                                    e.expected, e.actual, e.offset, true, e.byte};
                                throw;
                            } catch (...) {
                                if (!recorded.has_verified) {
                                    recorded.verified = stamp(Clock::now()); recorded.has_verified = true;
                                    recorded.verification = "aborted";
                                }
                                result.reset(); recorded.released = stamp(Clock::now()); recorded.has_released = true; recorded.release_kind = "failure";
                                throw;
                            }
                            active = std::move(result); active_row = snaps.size() - 1U;
                            release_at = base + std::chrono::duration_cast<Clock::duration>(Micros(recorded.verified))
                                + std::chrono::milliseconds(hold_ms);
                            if (!hold_ms) release("immediate");
                        } else if (result.status() != Status::Busy && result.status() != Status::NotRetained
#ifdef XERAX_CHUNK_COPY
                                   && result.status() != Status::DeadlineExpired
#endif
                        ) throw std::runtime_error("Unexpected snapshot error");
                    }
                } catch (const std::exception& e) {
                    if (!consumer_failure.present) {
                        consumer_failure.present = true; consumer_failure.worker = "consumer"; consumer_failure.message = e.what();
                        if (!snaps.empty()) { consumer_failure.first = snaps.back().first; consumer_failure.end = snaps.back().end; }
                    }
                    stop.store(true);
                } catch (...) {
                    consumer_failure.present = true; consumer_failure.worker = "consumer";
                    consumer_failure.message = "Nonstandard consumer exception"; stop.store(true);
                }
                release("shutdown"); // A right-censored hold, not a completed minimum hold.
            });
        } catch (const std::exception& e) {
            stop.store(true); control_failure.present = true; control_failure.worker = "control";
            control_failure.message = e.what();
        }
        if (producer.joinable()) producer.join();
        if (consumer.joinable()) consumer.join();
        const auto credits = history.credit_stats();
        bool failed = producer_failure.present || consumer_failure.present || control_failure.present;
        if (!failed && (appends.size() != seconds * 100U ||
            snaps.size() != (variant == "none" ? 0U : seconds * hz) || credits.outstanding_count ||
            credits.total_payload_bytes != 15U * mib)) {
            failed = true; control_failure.present = true; control_failure.worker = "control";
            control_failure.message = "Incomplete workload, leaked credit or changed budget";
        }
        bool trace_written = false;
        std::string trace_error;
        try { write_trace(csv, appends, snaps); trace_written = true; }
        catch (const std::exception& e) { trace_error = e.what(); failed = true; }
        std::cout << std::setprecision(12) << "{\"schema\":2,\"scope\":\"observed storage harness; no hardware or decoder\","
            << "\"complete\":" << (failed ? "false" : "true") << ",\"variant\":"; quoted(std::cout, variant);
        std::cout << ",\"format\":"; quoted(std::cout, format);
        std::cout << ",\"injection\":"; quoted(std::cout, injection);
        std::cout << ",\"seconds\":" << seconds << ",\"snapshot_hz\":" << hz << ",\"hold_ms\":" << hold_ms
            << ",\"sample_rate_hz\":" << rate << ",\"block_samples\":" << block_samples
            << ",\"snapshot_samples\":" << snapshot_samples << ",\"appends\":" << appends.size()
            << ",\"snapshot_attempts\":" << snaps.size() << ",\"outstanding_credits\":" << credits.outstanding_count
            << ",\"payload_bytes\":" << credits.total_payload_bytes << ",\"input_vector_bytes\":" << block.size()
            << ",\"trace_written\":" << (trace_written ? "true" : "false") << ",\"trace_error\":";
        if (trace_error.empty()) std::cout << "null"; else quoted(std::cout, trace_error);
        std::cout << ",\"failures\":[";
        bool comma = false;
        for (const auto* failure : {&producer_failure, &consumer_failure, &control_failure}) if (failure->present) {
            if (comma) std::cout << ',';
            write_failure(std::cout, *failure); comma = true;
        }
        std::cout << "]}\n";
        if (failed) std::cerr << "Observed workload failed; inspect JSON and any retained CSV.\n";
        return failed ? 1 : 0;
    } catch (const std::exception& e) {
        std::cerr << "Observed harness setup failed: " << e.what() << '\n'; return 2;
    }
}
