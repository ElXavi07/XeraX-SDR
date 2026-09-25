// SPDX-License-Identifier: GPL-3.0-or-later
// Independent correctness checks for the synchronous single-owner core only.
// No asynchronous coordinator, real SDR source or performance claim is tested.

#include "immutable_slabs.h"

#include <algorithm>
#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <deque>
#include <exception>
#include <iostream>
#include <limits>
#include <memory>
#include <new>
#include <stdexcept>
#include <string>
#include <thread>
#include <type_traits>
#include <utility>
#include <vector>
#ifdef _WIN32
#include <malloc.h>
#endif

// Count global C++ allocation calls only during tightly scoped library calls.
// This is additional evidence alongside the payload ledger, not a whole-process
// resident-memory measurement or interception of an arbitrary C allocator.
namespace allocation_probe {
thread_local bool active = false;
thread_local std::size_t calls = 0;
thread_local std::size_t requested = 0;
void record(std::size_t size) noexcept {
    if (active) { ++calls; requested += size; }
}
}

#if defined(_MSC_VER)
#define PROBE_NOINLINE __declspec(noinline)
#elif defined(__GNUC__)
#define PROBE_NOINLINE __attribute__((noinline))
#else
#define PROBE_NOINLINE
#endif

// Keep replacement allocation functions as call boundaries. Inlining a custom
// malloc/free-backed new/delete pair produces misleading GCC mismatch warnings.
PROBE_NOINLINE void* operator new(std::size_t size) {
    allocation_probe::record(size);
    if (void* result = std::malloc(size ? size : 1)) return result;
    throw std::bad_alloc();
}
PROBE_NOINLINE void* operator new[](std::size_t size) { return ::operator new(size); }
PROBE_NOINLINE void operator delete(void* pointer) noexcept { std::free(pointer); }
PROBE_NOINLINE void operator delete[](void* pointer) noexcept { ::operator delete(pointer); }
PROBE_NOINLINE void operator delete(void* pointer, std::size_t) noexcept { ::operator delete(pointer); }
PROBE_NOINLINE void operator delete[](void* pointer, std::size_t) noexcept { ::operator delete(pointer); }
PROBE_NOINLINE void* operator new(std::size_t size, std::align_val_t alignment) {
    allocation_probe::record(size);
    void* result = nullptr;
#ifdef _WIN32
    result = _aligned_malloc(size ? size : 1, static_cast<std::size_t>(alignment));
#else
    if (posix_memalign(&result, static_cast<std::size_t>(alignment), size ? size : 1) != 0) result = nullptr;
#endif
    if (!result) throw std::bad_alloc();
    return result;
}
PROBE_NOINLINE void* operator new[](std::size_t size, std::align_val_t alignment) { return ::operator new(size, alignment); }
PROBE_NOINLINE void operator delete(void* pointer, std::align_val_t) noexcept {
#ifdef _WIN32
    _aligned_free(pointer);
#else
    std::free(pointer);
#endif
}
PROBE_NOINLINE void operator delete[](void* pointer, std::align_val_t alignment) noexcept { ::operator delete(pointer, alignment); }
PROBE_NOINLINE void operator delete(void* pointer, std::size_t, std::align_val_t alignment) noexcept { ::operator delete(pointer, alignment); }
PROBE_NOINLINE void operator delete[](void* pointer, std::size_t, std::align_val_t alignment) noexcept { ::operator delete(pointer, alignment); }
#undef PROBE_NOINLINE

namespace {
using namespace xerax::experiment::slabs;
std::atomic<std::size_t> assertions{0};
std::atomic<std::size_t> verified_bytes{0};
std::size_t groups = 0;
// Captured on the owner thread; these are allocator request sizes reported by
// the contract ledger, not operating-system resident-memory measurements.
std::size_t observed_arena_metadata = 0;
std::size_t observed_budget_control = 0;

static_assert(!std::is_copy_constructible_v<Lease> && !std::is_copy_assignable_v<Lease>);
static_assert(std::is_nothrow_move_constructible_v<Lease> && std::is_nothrow_move_assignable_v<Lease>);

void require(bool condition, const char* message) {
    ++assertions;
    if (!condition) throw std::runtime_error(message);
}

template<typename Operation>
void no_allocation(Operation&& operation) {
    allocation_probe::calls = allocation_probe::requested = 0;
    allocation_probe::active = true;
    try { operation(); }
    catch (...) { allocation_probe::active = false; throw; }
    allocation_probe::active = false;
    require(allocation_probe::calls == 0 && allocation_probe::requested == 0,
            "library streaming/lease operation performs no C++ allocation");
}

// The receiver stores opaque bytes. This oracle is deliberately independent of
// its slab layout, retention index, snapshot implementation and generations.
// Capture nonce distinguishes A -> B -> A replacements reusing public IDs.
std::uint64_t mix(std::uint64_t x) {
    x ^= x >> 30U;
    x *= UINT64_C(0xbf58476d1ce4e5b9);
    x ^= x >> 27U;
    x *= UINT64_C(0x94d049bb133111eb);
    return x ^ (x >> 31U);
}

std::uint8_t source_byte(std::uint64_t sample, unsigned component,
                         std::uint64_t stream_id, std::uint64_t epoch,
                         std::uint64_t nonce) {
    const auto key = mix(stream_id) ^ mix(epoch + UINT64_C(0x512ca04f)) ^
                     mix(nonce + UINT64_C(0x971caf65));
    return static_cast<std::uint8_t>(mix(sample ^ key) >> (component * 8U));
}

std::vector<std::uint8_t> source_bytes(std::uint64_t first, std::size_t count,
                                      unsigned width, std::uint64_t stream_id,
                                      std::uint64_t epoch, std::uint64_t nonce) {
    std::vector<std::uint8_t> result(count * width);
    for (std::size_t i = 0; i < count; ++i)
        for (unsigned component = 0; component < width; ++component)
            result[i * width + component] = source_byte(first + i, component, stream_id, epoch, nonce);
    return result;
}

// Simple sequential byte-deque model; it does not use slab sizes or library
// snapshot results. Feed only accepted continuous source bytes into the model.
class ByteModel {
public:
    ByteModel(std::size_t capacity, unsigned width) : capacity_(capacity - capacity % width), width_(width) {}

    void append(std::uint64_t first, const std::vector<std::uint8_t>& input) {
        require(input.size() % width_ == 0, "model receives whole source samples");
        require(bytes_.empty() || first == end_, "model receives continuous source samples");
        bytes_.insert(bytes_.end(), input.begin(), input.end());
        end_ = first + input.size() / width_;
        while (bytes_.size() > capacity_) bytes_.pop_front();
        first_ = end_ - bytes_.size() / width_;
    }

    std::vector<std::uint8_t> interval(std::uint64_t first, std::size_t count) const {
        require(first >= first_ && first <= end_ && count <= end_ - first, "model interval retained");
        const auto offset = static_cast<std::size_t>(first - first_) * width_;
        const auto begin = bytes_.begin() + static_cast<std::ptrdiff_t>(offset);
        return {begin, begin + static_cast<std::ptrdiff_t>(count * width_)};
    }

    std::uint64_t first() const { return first_; }
    std::uint64_t end() const { return end_; }
    std::size_t bytes() const { return bytes_.size(); }

private:
    std::size_t capacity_;
    unsigned width_;
    std::uint64_t first_ = 0, end_ = 0;
    std::deque<std::uint8_t> bytes_;
};

unsigned width_of(Format format) { return format == Format::CU8 ? 2U : 8U; }

Stream source(Format format = Format::CF32LE, std::uint64_t epoch = 1) {
    return {87, epoch, 3072000, 451100000, format};
}

Request request(History& history, const Stream& stream, std::uint64_t first, std::uint64_t count) {
    const auto state = history.state();
    return {stream, state.generation, state.pool_id, first, count};
}

Lease snapshot(History& history, const Request& req) {
    Lease result;
    no_allocation([&] { result = history.snapshot(req); });
    return result;
}

Lease live(History& history, const Request& req) {
    Lease result;
    no_allocation([&] { result = history.live(req); });
    return result;
}

void release(History& history, Lease& lease) {
    no_allocation([&] { lease.reset(); history.reclaim(); });
}

Status append_bytes(History& history, const Stream& stream, std::uint64_t first,
                    const std::vector<std::uint8_t>& bytes) {
    Status result = Status::NoEpoch;
    no_allocation([&] { result = history.append(stream, first, bytes.data(), bytes.size()); });
    return result;
}

void append_generated(History& history, const Stream& stream, std::uint64_t first,
                       std::size_t count, std::uint64_t nonce = 1) {
    auto bytes = source_bytes(first, count, width_of(stream.format), stream.stream_id, stream.epoch, nonce);
    require(append_bytes(history, stream, first, bytes) == Status::Ok, "generated continuous append accepted");
    // Caller memory is deliberately overwritten after append, proving snapshots
    // do not accidentally alias a still-valid input vector.
    std::fill(bytes.begin(), bytes.end(), 0xA6);
}

void check_budget(const History& history, const ProcessBudget& budget) {
    const auto state = history.state();
    const auto ledger = budget.stats();
    observed_arena_metadata = ledger.metadata_bytes;
    observed_budget_control = ledger.budget_control_bytes;
    require(state.payload_bytes == 15728640 && state.payload_bytes == kPayloadBytes,
            "exact declared15MiB arena including ingress scratch");
    require(state.metadata_bytes > 0 && state.metadata_bytes <= kMetadataLimit,
            "actual metadata stays within explicit cap");
    require(state.metadata_bytes == ledger.metadata_bytes + ledger.budget_control_bytes,
            "single arena state includes separately charged budget-control bytes");
    require(ledger.arenas == 1 && ledger.payload_bytes == kPayloadBytes, "single arena process budget accounting");
    require(ledger.metadata_bytes + ledger.budget_control_bytes <= ledger.metadata_limit,
            "arena and process-control metadata both fit ledger");
    require(state.history_slabs <= 138 && state.retained_bytes <= 8388608, "exact useful history caps");
    require(state.snapshot_pinned_slabs <= 101 && state.live_pinned_slabs <= 8,
            "separate physical snapshot/live pin caps");
    require(state.outstanding_live_leases <= 8 && state.free_slabs <= 252,
            "fixed records and reusable slab count");
    require(state.filling_bytes < kSlabBytes, "full slabs publish immediately");
}

void check_lease(const Lease& lease, const Stream& stream, std::uint64_t first,
                  std::size_t count, std::uint64_t nonce = 1, std::size_t span_limit = 101) {
    require(lease.status() == Status::Ok && static_cast<bool>(lease), "lease reports successful ownership");
    const auto& info = lease.info();
    const auto width = width_of(stream.format);
    require(info.stream.stream_id == stream.stream_id && info.stream.epoch == stream.epoch &&
            info.stream.sample_rate_hz == stream.sample_rate_hz &&
            info.stream.center_frequency_hz == stream.center_frequency_hz && info.stream.format == stream.format,
            "every lease source metadata field is exact");
    require(info.first_sample == first && info.end_sample == first + count && info.byte_count == count * width,
            "lease exposes exactly requested source interval and byte count");
    require(info.pool_id != 0 && info.generation != 0 && info.lease_generation != 0,
            "lease has explicit pool/reset/lease identity");
    require(lease.span_count() > 0 && lease.span_count() <= span_limit, "bounded nonempty span list");
    std::array<bool, 252> seen{};
    std::uint64_t cursor = first;
    std::size_t total = 0;
    for (std::size_t n = 0; n < lease.span_count(); ++n) {
        const auto& span = lease.span(n);
        require(span.data != nullptr && span.byte_count > 0 && span.byte_count <= kSlabBytes &&
                span.byte_count % width == 0, "span contains complete samples within one slab");
        require(span.first_sample == cursor && span.slab_index < seen.size() && span.slab_incarnation > 0,
                "span has exact continuous source index and bounded identity");
        require(!seen[span.slab_index], "one source interval cannot duplicate a physical slab");
        seen[span.slab_index] = true;
        for (std::size_t j = 0; j < span.byte_count; ++j) {
            if (span.data[j] != source_byte(cursor + j / width, static_cast<unsigned>(j % width),
                                           stream.stream_id, stream.epoch, nonce))
                throw std::runtime_error("lease byte differs from independent source-index/epoch/nonce oracle");
        }
        cursor += span.byte_count / width;
        total += span.byte_count;
    }
    require(cursor == first + count && total == info.byte_count, "span concatenation has no gap or overlap");
    verified_bytes.fetch_add(total, std::memory_order_relaxed);
}

void check_model_bytes(const Lease& lease, const std::vector<std::uint8_t>& expected) {
    require(lease.status() == Status::Ok && lease.info().byte_count == expected.size(), "model byte length matches");
    std::size_t offset = 0;
    for (std::size_t n = 0; n < lease.span_count(); ++n) {
        const auto& span = lease.span(n);
        require(span.byte_count <= expected.size() - offset, "model span within requested extent");
        require(std::equal(expected.begin() + static_cast<std::ptrdiff_t>(offset),
                           expected.begin() + static_cast<std::ptrdiff_t>(offset + span.byte_count), span.data),
                "lease bytes match independent sequential byte-deque model");
        offset += span.byte_count;
    }
    require(offset == expected.size(), "model interval fully returned");
    verified_bytes.fetch_add(offset, std::memory_order_relaxed);
}

void check_error(const Lease& lease, Status expected) {
    if (lease.status() != expected)
        throw std::runtime_error("lease status expected=" + std::to_string(static_cast<int>(expected)) +
                                 " actual=" + std::to_string(static_cast<int>(lease.status())));
    require(!static_cast<bool>(lease), "specified lease error returns no ownership");
    require(lease.span_count() == 0 && lease.info().byte_count == 0 && lease.info().first_sample == 0 &&
            lease.info().end_sample == 0, "failed lease exposes no payload or successful interval");
}

void unchanged_interval(const State& before, const State& after) {
    require(before.generation == after.generation && before.first_sample == after.first_sample &&
            before.end_sample == after.end_sample && before.accepted_end_sample == after.accepted_end_sample &&
            before.retained_bytes == after.retained_bytes && before.history_slabs == after.history_slabs &&
            before.filling_bytes == after.filling_bytes && before.closed == after.closed &&
            before.requires_new_epoch == after.requires_new_epoch,
            "rejected atomic operation leaves source/history state unchanged");
}

void retention_and_unaligned_snapshots() {
    ++groups;
    for (const auto format : {Format::CU8, Format::CF32LE, Format::CF32BE}) {
        ProcessBudget budget;
        History history(budget);
        const auto stream = source(format);
        const auto width = width_of(format);
        const std::size_t slab_samples = kSlabBytes / width;
        constexpr std::uint64_t start = 107;
        require(history.begin_epoch(stream) == Status::Ok, "retention epoch begins");
        for (std::size_t n = 0; n < 160; ++n)
            append_generated(history, stream, start + n * slab_samples, slab_samples);
        auto state = history.state();
        require(state.retained_bytes == 8388608 && state.first_sample == state.end_sample - 8388608 / width,
                "retains exact8MiB useful source bytes rather than136 rounded slabs");
        require(state.history_slabs == 137 && state.end_sample == start + 160 * slab_samples,
                "aligned frontier has137 physical history slabs");
        const std::size_t quarter_second = 768000;
        const auto first = state.end_sample - quarter_second - 1;
        auto lease = snapshot(history, request(history, stream, first, quarter_second));
        check_lease(lease, stream, first, quarter_second);
        require(lease.span_count() == (format == Format::CU8 ? 26U : 101U),
                "unaligned250ms snapshot charges its partial first and last slabs");
        release(history, lease);
        check_error(snapshot(history, request(history, stream, state.first_sample - 1, 1)), Status::NotRetained);
        auto earliest = snapshot(history, request(history, stream, state.first_sample, 1));
        check_lease(earliest, stream, state.first_sample, 1);
        release(history, earliest);
        // A short final tail makes both ends of exact8MiB retention unaligned.
        append_generated(history, stream, state.end_sample, 1);
        require(history.state().end_sample == state.end_sample && history.state().filling_bytes == width,
                "partial input cannot move published frontier prematurely");
        require(history.seal_tail() == Status::Ok, "final partial tail sealed");
        state = history.state();
        require(state.closed && state.retained_bytes == 8388608 && state.history_slabs == 138,
                "partial final slab requires138 spans without reducing useful retention");
        auto tail = snapshot(history, request(history, stream, state.end_sample - quarter_second, quarter_second));
        check_lease(tail, stream, state.end_sample - quarter_second, quarter_second);
        release(history, tail);
        const auto before = history.state();
        const auto bytes = source_bytes(state.end_sample, 1, width, stream.stream_id, stream.epoch, 1);
        require(append_bytes(history, stream, state.end_sample, bytes) == Status::Closed, "seal permanently closes epoch");
        require(history.seal_tail() == Status::Closed, "second seal cannot fragment the epoch");
        unchanged_interval(before, history.state());
        check_budget(history, budget);
    }
}

void partial_callbacks_against_independent_model() {
    ++groups;
    for (const auto format : {Format::CU8, Format::CF32LE}) {
        ProcessBudget budget;
        History history(budget);
        const auto stream = source(format);
        const auto width = width_of(format);
        const auto slab_samples = kSlabBytes / width;
        ByteModel model(8388608, width);
        require(history.begin_epoch(stream) == Status::Ok, "model epoch begins");
        constexpr std::uint64_t first = 991;
        std::size_t accepted_samples = 0, published_samples = 0;
        std::uint64_t random = UINT64_C(0x0ac719083ab01234);
        for (unsigned step = 0; step < 220; ++step) {
            random = mix(random);
            const std::size_t count = 1 + static_cast<std::size_t>(random % (2 * slab_samples));
            append_generated(history, stream, first + accepted_samples, count, 37);
            accepted_samples += count;
            const auto full_samples = (accepted_samples / slab_samples) * slab_samples;
            if (full_samples != published_samples) {
                const auto bytes = source_bytes(first + published_samples, full_samples - published_samples, width,
                                                 stream.stream_id, stream.epoch, 37);
                model.append(first + published_samples, bytes);
                published_samples = full_samples;
            }
            const auto state = history.state();
            require(state.accepted_end_sample == first + accepted_samples &&
                    state.filling_bytes == (accepted_samples - published_samples) * width,
                    "accepted and unpublished source positions follow independent packing arithmetic");
            if (!published_samples) {
                require(!state.has_samples && state.retained_bytes == 0, "unsealed first slab not retained");
                continue;
            }
            require(state.first_sample == model.first() && state.end_sample == model.end() &&
                    state.retained_bytes == model.bytes(), "state equals byte-deque retention model");
            const auto available = static_cast<std::size_t>(model.end() - model.first());
            const std::size_t count_to_read = std::min<std::size_t>(1 + (random % 4093U), available);
            const auto wanted = model.end() - count_to_read;
            auto lease = snapshot(history, request(history, stream, wanted, count_to_read));
            check_model_bytes(lease, model.interval(wanted, count_to_read));
            check_lease(lease, stream, wanted, count_to_read, 37);
            release(history, lease);
            check_error(snapshot(history, request(history, stream, state.end_sample, 1)), Status::NotRetained);
        }
        const auto remaining = accepted_samples - published_samples;
        if (remaining) model.append(first + published_samples,
            source_bytes(first + published_samples, remaining, width, stream.stream_id, stream.epoch, 37));
        require(history.seal_tail() == Status::Ok, "model partial tail seal");
        const auto state = history.state();
        require(state.end_sample == model.end() && state.first_sample == model.first() &&
                state.retained_bytes == model.bytes() && state.filling_bytes == 0, "sealed state equals model");
        auto lease = snapshot(history, request(history, stream, model.end() - 1000, 1000));
        check_model_bytes(lease, model.interval(model.end() - 1000, 1000));
        release(history, lease);
        check_budget(history, budget);
    }
}

void stalled_snapshot_and_live_credits() {
    ++groups;
    ProcessBudget budget;
    History history(budget);
    const auto stream = source();
    const auto slab_samples = kSlabBytes / 8;
    require(history.begin_epoch(stream) == Status::Ok, "stall epoch begins");
    for (std::size_t n = 0; n < 150; ++n) append_generated(history, stream, n * slab_samples, slab_samples);
    const auto end = history.state().end_sample;
    const auto snapshot_first = end - 768000 - 1;
    auto held = snapshot(history, request(history, stream, snapshot_first, 768000));
    std::array<Lease, 8> live_leases;
    for (std::size_t n = 0; n < live_leases.size(); ++n)
        live_leases[n] = live(history, request(history, stream, end - (n + 1) * slab_samples, 1));
    require(history.state().snapshot_pinned_slabs == 101 && history.state().live_pinned_slabs == 8 &&
            history.state().outstanding_live_leases == 8, "snapshot and live credits charged separately");
    check_error(snapshot(history, request(history, stream, end - 1, 1)), Status::Busy);
    check_error(live(history, request(history, stream, end - 1, 1)), Status::Busy);
    for (std::size_t n = 0; n < 500; ++n) append_generated(history, stream, end + n * slab_samples, slab_samples);
    check_lease(held, stream, snapshot_first, 768000);
    for (std::size_t n = 0; n < live_leases.size(); ++n)
        check_lease(live_leases[n], stream, end - (n + 1) * slab_samples, 1, 1, 8);
    require(history.state().first_sample > end && history.state().retained_bytes == 8388608,
            "live ingestion retains full rolling history through long consumer stalls");
    check_budget(history, budget);
    release(history, held);
    for (auto& lease : live_leases) release(history, lease);
    require(history.state().snapshot_pinned_slabs == 0 && history.state().live_pinned_slabs == 0 &&
            history.state().outstanding_live_leases == 0, "all stalled leases reclaim exactly once");
    auto fresh = snapshot(history, request(history, stream, history.state().end_sample - 768000, 768000));
    check_lease(fresh, stream, history.state().end_sample - 768000, 768000);
    release(history, fresh);
}

void live_physical_claims_are_bounded() {
    ++groups;
    ProcessBudget budget;
    History history(budget);
    const auto stream = source();
    const auto slab_samples = kSlabBytes / 8;
    require(history.begin_epoch(stream) == Status::Ok, "live credit epoch begins");
    append_generated(history, stream, 0, 4 * slab_samples);
    append_generated(history, stream, 4 * slab_samples, 4 * slab_samples);
    append_generated(history, stream, 8 * slab_samples, slab_samples);
    auto a = live(history, request(history, stream, 0, 4 * slab_samples));
    auto b = live(history, request(history, stream, 0, 4 * slab_samples));
    check_lease(a, stream, 0, 4 * slab_samples, 1, 8);
    check_lease(b, stream, 0, 4 * slab_samples, 1, 8);
    require(history.state().live_pinned_slabs == 8, "overlapping live leases each consume their physical claims");
    check_error(live(history, request(history, stream, 4 * slab_samples, 1)), Status::Busy);
    release(history, a);
    auto crossing = live(history, request(history, stream, slab_samples - 1, 2));
    check_lease(crossing, stream, slab_samples - 1, 2, 1, 8);
    require(crossing.span_count() == 2 && history.state().live_pinned_slabs == 6,
            "two-sample straddling live request consumes two whole-slab claims");
    release(history, b); release(history, crossing);
    check_error(live(history, request(history, stream, 0, 8 * slab_samples + 1)), Status::TooLarge);
    check_budget(history, budget);
}

void leases_survive_changes_and_public_identity_reuse() {
    ++groups;
    ProcessBudget budget;
    History history(budget);
    const auto original = source();
    require(history.begin_epoch(original) == Status::Ok, "old source begins");
    append_generated(history, original, 0, kSlabBytes / 8, 5);
    const auto old_request = request(history, original, 0, 100);
    auto held = snapshot(history, old_request);
    auto held_live = live(history, old_request);
    const auto old_generation = held.info().generation;
    auto next = original;
    next.epoch = 2; next.sample_rate_hz = 1536000; next.center_frequency_hz += 12500; next.format = Format::CU8;
    require(history.begin_epoch(next) == Status::Ok, "retune/rate/format transition");
    append_generated(history, next, 400000, kSlabBytes / 2, 6);
    check_lease(held, original, 0, 100, 5);
    check_lease(held_live, original, 0, 100, 5, 8);
    check_error(snapshot(history, request(history, next, 400000, 1)), Status::Busy);
    release(history, held);
    check_error(snapshot(history, old_request), Status::EpochMismatch);
    auto b = next; b.stream_id = 555; b.epoch = 0;
    require(history.begin_epoch(b) == Status::Ok, "explicit source B replacement");
    append_generated(history, b, 0, kSlabBytes / 2, 7);
    require(history.begin_epoch(original) == Status::Ok, "explicit source A public IDs reused");
    append_generated(history, original, 0, kSlabBytes / 8, 8);
    require(history.state().generation > old_generation, "private generation changes through A-B-A");
    check_error(snapshot(history, old_request), Status::EpochMismatch);
    auto replacement = snapshot(history, request(history, original, 0, 100));
    check_lease(replacement, original, 0, 100, 8);
    check_lease(held_live, original, 0, 100, 5, 8);
    release(history, replacement); release(history, held_live);
    check_budget(history, budget);
}

void gaps_metadata_and_rejected_appends() {
    ++groups;
    for (unsigned failure = 0; failure < 4; ++failure) {
        ProcessBudget budget;
        History history(budget);
        auto stream = source();
        require(history.begin_epoch(stream) == Status::Ok, "failure epoch begins");
        const auto count = kSlabBytes / 8;
        append_generated(history, stream, 50, count);
        auto lease = snapshot(history, request(history, stream, 50, 100));
        auto changed = stream;
        std::uint64_t first = 50 + count;
        if (failure == 0) ++first;
        if (failure == 1) --first;
        if (failure == 2) changed.center_frequency_hz += 12500;
        if (failure == 3) changed.sample_rate_hz /= 2;
        const auto bytes = source_bytes(first, 10, 8, stream.stream_id, stream.epoch, 2);
        const auto wanted = failure < 2 ? Status::Discontinuity : Status::MetadataMismatch;
        require(append_bytes(history, changed, first, bytes) == wanted, "gap/overlap/metadata failure explicit");
        const auto invalid = history.state();
        require(invalid.requires_new_epoch && invalid.retained_bytes == 0 && !invalid.has_samples,
                "continuity failure clears discoverable history");
        check_lease(lease, stream, 50, 100);
        release(history, lease);
        check_error(snapshot(history, request(history, stream, 50, 100)), Status::Discontinuity);
        require(append_bytes(history, stream, 50 + count, bytes) == Status::Discontinuity,
                "matching append cannot implicitly repair a broken epoch");
        ++stream.epoch;
        require(history.begin_epoch(stream) == Status::Ok, "explicit new epoch repairs continuity");
        append_generated(history, stream, 90000, count, 17);
        auto fresh = snapshot(history, request(history, stream, 90000, 100));
        check_lease(fresh, stream, 90000, 100, 17);
        release(history, fresh);
    }
}

void argument_limits_and_unchanged_rejections() {
    ++groups;
    ProcessBudget budget;
    History history(budget);
    auto stream = source();
    check_error(snapshot(history, {stream, 0, 0, 0, 1}), Status::NoEpoch);
    auto invalid = stream; invalid.sample_rate_hz = 0;
    require(history.begin_epoch(invalid) == Status::InvalidMetadata, "zero source rate rejected");
    require(history.begin_epoch(stream) == Status::Ok, "argument epoch begins");
    append_generated(history, stream, 0, kSlabBytes / 8);
    const auto bytes = source_bytes(kSlabBytes / 8, 1, 8, stream.stream_id, stream.epoch, 1);
    const auto before = history.state();
    auto stale = stream; ++stale.epoch;
    require(append_bytes(history, stale, kSlabBytes / 8, bytes) == Status::EpochMismatch,
            "wrong append epoch does not delete current history");
    unchanged_interval(before, history.state());
    Status status;
    no_allocation([&] { status = history.append(stream, kSlabBytes / 8, nullptr, 8); });
    require(status == Status::InvalidArgument, "null append rejected");
    no_allocation([&] { status = history.append(stream, kSlabBytes / 8, bytes.data(), 0); });
    require(status == Status::InvalidArgument, "empty append rejected");
    no_allocation([&] { status = history.append(stream, kSlabBytes / 8, bytes.data(), 7); });
    require(status == Status::InvalidArgument, "partial complex sample rejected");
    no_allocation([&] { status = history.append(stream, kSlabBytes / 8, bytes.data(), kMaxIngressBytes + 8); });
    require(status == Status::TooLarge, "oversized ingress rejected before reading caller memory");
    no_allocation([&] { status = history.append(stream, (std::numeric_limits<std::uint64_t>::max)(), bytes.data(), 8); });
    require(status == Status::ArithmeticOverflow, "append source endpoint overflow rejected before copy");
    unchanged_interval(before, history.state());
    check_error(snapshot(history, request(history, stream, 0, 0)), Status::InvalidArgument);
    check_error(snapshot(history, request(history, stream, (std::numeric_limits<std::uint64_t>::max)(), 1)),
                Status::ArithmeticOverflow);
    check_error(snapshot(history, request(history, stream, 0, 768001)), Status::TooLarge);
    check_error(snapshot(history, request(history, stream, 0, (std::numeric_limits<std::uint64_t>::max)())),
                Status::ArithmeticOverflow);
    auto wrong_generation = request(history, stream, 0, 1); ++wrong_generation.generation;
    check_error(snapshot(history, wrong_generation), Status::EpochMismatch);
    auto wrong_metadata = request(history, stream, 0, 1); ++wrong_metadata.stream.center_frequency_hz;
    check_error(snapshot(history, wrong_metadata), Status::MetadataMismatch);
    auto current = snapshot(history, request(history, stream, 0, 100));
    check_lease(current, stream, 0, 100);
    release(history, current);
    require(history.begin_epoch(stream) == Status::EpochMismatch, "same source epoch cannot restart silently");
    unchanged_interval(before, history.state());
}

void snapshot_time_and_byte_caps_are_independent() {
    ++groups;
    for (const auto format : {Format::CU8, Format::CF32LE}) {
        ProcessBudget budget;
        History history(budget);
        auto stream = source(format);
        require(history.begin_epoch(stream) == Status::Ok, "duration cap epoch");
        check_error(snapshot(history, request(history, stream, 0, 768001)), Status::TooLarge);
        ++stream.epoch; stream.sample_rate_hz = 16000000;
        require(history.begin_epoch(stream) == Status::Ok, "changed rate recomputes duration cap");
        const auto width = width_of(format);
        const auto over_bytes = kMaxSnapshotBytes / width + 1;
        check_error(snapshot(history, request(history, stream, 0, over_bytes)), Status::TooLarge);
    }
}

void move_release_and_cross_thread_completion() {
    ++groups;
    ProcessBudget budget;
    History history(budget);
    const auto stream = source();
    require(history.begin_epoch(stream) == Status::Ok, "move epoch");
    append_generated(history, stream, 0, kSlabBytes / 8);
    auto first = live(history, request(history, stream, 0, 100));
    auto second = live(history, request(history, stream, 100, 100));
    no_allocation([&] { second = std::move(first); });
    require(first.span_count() == 0 && !first, "moved-from lease exposes no spans");
    no_allocation([&] { history.reclaim(); });
    require(history.state().live_pinned_slabs == 1 && history.state().outstanding_live_leases == 1,
            "move assignment releases previous lease exactly once");
    check_lease(second, stream, 0, 100, 1, 8);
    auto* alias = &second;
    no_allocation([&] { second = std::move(*alias); });
    check_lease(second, stream, 0, 100, 1, 8);
    std::exception_ptr error;
    std::thread consumer([held = std::move(second), &error, stream]() mutable {
        try {
            check_lease(held, stream, 0, 100, 1, 8);
            no_allocation([&] { held.reset(); held.reset(); });
        } catch (...) { error = std::current_exception(); }
    });
    consumer.join();
    if (error) std::rethrow_exception(error);
    require(second.span_count() == 0 && !second, "thread ownership transfer empties original lease");
    no_allocation([&] { history.reclaim(); });
    require(history.state().live_pinned_slabs == 0 && history.state().outstanding_live_leases == 0,
            "owner acknowledges completion from another thread");
    struct CancelledConsumer {};
    try {
        auto cancelled = snapshot(history, request(history, stream, 0, 100));
        check_lease(cancelled, stream, 0, 100);
        throw CancelledConsumer{};
    } catch (const CancelledConsumer&) {}
    no_allocation([&] { history.reclaim(); });
    require(history.state().snapshot_pinned_slabs == 0, "exception abandonment releases a granted lease");
}

void concurrent_read_release_and_owner_reuse() {
    ++groups;
    ProcessBudget budget;
    History history(budget);
    const auto original = source();
    require(history.begin_epoch(original) == Status::Ok, "concurrent lifetime initial epoch");
    append_generated(history, original, 0, kSlabBytes / 8, 14);
    auto lease = snapshot(history, request(history, original, 0, 1000));
    std::atomic<unsigned> reader_ready{0}, owner_done{0};
    std::atomic<bool> stop{false}, released{false};
    std::exception_ptr consumer_error;
    std::thread consumer([held = std::move(lease), &reader_ready, &owner_done, &stop, &released,
                          &consumer_error, original]() mutable {
        try {
            for (unsigned step = 1; step <= 32 && !stop.load(std::memory_order_acquire); ++step) {
                reader_ready.store(step, std::memory_order_release);
                do {
                    check_lease(held, original, 0, 1000, 14);
                    std::this_thread::yield();
                } while (owner_done.load(std::memory_order_acquire) < step &&
                         !stop.load(std::memory_order_acquire));
            }
            no_allocation([&] { held.reset(); });
        } catch (...) { consumer_error = std::current_exception(); stop.store(true, std::memory_order_release); }
        released.store(true, std::memory_order_release);
    });
    try {
        for (unsigned step = 1; step <= 32; ++step) {
            while (reader_ready.load(std::memory_order_acquire) < step && !stop.load(std::memory_order_acquire))
                std::this_thread::yield();
            if (stop.load(std::memory_order_acquire)) break;
            auto stream = source(step % 2 ? Format::CU8 : Format::CF32LE, step + 1);
            stream.center_frequency_hz += step * 12500;
            Status status;
            no_allocation([&] { status = history.begin_epoch(stream); });
            require(status == Status::Ok, "owner retunes while another thread reads an old immutable lease");
            append_generated(history, stream, step * 100000, kSlabBytes / width_of(stream.format), step);
            no_allocation([&] { history.reclaim(); });
            owner_done.store(step, std::memory_order_release);
        }
        // Actual owner reclaim calls overlap the consumer's completion store.
        // There is no concurrent access/reset of the same Lease object.
        while (!released.load(std::memory_order_acquire)) {
            no_allocation([&] { history.reclaim(); });
            std::this_thread::yield();
        }
    } catch (...) {
        stop.store(true, std::memory_order_release);
        consumer.join();
        throw;
    }
    consumer.join();
    if (consumer_error) std::rethrow_exception(consumer_error);
    no_allocation([&] { history.reclaim(); });
    require(history.state().snapshot_pinned_slabs == 0, "concurrent completion acknowledged without leaked pins");
    check_budget(history, budget);
}

void service_first_destruction_and_shared_process_budget() {
    ++groups;
    ProcessBudget budget;
    Lease survivor;
    const auto stream = source();
    std::uint64_t old_pool = 0;
    Request old_request;
    {
        auto history = std::make_unique<History>(budget);
        require(history->begin_epoch(stream) == Status::Ok, "lifetime epoch");
        append_generated(*history, stream, 0, kSlabBytes / 8, 77);
        old_request = request(*history, stream, 0, 100);
        survivor = snapshot(*history, old_request);
        old_pool = survivor.info().pool_id;
        check_budget(*history, budget);
        history.reset();
    }
    check_lease(survivor, stream, 0, 100, 77);
    require(budget.stats().arenas == 1 && budget.stats().payload_bytes == kPayloadBytes,
            "retired arena remains charged while its lease survives facade");
    bool rejected = false;
    try { History replacement(budget); }
    catch (const budget_exhausted&) { rejected = true; }
    require(rejected, "restart cannot allocate a second arena behind a stalled lease");
    std::thread consumer([held = std::move(survivor)]() mutable { held.reset(); });
    consumer.join();
    require(budget.stats().arenas == 0 && budget.stats().payload_bytes == 0 && budget.stats().metadata_bytes == 0,
            "last cross-thread lease release refunds retired arena exactly once");
    History replacement(budget);
    require(replacement.state().pool_id != old_pool && replacement.state().pool_id != 0,
            "new arena has distinct identity even if allocator reuses its address");
    require(replacement.begin_epoch(stream) == Status::Ok, "replacement recreates same public epoch/reset number");
    append_generated(replacement, stream, 0, kSlabBytes / 8, 99);
    check_error(snapshot(replacement, old_request), Status::EpochMismatch);
    check_budget(replacement, budget);
}

void budget_failure_paths_and_ledger_lifetime() {
    ++groups;
    for (const auto limits : {std::pair<std::size_t, std::size_t>{kPayloadBytes - 1, kMetadataLimit},
                             std::pair<std::size_t, std::size_t>{kPayloadBytes, 1}}) {
        bool rejected = false;
        try { ProcessBudget budget(limits.first, limits.second); History history(budget); }
        catch (const budget_exhausted&) { rejected = true; }
        catch (const std::invalid_argument&) { rejected = true; }
        require(rejected, "undersized payload or metadata budget rejects arena admission");
    }
    ProcessBudget shared(2 * kPayloadBytes, 2 * kMetadataLimit);
    auto first = std::make_unique<History>(shared);
    auto second = std::make_unique<History>(shared);
    require(shared.stats().arenas == 2 && shared.stats().payload_bytes == 2 * kPayloadBytes,
            "two services debit the same explicit process ledger");
    bool rejected = false;
    try { History third(shared); }
    catch (const budget_exhausted&) { rejected = true; }
    require(rejected && shared.stats().arenas == 2, "failed third admission leaves ledger unchanged");
    first.reset(); second.reset();
    require(shared.stats().arenas == 0 && shared.stats().payload_bytes == 0 && shared.stats().metadata_bytes == 0,
            "destroyed services return all ledger charges");
    Lease survivor;
    const auto stream = source();
    {
        ProcessBudget ephemeral;
        History history(ephemeral);
        require(history.begin_epoch(stream) == Status::Ok, "ephemeral ledger epoch");
        append_generated(history, stream, 0, kSlabBytes / 8, 78);
        survivor = snapshot(history, request(history, stream, 0, 100));
    }
    check_lease(survivor, stream, 0, 100, 78);
    survivor.reset();
}

void process_control_itself_obeys_metadata_limit() {
    ++groups;
    bool rejected = false;
    try { ProcessBudget too_small(kPayloadBytes, 1); }
    catch (const budget_exhausted&) { rejected = true; }
    catch (const std::invalid_argument&) { rejected = true; }
    require(rejected, "process ledger cannot construct above its own declared metadata budget");
}

void counter_exhaustion_cannot_wrap_or_partially_append() {
    ++groups;
    const auto stream = source();
    {
        ProcessBudget budget;
        CounterLimits limits; limits.max_reset_generation = 2;
        History history(budget, limits);
        require(history.begin_epoch(stream) == Status::Ok, "first limited reset");
        auto next = stream; next.epoch = 2;
        require(history.begin_epoch(next) == Status::Ok, "second limited reset");
        append_generated(history, next, 0, kSlabBytes / 8);
        const auto before = history.state();
        ++next.epoch;
        require(history.begin_epoch(next) == Status::CounterExhausted, "reset generation fails before wrap");
        unchanged_interval(before, history.state());
    }
    {
        ProcessBudget budget;
        CounterLimits limits; limits.max_lease_generation = 2;
        History history(budget, limits);
        require(history.begin_epoch(stream) == Status::Ok, "lease generation epoch");
        append_generated(history, stream, 0, kSlabBytes / 8);
        std::uint64_t previous = 0;
        for (unsigned i = 0; i < 2; ++i) {
            auto lease = snapshot(history, request(history, stream, 0, 1));
            check_lease(lease, stream, 0, 1);
            require(lease.info().lease_generation > previous, "reused snapshot record changes lease generation");
            previous = lease.info().lease_generation;
            release(history, lease);
        }
        check_error(snapshot(history, request(history, stream, 0, 1)), Status::CounterExhausted);
        require(history.state().snapshot_pinned_slabs == 0, "failed generation admission leaks no pins");
    }
    {
        ProcessBudget budget;
        CounterLimits limits; limits.max_slab_incarnation = 1;
        History history(budget, limits);
        require(history.begin_epoch(stream) == Status::Ok, "slab incarnation epoch");
        bool exhausted = false;
        for (unsigned n = 0; n < 600; ++n) {
            const auto before = history.state();
            const auto bytes = source_bytes(n * (kSlabBytes / 8), kSlabBytes / 8, 8, stream.stream_id, stream.epoch, 1);
            const auto result = append_bytes(history, stream, n * (kSlabBytes / 8), bytes);
            if (result == Status::CounterExhausted) {
                unchanged_interval(before, history.state());
                exhausted = true;
                break;
            }
            require(result == Status::Ok, "only explicit counter exhaustion may stop bounded incarnation test");
        }
        require(exhausted && history.state().highest_slab_incarnation <= 1, "slab identity never wraps or exceeds limit");
        check_budget(history, budget);
    }
}

void slab_reuse_has_new_identity_while_live_pin_stays_immutable() {
    ++groups;
    ProcessBudget budget;
    History history(budget);
    const auto stream = source();
    const auto slab_samples = kSlabBytes / 8;
    require(history.begin_epoch(stream) == Status::Ok, "ABA observation epoch");
    append_generated(history, stream, 0, slab_samples);
    auto held = live(history, request(history, stream, 0, 1));
    const auto held_index = held.span(0).slab_index;
    const auto held_incarnation = held.span(0).slab_incarnation;
    std::array<std::uint64_t, 252> previous{};
    bool reused = false;
    for (std::size_t n = 1; n <= 400; ++n) {
        append_generated(history, stream, n * slab_samples, slab_samples);
        auto lease = snapshot(history, request(history, stream, n * slab_samples, 1));
        check_lease(lease, stream, n * slab_samples, 1);
        const auto& span = lease.span(0);
        require(span.slab_index != held_index, "held live slab cannot be recycled by history turnover");
        if (previous[span.slab_index]) {
            require(span.slab_incarnation > previous[span.slab_index], "reused slot has a new nonwrapping incarnation");
            reused = true;
        }
        previous[span.slab_index] = span.slab_incarnation;
        release(history, lease);
    }
    require(reused, "test observes actual physical slot reuse rather than unused capacity only");
    require(held.span(0).slab_index == held_index && held.span(0).slab_incarnation == held_incarnation,
            "still-held lease retains original immutable slab identity");
    check_lease(held, stream, 0, 1, 1, 8);
    release(history, held);
    check_budget(history, budget);
}

} // namespace

int main() {
    struct Test { const char* name; void (*run)(); };
    const Test tests[] = {
        {"retention and unaligned snapshots", retention_and_unaligned_snapshots},
        {"independent byte model", partial_callbacks_against_independent_model},
        {"stalled snapshot and live credits", stalled_snapshot_and_live_credits},
        {"physical live claims", live_physical_claims_are_bounded},
        {"retune and public identity ABA", leases_survive_changes_and_public_identity_reuse},
        {"gap and metadata invalidation", gaps_metadata_and_rejected_appends},
        {"atomic argument rejection", argument_limits_and_unchanged_rejections},
        {"independent time and byte caps", snapshot_time_and_byte_caps_are_independent},
        {"move and thread transfer", move_release_and_cross_thread_completion},
        {"concurrent read/release and owner reuse", concurrent_read_release_and_owner_reuse},
        {"service-first lifetime and restart budget", service_first_destruction_and_shared_process_budget},
        {"shared ledger and budget failure", budget_failure_paths_and_ledger_lifetime},
        {"ledger control metadata cap", process_control_itself_obeys_metadata_limit},
        {"counter exhaustion", counter_exhaustion_cannot_wrap_or_partially_append},
        {"slab incarnation ABA", slab_reuse_has_new_identity_while_live_pin_stays_immutable}
    };
    unsigned failures = 0;
    for (const auto& test : tests) {
        try { test.run(); }
        catch (const std::exception& error) {
            ++failures;
            std::cerr << "FAIL " << test.name << ": " << error.what() << '\n';
        }
    }
    std::cout << "Immutable slab independent contract: " << groups << " groups, " << failures << " failures, "
              << assertions.load() << " assertions, " << verified_bytes.load() << " exact bytes.\n"
              << "ABI bytes: Stream=" << sizeof(Stream) << ", Request=" << sizeof(Request)
              << ", Span=" << sizeof(Span) << ", Lease=" << sizeof(Lease) << ", State=" << sizeof(State) << ".\n"
              << "Budget bytes: payload=" << kPayloadBytes << ", arena/control metadata=" << observed_arena_metadata
              << ", process-budget control=" << observed_budget_control
              << ", total metadata=" << observed_arena_metadata + observed_budget_control << ".\n"
              << "Scope: synchronous single-owner storage and lease completion; no async coordinator, RF or timing claim.\n";
    return failures ? 1 : 0;
}
