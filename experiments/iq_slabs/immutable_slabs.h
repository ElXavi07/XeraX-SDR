// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <cstddef>
#include <cstdint>
#include <limits>
#include <memory>
#include <stdexcept>

namespace xerax::experiment::slabs {

inline constexpr std::size_t kSlabBytes = 61440;
inline constexpr std::size_t kTotalSlabs = 256;
inline constexpr std::size_t kReusableSlabs = 252;
inline constexpr std::size_t kPayloadBytes = kSlabBytes * kTotalSlabs;
inline constexpr std::size_t kRetentionBytes = 8 * 1024 * 1024;
inline constexpr std::size_t kMetadataLimit = 128 * 1024;
inline constexpr std::size_t kMaxIngressBytes = 4 * kSlabBytes;
inline constexpr std::size_t kMaxSnapshotBytes = 6144000;
inline constexpr std::size_t kMaxSnapshotSpans = 101;
inline constexpr std::size_t kMaxLiveSpans = 8;
inline constexpr std::size_t kMaxHistorySpans = 138;

enum class Format { CU8, CF32LE, CF32BE };
struct Stream {
    std::uint64_t stream_id = 0;
    std::uint64_t epoch = 0;
    std::uint32_t sample_rate_hz = 0;
    std::uint64_t center_frequency_hz = 0;
    Format format = Format::CU8;
};
std::size_t sample_bytes(Format format) noexcept;
bool operator==(const Stream& a, const Stream& b) noexcept;
bool operator!=(const Stream& a, const Stream& b) noexcept;

enum class Status {
    Ok, InvalidMetadata, InvalidArgument, ArithmeticOverflow, NoEpoch,
    EpochMismatch, MetadataMismatch, Discontinuity, NotRetained,
    Busy, TooLarge, Closed, CounterExhausted, PoolExhausted
};

struct CounterLimits {
    std::uint64_t max_reset_generation = (std::numeric_limits<std::uint64_t>::max)();
    std::uint64_t max_slab_incarnation = (std::numeric_limits<std::uint64_t>::max)();
    std::uint64_t max_lease_generation = (std::numeric_limits<std::uint64_t>::max)();
};

struct BudgetStats {
    std::size_t payload_bytes = 0;
    std::size_t metadata_bytes = 0; // Actual arena/control-block allocator requests.
    std::size_t arenas = 0;
    std::size_t payload_limit = 0;
    std::size_t metadata_limit = 0;
    std::size_t budget_control_bytes = 0; // Separate, fixed process-ledger allocation.
};
class budget_exhausted : public std::runtime_error {
public:
    budget_exhausted() : std::runtime_error("Immutable slab process budget exhausted") {}
};
namespace detail { struct BudgetState; struct Arena; }

// Pass the SAME process ledger to every service/restart. Independently constructing
// ledgers deliberately creates independent limits; no implicit global singleton.
class ProcessBudget {
public:
    explicit ProcessBudget(std::size_t payload_limit = kPayloadBytes,
                           std::size_t metadata_limit = kMetadataLimit);
    BudgetStats stats() const;
private:
    friend class History;
    std::shared_ptr<detail::BudgetState> state_;
};

struct Request {
    Stream stream{};
    std::uint64_t generation = 0; // From state(); defeats public A -> B -> A reuse.
    std::uint64_t pool_id = 0; // From state(); identity within this ProcessBudget.
    std::uint64_t first_sample = 0;
    std::uint64_t sample_count = 0;
};
struct LeaseInfo {
    Status status = Status::NoEpoch;
    Stream stream{};
    std::uint64_t generation = 0;
    std::uint64_t pool_id = 0;
    std::uint64_t lease_generation = 0;
    std::uint64_t first_sample = 0;
    std::uint64_t end_sample = 0;
    std::size_t byte_count = 0;
};
struct Span {
    const std::uint8_t* data = nullptr;
    std::size_t byte_count = 0;
    std::uint64_t first_sample = 0;
    std::size_t slab_index = 0;
    std::uint64_t slab_incarnation = 0;
};

// Borrowed spans are valid ONLY while this move-only lease remains alive/unreset.
// No raw History lookup exists. Synchronize transfer to another thread yourself;
// do not read/reset the same lease concurrently. Release may occur on any thread.
class Lease {
public:
    Lease() = default;
    ~Lease();
    Lease(Lease&& other) noexcept;
    Lease& operator=(Lease&& other) noexcept;
    Lease(const Lease&) = delete;
    Lease& operator=(const Lease&) = delete;
    Status status() const noexcept { return info_.status; }
    const LeaseInfo& info() const noexcept { return info_; }
    explicit operator bool() const noexcept { return status() == Status::Ok; }
    std::size_t span_count() const noexcept;
    const Span& span(std::size_t index) const &;
    const Span& span(std::size_t) const && = delete;
    void reset() noexcept;
private:
    friend class History;
    LeaseInfo info_{};
    std::shared_ptr<detail::Arena> arena_;
    std::size_t record_ = 0;
};

struct State {
    Stream stream{};
    std::uint64_t generation = 0;
    bool active = false;
    bool requires_new_epoch = false;
    bool closed = false;
    bool has_samples = false;
    std::uint64_t first_sample = 0; // Exact useful retained interval.
    std::uint64_t end_sample = 0;   // Published frontier, exclusive.
    std::uint64_t accepted_end_sample = 0; // Includes unpublished filling bytes.
    std::size_t retained_bytes = 0;
    std::size_t history_slabs = 0;
    std::size_t filling_bytes = 0;
    std::size_t free_slabs = 0; // Unowned slots, including exhausted incarnation IDs.
    std::size_t snapshot_pinned_slabs = 0;
    std::size_t live_pinned_slabs = 0; // Sum of claims; overlap is still charged.
    std::size_t outstanding_live_leases = 0;
    std::size_t payload_bytes = kPayloadBytes;
    std::size_t metadata_bytes = 0;
    std::uint64_t pool_id = 0;
    std::uint64_t highest_slab_incarnation = 0;
};

class History {
public:
    explicit History(ProcessBudget& budget, CounterLimits limits = {});
    ~History();
    History(const History&) = delete;
    History& operator=(const History&) = delete;
    History(History&&) = delete;
    History& operator=(History&&) = delete;
    // ALL methods below are single-owner synchronous operations. No concurrent
    // request coordinator is supplied. Only Lease release may run concurrently.
    // Requests are scoped to this ProcessBudget ownership domain, never portable
    // between independently constructed ledgers or serializable network handles.
    Status begin_epoch(const Stream& stream);
    // A gap/overlap or same-epoch metadata change invalidates discoverable data;
    // append/grant/seal then return Discontinuity until an explicit new epoch.
    // Other failures accept no prefix and leave the source interval unchanged.
    Status append(const Stream& stream, std::uint64_t first_sample,
                  const void* bytes, std::size_t byte_count);
    // Publishes one final short slab and permanently closes this epoch. Retune
    // using begin_epoch before appending again; never seal every short callback.
    Status seal_tail();
    Lease snapshot(const Request& request);
    Lease live(const Request& request);
    void reclaim() noexcept;
    State state() const noexcept;
private:
    Lease grant(const Request& request, bool snapshot);
    std::shared_ptr<detail::Arena> arena_;
};

} // namespace xerax::experiment::slabs
