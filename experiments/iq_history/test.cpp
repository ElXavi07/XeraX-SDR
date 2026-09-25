// SPDX-License-Identifier: GPL-3.0-or-later
#include "iq_history.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <exception>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

using namespace xerax::experiment;

namespace {
void require(bool yes, const char* message) {
    if (!yes) throw std::runtime_error(message);
}

Stream source(std::uint32_t bps = 2, std::uint64_t epoch = 1) {
    return {7, epoch, 3072000, 451100000, bps};
}

std::vector<std::uint8_t> bytes_for(std::uint64_t first, std::size_t samples, const Stream& s) {
    std::vector<std::uint8_t> out(samples * s.bytes_per_complex_sample);
    for (std::size_t n = 0; n < samples; ++n)
        for (std::size_t b = 0; b < s.bytes_per_complex_sample; ++b)
            out[n * s.bytes_per_complex_sample + b] = static_cast<std::uint8_t>(
                (((first + n) % 251) * 17 + b * 29 + (s.epoch % 251) * 13 + s.stream_id % 251) % 251);
    return out;
}

void check_snapshot(const Snapshot& snapshot, const Stream& s, std::uint64_t first, std::size_t count) {
    require(snapshot.status == Status::Ok, "snapshot status");
    require(snapshot.first_sample == first && snapshot.end_sample == first + count, "snapshot interval");
    require(snapshot.stream.stream_id == s.stream_id && snapshot.stream.epoch == s.epoch &&
            snapshot.stream.sample_rate_hz == s.sample_rate_hz &&
            snapshot.stream.center_frequency_hz == s.center_frequency_hz &&
            snapshot.stream.bytes_per_complex_sample == s.bytes_per_complex_sample, "snapshot metadata");
    require(snapshot.bytes == bytes_for(first, count, s), "snapshot byte parity");
}

void wraparound_and_model() {
    for (const auto bps : {2U, 8U}) {
        const auto s = source(bps);
        for (const auto samples_capacity : {1U, 2U, 7U, 31U, 65U}) {
            History h(samples_capacity * bps + 1); // one unusable byte must never form a partial sample
            require(h.begin_epoch(s) == Status::Ok, "begin model epoch");
            require(h.capacity_bytes() == samples_capacity * bps + 1, "strict payload capacity");
            require(h.state().usable_capacity_bytes == samples_capacity * bps, "aligned capacity");
            std::vector<std::uint8_t> oracle;
            std::uint64_t next = 1000;
            for (unsigned step = 0; step < 700; ++step) {
                const auto count = 1 + (step * 43U + 7U) % (samples_capacity * 3U);
                const auto input = bytes_for(next, count, s);
                const auto result = h.append(s, next, input.data(), input.size());
                require(result == (count > samples_capacity ? Status::Truncated : Status::Ok), "append truncation status");
                oracle.insert(oracle.end(), input.begin(), input.end());
                const auto capacity_bytes = samples_capacity * bps;
                if (oracle.size() > capacity_bytes)
                    oracle.erase(oracle.begin(), oracle.begin() + static_cast<std::ptrdiff_t>(oracle.size() - capacity_bytes));
                next += count;
                const auto state = h.state();
                const auto retained_samples = oracle.size() / bps;
                require(state.retained_bytes == oracle.size() && state.retained_bytes <= capacity_bytes, "bounded retained bytes");
                require(state.first_sample == next - retained_samples && state.end_sample == next, "retained absolute range");
                const auto all = h.snapshot(s, state.first_sample, retained_samples);
                require(all.status == Status::Ok && all.bytes == oracle, "independent append/erase oracle");
                check_snapshot(h.snapshot(s, next - 1, 1), s, next - 1, 1);
                check_snapshot(h.snapshot(s, state.first_sample, 1), s, state.first_sample, 1);
                require(h.snapshot(s, state.first_sample - 1, 1).status == Status::NotRetained, "overwritten prefix rejected");
                require(h.snapshot(s, next, 1).status == Status::NotRetained, "unreceived future rejected");
            }
        }
    }
}

void bounds_and_epochs() {
    bool zero_threw = false;
    try { History bad(0); } catch (const std::invalid_argument&) { zero_threw = true; }
    require(zero_threw, "zero capacity rejected");
    History tiny(1);
    require(tiny.begin_epoch(source()) == Status::InvalidMetadata, "insufficient whole-sample capacity");
    History h(32);
    auto s = source();
    auto input = bytes_for(10, 8, s);
    require(h.append(s, 10, input.data(), input.size()) == Status::NoEpoch, "explicit epoch required");
    require(h.snapshot(s, 10, 1).status == Status::NoEpoch, "no invented epoch");
    auto invalid = s; invalid.sample_rate_hz = 0;
    require(h.begin_epoch(invalid) == Status::InvalidMetadata, "zero sample rate rejected");
    invalid = s; invalid.bytes_per_complex_sample = 4;
    require(h.begin_epoch(invalid) == Status::InvalidMetadata, "unsupported format rejected");
    require(h.begin_epoch(s) == Status::Ok, "begin test epoch");
    require(h.snapshot(s, 0, 1).status == Status::NotRetained, "empty history rejected");
    require(h.append(s, 10, nullptr, input.size()) == Status::InvalidArgument, "null append rejected");
    require(h.append(s, 10, input.data(), 0) == Status::InvalidArgument, "empty append rejected");
    require(h.append(s, 10, input.data(), 3) == Status::InvalidArgument, "partial complex sample rejected");
    const auto maximum = std::numeric_limits<std::uint64_t>::max();
    require(h.append(s, maximum - 1, input.data(), 4) == Status::ArithmeticOverflow, "append endpoint overflow");
    require(h.snapshot(s, maximum - 1, 2).status == Status::ArithmeticOverflow, "snapshot endpoint overflow");
    require(h.snapshot(s, 0, maximum / 2 + 1).status == Status::ArithmeticOverflow, "snapshot byte multiplication overflow");
    require(h.snapshot(s, 0, 0).status == Status::InvalidArgument, "empty snapshot rejected");
    require(h.append(s, 10, input.data(), input.size()) == Status::Ok, "valid append");
    check_snapshot(h.snapshot(s, 10, 8), s, 10, 8);
    auto wrong = s; wrong.epoch++;
    require(h.append(wrong, 18, input.data(), input.size()) == Status::EpochMismatch, "unbegun epoch rejected");
    require(h.snapshot(wrong, 10, 8).status == Status::EpochMismatch, "stale/wrong snapshot identity rejected");
    wrong = s; wrong.stream_id++;
    require(h.append(wrong, 18, input.data(), input.size()) == Status::EpochMismatch, "wrong stream rejected");
    check_snapshot(h.snapshot(s, 10, 8), s, 10, 8);
    require(h.begin_epoch(s) == Status::EpochMismatch, "same epoch cannot be reused");

    // A gap never becomes silent samples and the new block is not accepted implicitly.
    require(h.append(s, 19, input.data(), input.size()) == Status::Discontinuity, "missing interval invalidates history");
    require(h.state().retained_bytes == 0 && h.state().requires_new_epoch, "gap purges stale history");
    require(h.snapshot(s, 10, 8).status == Status::Discontinuity, "gap cannot be spanned");
    require(h.append(s, 18, input.data(), input.size()) == Status::Discontinuity, "explicit new epoch after gap");
    const auto old = s; s.epoch++;
    require(h.begin_epoch(s) == Status::Ok, "new gap epoch accepted");
    input = bytes_for(19, 8, s);
    require(h.append(s, 19, input.data(), input.size()) == Status::Ok, "post-gap epoch append");
    check_snapshot(h.snapshot(s, 19, 8), s, 19, 8);
    require(h.snapshot(old, 19, 8).status == Status::EpochMismatch, "old epoch stays stale");
    require(h.begin_epoch(old) == Status::EpochMismatch, "epoch rollback rejected");
    require(h.append(s, 26, input.data(), input.size()) == Status::Discontinuity, "overlap/reordered input invalidates history");

    for (unsigned change = 0; change < 3; ++change) {
        s.epoch++;
        require(h.begin_epoch(s) == Status::Ok, "metadata test epoch");
        input = bytes_for(0, 2, s);
        require(h.append(s, 0, input.data(), input.size()) == Status::Ok, "metadata test append");
        auto changed = s;
        if (change == 0) changed.center_frequency_hz += 12500;
        if (change == 1) changed.sample_rate_hz /= 2;
        if (change == 2) changed.bytes_per_complex_sample = 8;
        auto new_input = bytes_for(2, 2, changed);
        require(h.snapshot(changed, 0, 1).status == Status::MetadataMismatch, "wrong snapshot metadata rejected");
        check_snapshot(h.snapshot(s, 0, 2), s, 0, 2); // a read cannot invalidate stored data
        require(h.append(changed, 2, new_input.data(), new_input.size()) == Status::MetadataMismatch, "unannounced source change rejected");
        require(h.state().retained_bytes == 0 && h.state().requires_new_epoch, "source change invalidates history");
        changed.epoch++;
        require(h.begin_epoch(changed) == Status::Ok, "announced metadata change resets history");
        require(h.snapshot(s, 0, 1).status == Status::EpochMismatch, "retune/rate/format cannot expose old samples");
        new_input = bytes_for(2, 2, changed);
        require(h.append(changed, 2, new_input.data(), new_input.size()) == Status::Ok, "new metadata append");
        check_snapshot(h.snapshot(changed, 2, 2), changed, 2, 2);
        s = changed;
    }

    // Endpoints immediately below uint64 maximum remain exact; no signed arithmetic.
    s.epoch++;
    require(h.begin_epoch(s) == Status::Ok, "high index epoch");
    input = bytes_for(maximum - 2, 2, s);
    require(h.append(s, maximum - 2, input.data(), input.size()) == Status::Ok, "large valid index");
    check_snapshot(h.snapshot(s, maximum - 2, 2), s, maximum - 2, 2);
}

void independent_receivers_and_owned_copies() {
    History a(32), b(64);
    auto sa = source(), sb = source(8); sb.stream_id++;
    require(a.begin_epoch(sa) == Status::Ok && b.begin_epoch(sb) == Status::Ok, "independent epochs");
    auto data_a = bytes_for(0, 8, sa), data_b = bytes_for(900, 4, sb);
    require(a.append(sa, 0, data_a.data(), data_a.size()) == Status::Ok, "receiver A append");
    require(b.append(sb, 900, data_b.data(), data_b.size()) == Status::Ok, "receiver B append");
    auto owned = a.snapshot(sa, 0, 8);
    sa.epoch++;
    require(a.begin_epoch(sa) == Status::Ok, "receiver A reset");
    require(owned.bytes == data_a && owned.stream.epoch == 1, "owned snapshot survives reset");
    owned.bytes[0] ^= 255;
    check_snapshot(b.snapshot(sb, 900, 4), sb, 900, 4);
    auto b_copy = b.snapshot(sb, 900, 4); b_copy.bytes[0] ^= 255;
    check_snapshot(b.snapshot(sb, 900, 4), sb, 900, 4);
}

void concurrent_producer_and_snapshots() {
    History h(4096);
    const auto initial = source();
    require(h.begin_epoch(initial) == Status::Ok, "concurrent initial epoch");
    std::atomic<bool> done{false}, start{false};
    std::atomic<unsigned> snapshots{0};
    std::exception_ptr writer_error, reader_error;
    std::thread writer([&] {
        try {
            while (!start.load()) std::this_thread::yield();
            auto s = initial;
            std::uint64_t next = 0;
            for (unsigned block = 0; block < 12000; ++block) {
                if (block == 6000) {
                    ++s.epoch; s.center_frequency_hz += 12500;
                    require(h.begin_epoch(s) == Status::Ok, "concurrent epoch transition");
                    next = 1000000;
                }
                auto input = bytes_for(next, 64, s);
                require(h.append(s, next, input.data(), input.size()) == Status::Ok, "concurrent append");
                next += 64;
                if (block % 16 == 0) std::this_thread::yield();
            }
        } catch (...) { writer_error = std::current_exception(); }
        done = true;
    });
    std::thread reader([&] {
        try {
            start = true;
            unsigned after_done = 0;
            while (!done.load() || after_done++ < 4) {
                const auto state = h.state();
                if (!state.has_samples) { std::this_thread::yield(); continue; }
                const auto count = std::min<std::uint64_t>(state.end_sample - state.first_sample, 128);
                const auto result = h.snapshot(state.stream, state.end_sample - count, count);
                if (result.status == Status::Ok) {
                    check_snapshot(result, state.stream, state.end_sample - count, static_cast<std::size_t>(count));
                    ++snapshots;
                } else {
                    require(result.bytes.empty(), "failed snapshot contains no stale payload");
                    require(result.status == Status::NotRetained || result.status == Status::EpochMismatch,
                            "only overwrite/epoch races allowed");
                }
            }
        } catch (...) { reader_error = std::current_exception(); start = true; }
    });
    writer.join(); reader.join();
    if (writer_error) std::rethrow_exception(writer_error);
    if (reader_error) std::rethrow_exception(reader_error);
    require(snapshots.load() >= 4, "successful concurrent/terminal snapshots");
}

void benchmark() {
    using Clock = std::chrono::steady_clock;
    constexpr std::size_t capacity = 16 * 1024 * 1024;
    constexpr std::size_t block_samples = 30720; // 10 ms at 3.072 MS/s
    constexpr unsigned append_count = 2000;
    constexpr unsigned snapshot_count = 100;
    for (const auto bps : {2U, 8U}) {
        auto s = source(bps);
        History h(capacity);
        require(h.begin_epoch(s) == Status::Ok, "benchmark epoch");
        auto input = bytes_for(0, block_samples, s);
        for (unsigned warm = 0; warm < 50; ++warm)
            require(h.append(s, static_cast<std::uint64_t>(warm) * block_samples, input.data(), input.size()) == Status::Ok,
                    "benchmark warmup");
        std::uint64_t next = 50ULL * block_samples;
        const auto start = Clock::now();
        for (unsigned i = 0; i < append_count; ++i) {
            require(h.append(s, next, input.data(), input.size()) == Status::Ok, "benchmark append");
            next += block_samples;
        }
        const auto appended = Clock::now();
        constexpr std::uint64_t history_samples = 768000; // 250 ms
        std::uint64_t checksum = 0;
        for (unsigned i = 0; i < snapshot_count; ++i) {
            const auto shot = h.snapshot(s, next - history_samples, history_samples);
            require(shot.status == Status::Ok, "benchmark snapshot");
            checksum += shot.bytes.front() + shot.bytes.back() + shot.bytes.size();
        }
        const auto end = Clock::now();
        std::cout << "{\"schema\":1,\"scope\":\"isolated-history-copy\",\"bytes_per_complex_sample\":" << bps
                  << ",\"capacity_bytes\":" << capacity << ",\"append_count\":" << append_count
                  << ",\"append_bytes\":" << static_cast<std::uint64_t>(append_count) * input.size()
                  << ",\"append_seconds\":" << std::chrono::duration<double>(appended - start).count()
                  << ",\"snapshot_count\":" << snapshot_count << ",\"snapshot_bytes\":" << history_samples * bps * snapshot_count
                  << ",\"snapshot_seconds\":" << std::chrono::duration<double>(end - appended).count()
                  << ",\"checksum\":" << checksum << "}\n";
    }
}
} // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--benchmark") {
            benchmark(); return 0;
        }
        if (argc != 1) throw std::runtime_error("usage: xerax_iq_history_test [--benchmark]");
        wraparound_and_model();
        bounds_and_epochs();
        independent_receivers_and_owned_copies();
        concurrent_producer_and_snapshots();
        std::cout << "IQ history contract passed: CU8/CF32 exact bytes, 7000 model steps, boundaries, epochs, concurrency.\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "IQ history failure: " << e.what() << '\n';
        return 1;
    }
}
