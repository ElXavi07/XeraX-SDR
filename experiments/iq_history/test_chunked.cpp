// SPDX-License-Identifier: GPL-3.0-or-later
#include "credit_history.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <functional>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <vector>

using namespace xerax::experiment;

namespace {
void require(bool yes, const char* message) {
    if (!yes) throw std::runtime_error(message);
}

Stream source(std::uint32_t bps = 2) { return {97, 1, 3072000, 451100000, bps}; }

std::vector<std::uint8_t> data_for(std::uint64_t first, std::size_t count, const Stream& stream) {
    std::vector<std::uint8_t> bytes(count * stream.bytes_per_complex_sample);
    for (std::size_t n = 0; n < count; ++n)
        for (std::size_t byte = 0; byte < stream.bytes_per_complex_sample; ++byte)
            bytes[n * stream.bytes_per_complex_sample + byte] = static_cast<std::uint8_t>(
                (((first + n) % 251) * 13 + byte * 41 + (stream.epoch % 251) * 17) % 251);
    return bytes;
}

void check(const SnapshotLease& lease, const Stream& stream, std::uint64_t first, std::size_t count) {
    require(lease.status() == Status::Ok && static_cast<bool>(lease), "chunked lease success");
    require(lease.info().stream.stream_id == stream.stream_id && lease.info().stream.epoch == stream.epoch &&
            lease.info().stream.sample_rate_hz == stream.sample_rate_hz &&
            lease.info().stream.center_frequency_hz == stream.center_frequency_hz &&
            lease.info().stream.bytes_per_complex_sample == stream.bytes_per_complex_sample, "chunked metadata");
    require(lease.info().first_sample == first && lease.info().end_sample == first + count, "chunked exact interval");
    const auto expected = data_for(first, count, stream);
    require(lease.data() != nullptr && lease.size() == expected.size() &&
            std::equal(expected.begin(), expected.end(), lease.data()), "chunked exact byte parity");
}

void check_error(const SnapshotLease& lease, Status expected, const CreditHistory& history) {
    require(lease.status() == expected && !static_cast<bool>(lease), "chunked expected error");
    require(lease.data() == nullptr && lease.size() == 0 && lease.info().first_sample == 0 &&
            lease.info().end_sample == 0, "no partial lease published");
    require(history.credit_stats().outstanding_count == 0, "aborted chunked request returns credit");
}

struct Hook {
    std::function<void(std::size_t)> action;
    std::size_t calls = 0;
    static void run(void* context, std::size_t copied) {
        auto& hook = *static_cast<Hook*>(context);
        ++hook.calls;
        hook.action(copied);
    }
};

ChunkCopyOptions with_hook(std::size_t chunk_bytes, Hook& hook) {
    ChunkCopyOptions options;
    options.chunk_bytes = chunk_bytes;
    options.test_after_chunk = &Hook::run;
    options.test_context = &hook;
    return options;
}

void fill(CreditHistory& history, const Stream& stream, std::uint64_t first, std::size_t count) {
    require(history.begin_epoch(stream) == Status::Ok, "begin chunked epoch");
    const auto data = data_for(first, count, stream);
    require(history.append(stream, first, data.data(), data.size()) == Status::Ok, "fill chunked history");
}

void exact_copies_and_whole_sample_chunks() {
    for (const auto bps : {2U, 8U}) {
        const auto stream = source(bps);
        CreditHistory history({2048, 1024, 2, 4096});
        require(history.begin_epoch(stream) == Status::Ok, "parity initial epoch");
        std::uint64_t next = 50;
        for (unsigned step = 0; step < 100; ++step) {
            const auto count = 1U + (step * 37U) % 300U;
            const auto data = data_for(next, count, stream);
            const auto append = history.append(stream, next, data.data(), data.size());
            require(append == (data.size() > 2048 ? Status::Truncated : Status::Ok), "chunked parity append status");
            next += count;
            const auto state = history.state();
            const auto samples = std::min<std::size_t>(state.retained_bytes, 1024) / bps;
            const auto first = state.end_sample - samples;
            const auto baseline = history.snapshot(stream, first, samples);
            check(baseline, stream, first, samples);
            for (const auto chunk : {std::size_t{bps}, std::size_t{bps + 1U}, std::size_t{3U * bps - 1U},
                                     std::size_t{64 * 1024}, std::size_t{256 * 1024},
                                     std::numeric_limits<std::size_t>::max()}) {
                std::size_t progress = 0;
                const auto rounded = chunk - chunk % bps;
                Hook hook{[&](std::size_t copied) {
                    require(copied > progress && copied - progress <= rounded && copied % bps == 0,
                            "whole-sample bounded chunk progress");
                    progress = copied;
                    // Reentrant getters prove this interleaving hook holds neither mutex.
                    require(history.state().stream.epoch == stream.epoch, "hook runs outside ring lock");
                    require(history.credit_stats().outstanding_count == 2, "hook runs outside pool lock");
                }};
                const auto options = with_hook(chunk, hook);
                auto candidate = history.snapshot_chunked(stream, first, samples, options);
                check(candidate, stream, first, samples);
                require(candidate.size() == baseline.size() &&
                        std::equal(baseline.data(), baseline.data() + baseline.size(), candidate.data()), "whole/chunked equality");
                require(hook.calls == (candidate.size() - 1) / rounded, "hook runs between chunks only");
            }
        }
    }
}

void cancel_deadline_and_failure_paths() {
    const auto stream = source();
    CreditHistory history({128, 64, 1, 192});
    fill(history, stream, 0, 32);
    std::atomic<bool> cancelled{true};
    ChunkCopyOptions options;
    options.cancelled = &cancelled;
    check_error(history.snapshot_chunked(stream, 0, 16, options), Status::Cancelled, history);
    cancelled = false;
    options.deadline = std::chrono::steady_clock::time_point::min();
    check_error(history.snapshot_chunked(stream, 0, 16, options), Status::DeadlineExpired, history);
    options.deadline = std::chrono::steady_clock::time_point::max();
    options.chunk_bytes = 1;
    check_error(history.snapshot_chunked(stream, 0, 16, options), Status::InvalidArgument, history);
    options.chunk_bytes = 8;
    check_error(history.snapshot_chunked(stream, 0, 33, options), Status::OutputTooSmall, history);
    check_error(history.snapshot_chunked(stream, 0, 0, options), Status::InvalidArgument, history);
    check_error(history.snapshot_chunked(stream, std::numeric_limits<std::uint64_t>::max(), 1, options),
                Status::ArithmeticOverflow, history);
    check_error(history.snapshot_chunked(stream, 32, 1, options), Status::NotRetained, history);
    auto wrong = stream; ++wrong.epoch;
    check_error(history.snapshot_chunked(wrong, 0, 16, options), Status::EpochMismatch, history);

    Hook cancel_hook{[&](std::size_t copied) { require(copied == 8, "cancel at first boundary"); cancelled = true; }};
    options = with_hook(8, cancel_hook);
    options.cancelled = &cancelled;
    check_error(history.snapshot_chunked(stream, 0, 16, options), Status::Cancelled, history);
    require(cancel_hook.calls == 1, "cancellation stops before another chunk");
    cancelled = false;
    Hook deadline_hook{[&](std::size_t copied) {
        require(copied == 8, "deadline at first boundary");
        // Deterministic test-only update on this same thread; no sleep or clock race.
        options.deadline = std::chrono::steady_clock::time_point::min();
    }};
    options = with_hook(8, deadline_hook);
    check_error(history.snapshot_chunked(stream, 0, 16, options), Status::DeadlineExpired, history);
    require(deadline_hook.calls == 1, "deadline stops before another chunk");

    struct TestStop {};
    Hook throwing{[](std::size_t) { throw TestStop{}; }};
    options = with_hook(8, throwing);
    bool caught = false;
    try { auto lease = history.snapshot_chunked(stream, 0, 16, options); }
    catch (const TestStop&) { caught = true; }
    require(caught && history.credit_stats().outstanding_count == 0, "hook exception safely releases credit");
    options = {};
    auto held = history.snapshot_chunked(stream, 0, 16, options);
    check(held, stream, 0, 16);
    auto busy = history.snapshot_chunked(stream, 0, 16, options);
    require(busy.status() == Status::Busy && busy.data() == nullptr && busy.size() == 0, "exhausted credits do not wait");
    require(history.credit_stats().outstanding_count == 1, "busy attempt cannot steal held credit");
    held.reset();
    auto reused = history.snapshot_chunked(stream, 0, 16, options);
    check(reused, stream, 0, 16);
}

void retune_overwrite_gap_and_safe_append() {
    const auto stream = source();
    for (unsigned change = 0; change < 3; ++change) {
        CreditHistory history({128, 64, 1, 192});
        fill(history, stream, 0, 32);
        Hook hook{[&](std::size_t copied) {
            require(copied == 8, "retune between first and second chunk");
            auto next = stream; ++next.epoch;
            if (change == 0) next.center_frequency_hz += 12500;
            if (change == 1) next.sample_rate_hz /= 2;
            if (change == 2) next.bytes_per_complex_sample = 8;
            require(history.begin_epoch(next) == Status::Ok, "interleaved source change");
            const auto data = data_for(1000, 8, next);
            require(history.append(next, 1000, data.data(), data.size()) == Status::Ok, "new epoch bytes after retune");
        }};
        const auto options = with_hook(8, hook);
        check_error(history.snapshot_chunked(stream, 0, 16, options), Status::EpochMismatch, history);
        require(hook.calls == 1, "new epoch never contributes to old snapshot");
    }
    {
        CreditHistory history({128, 64, 1, 192});
        fill(history, stream, 0, 32);
        Hook hook{[&](std::size_t) {
            auto other = stream; ++other.stream_id;
            require(history.begin_epoch(other) == Status::Ok, "explicit replacement to different stream");
            // Explicit replacement permits this caller ID reuse; the private
            // reset generation must still reject an in-progress stale copy.
            require(history.begin_epoch(stream) == Status::Ok, "explicit replacement back to original IDs");
            const auto bytes = data_for(0, 32, stream);
            require(history.append(stream, 0, bytes.data(), bytes.size()) == Status::Ok, "reused-ID capture data");
        }};
        const auto options = with_hook(8, hook);
        check_error(history.snapshot_chunked(stream, 0, 16, options), Status::EpochMismatch, history);
    }
    {
        CreditHistory history({64, 64, 1, 128});
        fill(history, stream, 0, 32);
        Hook hook{[&](std::size_t copied) {
            require(copied == 8, "overwrite after one copied chunk");
            const auto data = data_for(32, 4, stream);
            require(history.append(stream, 32, data.data(), data.size()) == Status::Ok, "overwrite already copied prefix");
        }};
        const auto options = with_hook(8, hook);
        check_error(history.snapshot_chunked(stream, 0, 16, options), Status::NotRetained, history);
        require(history.state().first_sample == 4, "remaining requested suffix still existed when full-range check rejected");
    }
    {
        CreditHistory history({128, 64, 1, 192});
        fill(history, stream, 0, 32);
        Hook hook{[&](std::size_t) {
            const auto data = data_for(33, 4, stream);
            require(history.append(stream, 33, data.data(), data.size()) == Status::Discontinuity, "gap interleaving");
        }};
        const auto options = with_hook(8, hook);
        check_error(history.snapshot_chunked(stream, 0, 16, options), Status::Discontinuity, history);
    }
    {
        CreditHistory history({64, 64, 1, 128});
        fill(history, stream, 0, 32);
        Hook hook{[&](std::size_t) {
            const auto data = data_for(32, 4, stream);
            require(history.append(stream, 32, data.data(), data.size()) == Status::Ok, "safe append moves ring head");
        }};
        const auto options = with_hook(8, hook);
        auto lease = history.snapshot_chunked(stream, 8, 8, options);
        check(lease, stream, 8, 8);
        require(hook.calls == 1 && history.state().first_sample == 4, "head movement preserves fully retained interval");
    }
}

void caller_buffer_and_service_lifetime() {
    const auto stream = source();
    History history(64);
    require(history.begin_epoch(stream) == Status::Ok, "caller-buffer epoch");
    const auto input = data_for(0, 16, stream);
    require(history.append(stream, 0, input.data(), input.size()) == Status::Ok, "caller-buffer input");
    std::vector<std::uint8_t> output(32, 0xCD);
    std::atomic<bool> cancelled{false};
    Hook hook{[&](std::size_t copied) { require(copied == 8, "private partial copy size"); cancelled = true; }};
    auto options = with_hook(8, hook);
    options.cancelled = &cancelled;
    const auto partial = history.snapshot_chunked_into(stream, 0, 16, output.data(), output.size(), options);
    require(partial.status == Status::Cancelled && partial.byte_count == 0 && partial.first_sample == 0 &&
            partial.end_sample == 0, "partial caller storage has no valid result interval");
    require(std::equal(input.begin(), input.begin() + 8, output.begin()) &&
            std::all_of(output.begin() + 8, output.end(), [](std::uint8_t value) { return value == 0xCD; }),
            "partial private bytes are never implicitly zero-filled or labeled complete");

    SnapshotLease survivor;
    {
        auto owner = std::make_unique<CreditHistory>(CreditConfig{64, 64, 1, 128});
        fill(*owner, stream, 0, 16);
        options = {}; options.chunk_bytes = 8;
        survivor = owner->snapshot_chunked(stream, 0, 16, options);
        check(survivor, stream, 0, 16);
        owner.reset();
        check(survivor, stream, 0, 16);
    }
    survivor.reset();
}
} // namespace

int main() {
    try {
        exact_copies_and_whole_sample_chunks();
        cancel_deadline_and_failure_paths();
        retune_overwrite_gap_and_safe_append();
        caller_buffer_and_service_lifetime();
        std::cout << "IQ chunked contract passed: 1200 exact-copy pairs, bounded chunks, cancellation/deadline, retune/gap/overwrite, credits and lifetime.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "IQ chunked history failure: " << error.what() << '\n';
        return 1;
    }
}
