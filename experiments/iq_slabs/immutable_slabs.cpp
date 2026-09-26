// SPDX-License-Identifier: GPL-3.0-or-later
#include "immutable_slabs.h"

#include <algorithm>
#include <array>
#include <atomic>
#include <cstring>
#include <mutex>
#include <new>
#include <utility>

namespace xerax::experiment::slabs {

std::size_t sample_bytes(Format format) noexcept {
    switch (format) {
    case Format::CU8: return 2;
    case Format::CF32LE: case Format::CF32BE: return 8;
    }
    return 0;
}
bool operator==(const Stream& a, const Stream& b) noexcept {
    return a.stream_id == b.stream_id && a.epoch == b.epoch &&
        a.sample_rate_hz == b.sample_rate_hz && a.center_frequency_hz == b.center_frequency_hz &&
        a.format == b.format;
}
bool operator!=(const Stream& a, const Stream& b) noexcept { return !(a == b); }

namespace detail {
struct BudgetState {
    mutable std::mutex mutex;
    BudgetStats stats{};
    std::uint64_t next_pool_id = 0;
};

// The size observer is used only synchronously by allocate_shared construction.
// Copies retained by its control block NEVER dereference it during deallocation.
template<class T> struct ControlAllocator {
    using value_type = T;
    std::size_t* observed;
    std::size_t limit;
    ControlAllocator(std::size_t* value, std::size_t cap) noexcept : observed(value), limit(cap) {}
    template<class U> ControlAllocator(const ControlAllocator<U>& other) noexcept
        : observed(other.observed), limit(other.limit) {}
    T* allocate(std::size_t n) {
        if (n > limit / sizeof(T)) throw budget_exhausted();
        const auto bytes = n * sizeof(T);
        if (*observed > limit - bytes) throw budget_exhausted();
        auto* result = static_cast<T*>(::operator new(bytes));
        *observed += bytes;
        return result;
    }
    void deallocate(T* pointer, std::size_t) noexcept { ::operator delete(pointer); }
    template<class U> bool operator==(const ControlAllocator<U>& other) const noexcept { return observed == other.observed; }
    template<class U> bool operator!=(const ControlAllocator<U>& other) const noexcept { return !(*this == other); }
};

template<class T> struct ArenaAllocator {
    using value_type = T;
    std::shared_ptr<BudgetState> budget;
    std::size_t* observed;
    ArenaAllocator(std::shared_ptr<BudgetState> value, std::size_t* count) noexcept
        : budget(std::move(value)), observed(count) {}
    template<class U> ArenaAllocator(const ArenaAllocator<U>& other) noexcept
        : budget(other.budget), observed(other.observed) {}
    T* allocate(std::size_t n) {
        if (n > kMetadataLimit / sizeof(T)) throw budget_exhausted();
        const auto bytes = n * sizeof(T);
        {
            std::lock_guard<std::mutex> lock(budget->mutex);
            const auto control = budget->stats.budget_control_bytes;
            const auto limit = budget->stats.metadata_limit;
            if (control > kMetadataLimit || bytes > kMetadataLimit - control ||
                control > limit || budget->stats.metadata_bytes > limit - control ||
                bytes > limit - control - budget->stats.metadata_bytes ||
                *observed > kMetadataLimit - control - bytes) throw budget_exhausted();
            budget->stats.metadata_bytes += bytes;
        }
        T* result = nullptr;
        try { result = static_cast<T*>(::operator new(bytes)); }
        catch (...) {
            std::lock_guard<std::mutex> lock(budget->mutex);
            budget->stats.metadata_bytes -= bytes;
            throw;
        }
        *observed += bytes;
        return result;
    }
    void deallocate(T* pointer, std::size_t n) noexcept {
        ::operator delete(pointer);
        std::lock_guard<std::mutex> lock(budget->mutex);
        budget->stats.metadata_bytes -= n * sizeof(T);
    }
    template<class U> bool operator==(const ArenaAllocator<U>& other) const noexcept { return budget == other.budget; }
    template<class U> bool operator!=(const ArenaAllocator<U>& other) const noexcept { return !(*this == other); }
};

struct Slab {
    std::uint64_t incarnation = 0;
    std::uint64_t first_sample = 0;
    std::size_t valid_bytes = 0;
    std::size_t pins = 0;
    bool history = false;
    bool filling = false;
    bool free() const noexcept { return !history && !filling && pins == 0; }
};
struct Record {
    std::atomic<bool> completed{false};
    bool active = false;
    std::uint64_t generation = 0;
    std::size_t span_count = 0;
    std::array<Span, kMaxSnapshotSpans> spans{};
};

struct Arena {
    std::shared_ptr<BudgetState> budget;
    std::unique_ptr<std::uint8_t[]> payload;
    CounterLimits limits;
    std::array<Slab, kReusableSlabs> slabs{};
    std::array<Record, 1 + kMaxLiveSpans> records{};
    std::array<std::size_t, kMaxHistorySpans> history{};
    std::size_t head = 0, count = 0, head_offset = 0;
    std::size_t filling = kReusableSlabs;
    bool accepted = false;
    bool had_epoch = false;
    State state{};

    Arena(std::shared_ptr<BudgetState> value, CounterLimits counter_limits)
        : budget(std::move(value)), limits(counter_limits) {
        {
            std::lock_guard<std::mutex> lock(budget->mutex);
            if (budget->stats.payload_bytes > budget->stats.payload_limit ||
                kPayloadBytes > budget->stats.payload_limit - budget->stats.payload_bytes)
                throw budget_exhausted();
            if (budget->next_pool_id == (std::numeric_limits<std::uint64_t>::max)())
                throw std::overflow_error("Slab pool identity exhausted");
            state.pool_id = ++budget->next_pool_id;
            budget->stats.payload_bytes += kPayloadBytes;
            ++budget->stats.arenas;
        }
        try { payload.reset(new std::uint8_t[kPayloadBytes]); }
        catch (...) {
            std::lock_guard<std::mutex> lock(budget->mutex);
            budget->stats.payload_bytes -= kPayloadBytes;
            --budget->stats.arenas;
            throw;
        }
    }
    ~Arena() {
        payload.reset(); // Keep the token charged until the bytes are actually freed.
        std::lock_guard<std::mutex> lock(budget->mutex);
        budget->stats.payload_bytes -= kPayloadBytes;
        --budget->stats.arenas;
    }
    std::uint8_t* bytes(std::size_t index) noexcept { return payload.get() + index * kSlabBytes; }
    std::size_t at(std::size_t index) const noexcept { return history[(head + index) % kMaxHistorySpans]; }
    void clear_history() noexcept {
        for (std::size_t i = 0; i < count; ++i) slabs[at(i)].history = false;
        if (filling != kReusableSlabs) slabs[filling].filling = false;
        head = count = head_offset = 0;
        filling = kReusableSlabs;
        accepted = false;
        state.has_samples = false;
        state.first_sample = state.end_sample = state.accepted_end_sample = 0;
        state.retained_bytes = 0;
    }
    void invalidate() noexcept {
        clear_history();
        state.active = false;
        state.requires_new_epoch = true;
        state.closed = false;
    }
    void reclaim() noexcept {
        for (auto& record : records) {
            if (!record.active || !record.completed.load(std::memory_order_acquire)) continue;
            for (std::size_t i = 0; i < record.span_count; ++i)
                --slabs[record.spans[i].slab_index].pins;
            record.span_count = 0;
            record.active = false;
            record.completed.store(false, std::memory_order_relaxed);
        }
    }
    void publish() noexcept {
        auto& tail = slabs[filling];
        std::size_t trim = state.retained_bytes + tail.valid_bytes > kRetentionBytes
            ? state.retained_bytes + tail.valid_bytes - kRetentionBytes : 0;
        while (trim != 0) {
            auto& front = slabs[at(0)];
            const auto useful = front.valid_bytes - head_offset;
            const auto remove = (std::min)(trim, useful);
            trim -= remove;
            state.retained_bytes -= remove;
            head_offset += remove;
            if (head_offset == front.valid_bytes) {
                front.history = false;
                head = (head + 1) % kMaxHistorySpans;
                --count;
                head_offset = 0;
            }
        }
        history[(head + count) % kMaxHistorySpans] = filling;
        ++count;
        tail.filling = false;
        tail.history = true;
        state.retained_bytes += tail.valid_bytes;
        const auto width = sample_bytes(state.stream.format);
        state.first_sample = slabs[at(0)].first_sample + head_offset / width;
        state.end_sample = tail.first_sample + tail.valid_bytes / width;
        state.has_samples = true;
        filling = kReusableSlabs;
    }
};

static_assert(sizeof(Arena) + sizeof(BudgetState) + 4096 < kMetadataLimit,
              "Slab arena metadata profile must be reviewed on this ABI");
} // namespace detail

ProcessBudget::ProcessBudget(std::size_t payload_limit, std::size_t metadata_limit) {
    std::size_t allocation_bytes = 0;
    state_ = std::allocate_shared<detail::BudgetState>(detail::ControlAllocator<detail::BudgetState>(
        &allocation_bytes, (std::min)(metadata_limit, kMetadataLimit)));
    state_->stats.payload_limit = payload_limit;
    state_->stats.metadata_limit = metadata_limit;
    state_->stats.budget_control_bytes = allocation_bytes;
}
BudgetStats ProcessBudget::stats() const {
    std::lock_guard<std::mutex> lock(state_->mutex);
    return state_->stats;
}

Lease::~Lease() { reset(); }
Lease::Lease(Lease&& other) noexcept
    : info_(other.info_), arena_(std::move(other.arena_)), record_(other.record_) {
    other.info_ = {};
}
Lease& Lease::operator=(Lease&& other) noexcept {
    if (this != &other) {
        reset();
        info_ = other.info_;
        arena_ = std::move(other.arena_);
        record_ = other.record_;
        other.info_ = {};
    }
    return *this;
}
std::size_t Lease::span_count() const noexcept { return arena_ ? arena_->records[record_].span_count : 0; }
const Span& Lease::span(std::size_t index) const & {
    if (!arena_ || index >= span_count()) throw std::out_of_range("Invalid immutable lease span");
    return arena_->records[record_].spans[index];
}
void Lease::reset() noexcept {
    if (arena_) {
        // No reads of record/span storage after publication. The owner can reclaim
        // immediately; the local shared ownership keeps its arena alive meanwhile.
        arena_->records[record_].completed.store(true, std::memory_order_release);
        arena_.reset();
    }
    info_ = {};
}

History::History(ProcessBudget& budget, CounterLimits limits) {
    if (!limits.max_reset_generation || !limits.max_slab_incarnation || !limits.max_lease_generation)
        throw std::invalid_argument("Generation limits must be positive");
    std::size_t allocation_bytes = 0;
    arena_ = std::allocate_shared<detail::Arena>(
        detail::ArenaAllocator<detail::Arena>(budget.state_, &allocation_bytes), budget.state_, limits);
    arena_->state.metadata_bytes = allocation_bytes + budget.state_->stats.budget_control_bytes;
}
History::~History() = default;

Status History::begin_epoch(const Stream& stream) {
    auto& arena = *arena_;
    if (!stream.sample_rate_hz || !sample_bytes(stream.format)) return Status::InvalidMetadata;
    if (arena.had_epoch && arena.state.stream.stream_id == stream.stream_id &&
        stream.epoch <= arena.state.stream.epoch) return Status::EpochMismatch;
    if (arena.state.generation == arena.limits.max_reset_generation) return Status::CounterExhausted;
    arena.reclaim();
    arena.clear_history();
    ++arena.state.generation;
    arena.state.stream = stream;
    arena.state.active = true;
    arena.state.requires_new_epoch = false;
    arena.state.closed = false;
    arena.had_epoch = true;
    return Status::Ok;
}

Status History::append(const Stream& stream, std::uint64_t first_sample,
                       const void* input, std::size_t byte_count) {
    auto& arena = *arena_;
    if (!arena.state.active) return arena.state.requires_new_epoch ? Status::Discontinuity : Status::NoEpoch;
    if (stream.stream_id != arena.state.stream.stream_id || stream.epoch != arena.state.stream.epoch)
        return Status::EpochMismatch;
    if (stream != arena.state.stream) { arena.invalidate(); return Status::MetadataMismatch; }
    if (arena.state.closed) return Status::Closed;
    const auto width = sample_bytes(stream.format);
    if (!input || !byte_count || byte_count % width != 0) return Status::InvalidArgument;
    if (byte_count > kMaxIngressBytes) return Status::TooLarge;
    const auto samples = static_cast<std::uint64_t>(byte_count / width);
    if (first_sample > (std::numeric_limits<std::uint64_t>::max)() - samples)
        return Status::ArithmeticOverflow;
    if (arena.accepted && first_sample != arena.state.accepted_end_sample) {
        arena.invalidate();
        return Status::Discontinuity;
    }
    arena.reclaim();
    const auto filled = arena.filling == kReusableSlabs ? 0 : arena.slabs[arena.filling].valid_bytes;
    const auto required = (filled + byte_count + kSlabBytes - 1) / kSlabBytes - (filled ? 1 : 0);
    std::array<std::size_t, 4> reserved{};
    std::size_t found = 0, free_count = 0;
    for (std::size_t i = 0; i < kReusableSlabs; ++i) {
        const auto& slab = arena.slabs[i];
        if (!slab.free()) continue;
        ++free_count;
        if (found < required && slab.incarnation < arena.limits.max_slab_incarnation) reserved[found++] = i;
    }
    if (found != required) return free_count >= required ? Status::CounterExhausted : Status::PoolExhausted;
    // Four permanently reserved scratch slabs make caller/arena aliasing harmless.
    // This first correctness increment stages then copies into packed slabs; its
    // extra ingress copy is explicit and must not be hidden in a future comparison.
    auto* scratch = arena.payload.get() + kReusableSlabs * kSlabBytes;
    std::memmove(scratch, input, byte_count);
    std::size_t consumed = 0, reservation = 0;
    while (consumed < byte_count) {
        if (arena.filling == kReusableSlabs) {
            arena.filling = reserved[reservation++];
            auto& slab = arena.slabs[arena.filling];
            ++slab.incarnation;
            slab.first_sample = first_sample + consumed / width;
            slab.valid_bytes = 0;
            slab.filling = true;
        }
        auto& slab = arena.slabs[arena.filling];
        const auto copy = (std::min)(byte_count - consumed, kSlabBytes - slab.valid_bytes);
        std::memcpy(arena.bytes(arena.filling) + slab.valid_bytes, scratch + consumed, copy);
        slab.valid_bytes += copy;
        consumed += copy;
        if (slab.valid_bytes == kSlabBytes) arena.publish();
    }
    arena.accepted = true;
    arena.state.accepted_end_sample = first_sample + samples;
    return Status::Ok;
}

Status History::seal_tail() {
    auto& arena = *arena_;
    if (!arena.state.active) return arena.state.requires_new_epoch ? Status::Discontinuity : Status::NoEpoch;
    if (arena.state.closed) return Status::Closed;
    arena.reclaim();
    if (arena.filling != kReusableSlabs) arena.publish();
    arena.state.closed = true;
    return Status::Ok;
}

Lease History::snapshot(const Request& request) { return grant(request, true); }
Lease History::live(const Request& request) { return grant(request, false); }
Lease History::grant(const Request& request, bool snapshot_request) {
    auto& arena = *arena_;
    arena.reclaim();
    Lease result;
    auto fail = [&result](Status status) -> Lease { result.info_.status = status; return std::move(result); };
    if (!arena.state.active) return fail(arena.state.requires_new_epoch ? Status::Discontinuity : Status::NoEpoch);
    if (request.pool_id != arena.state.pool_id || request.generation != arena.state.generation ||
        request.stream.stream_id != arena.state.stream.stream_id || request.stream.epoch != arena.state.stream.epoch)
        return fail(Status::EpochMismatch);
    if (request.stream != arena.state.stream) return fail(Status::MetadataMismatch);
    if (!request.sample_count) return fail(Status::InvalidArgument);
    const auto maximum = (std::numeric_limits<std::uint64_t>::max)();
    const auto width = sample_bytes(request.stream.format);
    if (request.first_sample > maximum - request.sample_count || request.sample_count > maximum / width ||
        request.sample_count > (std::numeric_limits<std::size_t>::max)() / width)
        return fail(Status::ArithmeticOverflow);
    const auto bytes = static_cast<std::size_t>(request.sample_count) * width;
    const auto end = request.first_sample + request.sample_count;
    if (snapshot_request && (bytes > kMaxSnapshotBytes || request.sample_count > request.stream.sample_rate_hz / 4U))
        return fail(Status::TooLarge);
    if (!arena.state.has_samples || request.first_sample < arena.state.first_sample || end > arena.state.end_sample)
        return fail(Status::NotRetained);
    std::size_t span_count = 0;
    for (std::size_t i = 0; i < arena.count; ++i) {
        const auto& slab = arena.slabs[arena.at(i)];
        if (slab.first_sample < end && slab.first_sample + slab.valid_bytes / width > request.first_sample) ++span_count;
    }
    if (!span_count || span_count > (snapshot_request ? kMaxSnapshotSpans : kMaxLiveSpans))
        return fail(Status::TooLarge);
    std::size_t selected = arena.records.size();
    if (snapshot_request) {
        if (arena.records[0].active) return fail(Status::Busy);
        if (arena.records[0].generation == arena.limits.max_lease_generation) return fail(Status::CounterExhausted);
        selected = 0;
    } else {
        std::size_t pinned = 0;
        bool exhausted = false;
        for (std::size_t i = 1; i < arena.records.size(); ++i) {
            const auto& record = arena.records[i];
            if (record.active) pinned += record.span_count;
            else if (record.generation == arena.limits.max_lease_generation) exhausted = true;
            else if (selected == arena.records.size()) selected = i;
        }
        if (pinned + span_count > kMaxLiveSpans) return fail(Status::Busy);
        if (selected == arena.records.size()) return fail(exhausted ? Status::CounterExhausted : Status::Busy);
    }
    auto& record = arena.records[selected];
    record.span_count = 0;
    for (std::size_t i = 0; i < arena.count; ++i) {
        const auto index = arena.at(i);
        auto& slab = arena.slabs[index];
        const auto first = (std::max)(request.first_sample, slab.first_sample);
        const auto last = (std::min)(end, slab.first_sample + slab.valid_bytes / width);
        if (first >= last) continue;
        const auto offset = static_cast<std::size_t>(first - slab.first_sample) * width;
        const auto length = static_cast<std::size_t>(last - first) * width;
        record.spans[record.span_count++] = Span{arena.bytes(index) + offset, length, first, index, slab.incarnation};
        ++slab.pins;
    }
    ++record.generation;
    record.completed.store(false, std::memory_order_relaxed);
    record.active = true;
    result.info_ = LeaseInfo{Status::Ok, request.stream, request.generation, arena.state.pool_id,
                            record.generation, request.first_sample, end, bytes};
    result.record_ = selected;
    result.arena_ = arena_;
    return result;
}

void History::reclaim() noexcept { arena_->reclaim(); }
State History::state() const noexcept {
    const auto& arena = *arena_;
    State result = arena.state;
    result.history_slabs = arena.count;
    result.filling_bytes = arena.filling == kReusableSlabs ? 0 : arena.slabs[arena.filling].valid_bytes;
    for (const auto& slab : arena.slabs) {
        if (slab.free()) ++result.free_slabs;
        result.highest_slab_incarnation = (std::max)(result.highest_slab_incarnation, slab.incarnation);
    }
    if (arena.records[0].active) result.snapshot_pinned_slabs = arena.records[0].span_count;
    for (std::size_t i = 1; i < arena.records.size(); ++i) {
        if (!arena.records[i].active) continue;
        result.live_pinned_slabs += arena.records[i].span_count;
        ++result.outstanding_live_leases;
    }
    return result;
}

} // namespace xerax::experiment::slabs
