// SPDX-License-Identifier: GPL-3.0-or-later
#include "credit_history.h"

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <exception>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <thread>
#include <type_traits>
#include <utility>
#include <vector>

using namespace xerax::experiment;

static_assert(!std::is_copy_constructible_v<SnapshotLease> && !std::is_copy_assignable_v<SnapshotLease>);
static_assert(std::is_nothrow_move_constructible_v<SnapshotLease> && std::is_nothrow_move_assignable_v<SnapshotLease>);

namespace {
void require(bool yes, const char* message) {
    if (!yes) throw std::runtime_error(message);
}

Stream source(std::uint32_t bps = 2, std::uint64_t epoch = 1) {
    return {73, epoch, 3072000, 451100000, bps};
}

std::vector<std::uint8_t> data_for(std::uint64_t first, std::size_t samples, const Stream& s) {
    std::vector<std::uint8_t> bytes(samples * s.bytes_per_complex_sample);
    for (std::size_t sample = 0; sample < samples; ++sample)
        for (std::size_t byte = 0; byte < s.bytes_per_complex_sample; ++byte)
            bytes[sample * s.bytes_per_complex_sample + byte] = static_cast<std::uint8_t>(
                (((first + sample) % 251) * 19 + byte * 31 + (s.epoch % 251) * 7) % 251);
    return bytes;
}

void check(const SnapshotLease& lease, const Stream& s, std::uint64_t first, std::size_t count) {
    require(lease.status() == Status::Ok && static_cast<bool>(lease), "lease success");
    const auto& info = lease.info();
    require(info.first_sample == first && info.end_sample == first + count, "lease exact interval");
    require(info.stream.stream_id == s.stream_id && info.stream.epoch == s.epoch &&
            info.stream.sample_rate_hz == s.sample_rate_hz &&
            info.stream.center_frequency_hz == s.center_frequency_hz &&
            info.stream.bytes_per_complex_sample == s.bytes_per_complex_sample, "lease exact metadata");
    const auto expected = data_for(first, count, s);
    require(lease.data() != nullptr && lease.size() == expected.size(), "lease byte count");
    require(std::equal(expected.begin(), expected.end(), lease.data()), "lease exact bytes");
}

void check_error(const SnapshotLease& lease, Status status) {
    require(lease.status() == status && !static_cast<bool>(lease), "expected lease error");
    require(lease.data() == nullptr && lease.size() == 0, "failed lease exposes no payload");
}

void budget_and_exhaustion() {
    const std::array<CreditConfig, 5> invalid{{
        {0, 16, 2, 64}, {32, 0, 2, 64}, {32, 16, 0, 64}, {32, 16, 2, 0},
        {32, 16, 2, 63}
    }};
    for (const auto& config : invalid) {
        bool threw = false;
        try { CreditHistory h(config); }
        catch (const std::invalid_argument&) { threw = true; }
        catch (const std::length_error&) { threw = true; }
        require(threw, "invalid budget rejected before payload allocation");
    }
    const auto maximum = std::numeric_limits<std::size_t>::max();
    bool overflow_rejected = false;
    try { CreditHistory h({32, maximum, 2, maximum}); }
    catch (const std::length_error&) { overflow_rejected = true; }
    require(overflow_rejected, "slot multiplication overflow rejected before allocation");
    bool ring_rejected = false;
    try { CreditHistory h({maximum, 1, 1, 32}); }
    catch (const std::length_error&) { ring_rejected = true; }
    require(ring_rejected, "oversized ring rejected before allocation");

    CreditHistory h({64, 32, 2, 128});
    auto s = source();
    require(h.begin_epoch(s) == Status::Ok, "credit epoch");
    const auto input = data_for(100, 32, s);
    require(h.append(s, 100, input.data(), input.size()) == Status::Ok, "credit append");
    const auto initial = h.credit_stats();
    require(initial.ring_capacity_bytes == 64 && initial.snapshot_capacity_bytes == 32 &&
            initial.slot_count == 2 && initial.total_payload_bytes == 128 &&
            initial.preallocated_snapshot_bytes == 64 && initial.payload_budget_bytes == 128 &&
            initial.outstanding_count == 0 && initial.outstanding_reserved_bytes == 0, "exact payload budget");
    auto a = h.snapshot(s, 100, 8), b = h.snapshot(s, 108, 16);
    check(a, s, 100, 8); check(b, s, 108, 16);
    require(a.data() != b.data(), "simultaneous leases have separate preallocated slots");
    const auto* first_slot = a.data();
    const auto* second_slot = b.data();
    auto full = h.credit_stats();
    require(full.outstanding_count == 2 && full.outstanding_reserved_bytes == 64, "credits reserve slot capacity");
    check_error(h.snapshot(s, 110, 1), Status::Busy);
    a.reset();
    require(h.credit_stats().outstanding_count == 1, "explicit release returns credit");
    auto reused = h.snapshot(s, 116, 8);
    require(reused.data() == first_slot, "released slot reused without new payload allocation");
    check(reused, s, 116, 8);
    auto moved = std::move(reused);
    require(reused.data() == nullptr && reused.size() == 0, "move source is empty");
    check(moved, s, 116, 8);
    require(h.credit_stats().outstanding_count == 2, "move construction does not duplicate credit");
    b = std::move(moved); // Releases slot two, then takes slot one.
    require(moved.data() == nullptr && moved.size() == 0, "move assignment source is empty");
    require(h.credit_stats().outstanding_count == 1, "move assignment releases previous credit");
    check(b, s, 116, 8);
    auto another = h.snapshot(s, 124, 8);
    require(another.data() == second_slot, "move-released slot is reusable");
    // Explicitly exercise self move through an alias without compiler self-move warnings.
    auto* same = &another; another = std::move(*same);
    check(another, s, 124, 8);
    another.reset(); b.reset();
    require(h.credit_stats().outstanding_count == 0, "all credits returned once");
    for (unsigned request = 0; request < 500; ++request) {
        auto lease = h.snapshot(s, 100, 8);
        require(lease.data() == first_slot, "bounded pool survives repeated lease reuse");
    }
    require(h.credit_stats().total_payload_bytes == 128 && h.credit_stats().outstanding_count == 0,
            "request count cannot grow pool payload storage");
    struct ConsumerCancelled {};
    try {
        auto lease = h.snapshot(s, 100, 8);
        check(lease, s, 100, 8);
        throw ConsumerCancelled{};
    } catch (const ConsumerCancelled&) {}
    require(h.credit_stats().outstanding_count == 0, "consumer exception returns credit");
}

void lifetime_and_errors() {
    auto s = source(8);
    SnapshotLease survivor;
    {
        auto h = std::make_unique<CreditHistory>(CreditConfig{128, 64, 1, 192});
        require(h->begin_epoch(s) == Status::Ok, "lifetime epoch");
        const auto input = data_for(44, 8, s);
        require(h->append(s, 44, input.data(), input.size()) == Status::Ok, "lifetime append");
        survivor = h->snapshot(s, 44, 8);
        check(survivor, s, 44, 8);
        h.reset();
        check(survivor, s, 44, 8); // No pointer or callback into a destroyed History.
    }
    auto moved_survivor = std::move(survivor);
    check(moved_survivor, s, 44, 8);
    moved_survivor.reset(); // Last pool owner may disappear here.
    moved_survivor.reset(); // Idempotent, never double-returns a credit.

    CreditHistory h({128, 32, 1, 160});
    check_error(h.snapshot(s, 0, 1), Status::NoEpoch);
    require(h.credit_stats().outstanding_count == 0, "missing-epoch error returns credit");
    require(h.begin_epoch(s) == Status::Ok, "errors epoch");
    auto input = data_for(20, 16, s);
    require(h.append(s, 20, input.data(), input.size()) == Status::Ok, "errors append");
    check_error(h.snapshot(s, 20, 5), Status::OutputTooSmall);
    check_error(h.snapshot(s, 19, 1), Status::NotRetained);
    check_error(h.snapshot(s, 20, 0), Status::InvalidArgument);
    check_error(h.snapshot(s, std::numeric_limits<std::uint64_t>::max(), 1), Status::ArithmeticOverflow);
    auto wrong = s; wrong.epoch++;
    check_error(h.snapshot(wrong, 20, 1), Status::EpochMismatch);
    wrong = s; wrong.sample_rate_hz /= 2;
    check_error(h.snapshot(wrong, 20, 1), Status::MetadataMismatch);
    require(h.credit_stats().outstanding_count == 0, "all request errors return credits");
    auto old = h.snapshot(s, 20, 4);
    check(old, s, 20, 4);
    require(h.append(s, 37, input.data(), input.size()) == Status::Discontinuity, "gap still invalidates ring");
    check(old, s, 20, 4); // An owned historical snapshot remains historical, not relabeled.
    old.reset();
    check_error(h.snapshot(s, 20, 1), Status::Discontinuity);
    s.epoch++; s.bytes_per_complex_sample = 2; s.center_frequency_hz += 12500;
    require(h.begin_epoch(s) == Status::Ok, "new retune format epoch");
    input = data_for(900, 16, s);
    require(h.append(s, 900, input.data(), input.size()) == Status::Ok, "new epoch append");
    auto current = h.snapshot(s, 900, 16);
    check(current, s, 900, 16);
}

void parity_and_output_contract() {
    for (const auto bps : {2U, 8U}) {
        auto s = source(bps);
        History baseline(127);
        CreditHistory candidate({127, 127, 1, 254});
        require(baseline.begin_epoch(s) == Status::Ok && candidate.begin_epoch(s) == Status::Ok, "parity epochs");
        std::uint64_t next = 70;
        for (unsigned step = 0; step < 800; ++step) {
            const std::size_t count = 1 + (step * 19U) % 131U;
            const auto input = data_for(next, count, s);
            require(baseline.append(s, next, input.data(), input.size()) ==
                    candidate.append(s, next, input.data(), input.size()), "credit variant preserves append status");
            next += count;
            const auto state = baseline.state();
            const auto samples = static_cast<std::size_t>(state.end_sample - state.first_sample);
            const auto original = baseline.snapshot(s, state.first_sample, samples);
            auto lease = candidate.snapshot(s, state.first_sample, samples);
            check(lease, s, state.first_sample, samples);
            require(original.status == lease.status() && original.bytes.size() == lease.size() &&
                    std::equal(original.bytes.begin(), original.bytes.end(), lease.data()), "baseline/lease parity");
        }
        std::array<std::uint8_t, 128> output{}; output.fill(0xDA);
        const auto untouched = output;
        const auto state = baseline.state();
        auto status = baseline.snapshot_into(s, state.first_sample, 1, output.data(), bps - 1);
        require(status.status == Status::OutputTooSmall && output == untouched, "short destination remains unchanged");
        status = baseline.snapshot_into(s, state.end_sample, 1, output.data(), output.size());
        require(status.status == Status::NotRetained && output == untouched, "missing request leaves destination unchanged");
        status = baseline.snapshot_into(s, state.first_sample, 1, nullptr, output.size());
        require(status.status == Status::InvalidArgument, "null destination rejected");
        status = baseline.snapshot_into(s, state.first_sample, 1, output.data(), output.size());
        const auto expected = data_for(state.first_sample, 1, s);
        require(status.status == Status::Ok && status.byte_count == bps &&
                std::equal(expected.begin(), expected.end(), output.begin()), "caller-buffer exact copy");
        require(std::equal(output.begin() + bps, output.end(), untouched.begin() + bps), "copy respects exact destination extent");
    }
}

void concurrent_leases_and_retunes() {
    CreditHistory h({4096, 1024, 2, 6144});
    const auto initial = source();
    require(h.begin_epoch(initial) == Status::Ok, "concurrent credit epoch");
    const auto input = data_for(0, 1024, initial);
    require(h.append(initial, 0, input.data(), input.size()) == Status::Ok, "concurrent credit input");
    std::atomic<unsigned> ready{0};
    std::atomic<bool> release{false};
    std::array<std::exception_ptr, 2> errors{};
    auto reader = [&](std::size_t which) {
        bool announced = false;
        try {
            const auto first = static_cast<std::uint64_t>(which) * 128;
            auto lease = h.snapshot(initial, first, 128);
            check(lease, initial, first, 128);
            ++ready; announced = true;
            while (!release.load()) {
                check(lease, initial, first, 128);
                std::this_thread::yield();
            }
            check(lease, initial, first, 128);
        } catch (...) { errors[which] = std::current_exception(); if (!announced) ++ready; }
    };
    std::thread one(reader, std::size_t{0}), two(reader, std::size_t{1});
    Stream current = initial;
    try {
        const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
        while (ready.load() != 2) {
            require(std::chrono::steady_clock::now() < deadline, "concurrent readers become ready");
            std::this_thread::yield();
        }
        require(h.credit_stats().outstanding_count == 2, "concurrent readers consume two credits");
        check_error(h.snapshot(initial, 0, 1), Status::Busy);
        for (unsigned epoch = 2; epoch <= 100; ++epoch) {
            current.epoch = epoch;
            current.center_frequency_hz += 12500;
            current.bytes_per_complex_sample = epoch % 2 == 0 ? 8U : 2U;
            require(h.begin_epoch(current) == Status::Ok, "producer retune while old leases exist");
            const auto next = data_for(5000, 64, current);
            require(h.append(current, 5000, next.data(), next.size()) == Status::Ok, "producer append while old leases exist");
            check_error(h.snapshot(current, 5000, 1), Status::Busy);
        }
        release = true;
    } catch (...) {
        release = true; one.join(); two.join(); throw;
    }
    one.join(); two.join();
    for (const auto& error : errors) if (error) std::rethrow_exception(error);
    require(h.credit_stats().outstanding_count == 0, "concurrent reader destruction returns credits");
    auto after = h.snapshot(current, 5000, 64);
    check(after, current, 5000, 64);
}
} // namespace

int main() {
    try {
        budget_and_exhaustion();
        lifetime_and_errors();
        parity_and_output_contract();
        concurrent_leases_and_retunes();
        std::cout << "IQ credit history passed: budget, exhaustion, moves, lifetime, errors, 1600 parity steps, concurrent retunes.\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "IQ credit history failure: " << e.what() << '\n';
        return 1;
    }
}
