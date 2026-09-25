// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include "iq_history.h"
#include <memory>

namespace xerax::experiment {

struct CreditConfig {
    std::size_t ring_capacity_bytes = 0;
    std::size_t snapshot_capacity_bytes = 0;
    std::size_t max_snapshots = 0;
    // Bounds payload allocation: ring + all preallocated snapshot slots.
    // C++ object, mutex, allocator and descriptor overhead is additional.
    std::size_t payload_budget_bytes = 0;
};

struct CreditStats {
    std::size_t ring_capacity_bytes = 0;
    std::size_t snapshot_capacity_bytes = 0;
    std::size_t slot_count = 0;
    std::size_t outstanding_count = 0;
    std::size_t outstanding_reserved_bytes = 0;
    std::size_t preallocated_snapshot_bytes = 0;
    std::size_t total_payload_bytes = 0;
    std::size_t payload_budget_bytes = 0;
};

namespace detail { struct SnapshotPool; }
class CreditHistory;

// Immutable, move-only snapshot. Moving or destroying a lease releases no other
// lease's storage. Pool ownership remains valid after CreditHistory is destroyed.
// data() is valid only until this lease is moved, reset or destroyed.
class SnapshotLease {
public:
    SnapshotLease() = default;
    ~SnapshotLease();
    SnapshotLease(SnapshotLease&& other) noexcept;
    SnapshotLease& operator=(SnapshotLease&& other) noexcept;
    SnapshotLease(const SnapshotLease&) = delete;
    SnapshotLease& operator=(const SnapshotLease&) = delete;

    const SnapshotInfo& info() const noexcept { return info_; }
    Status status() const noexcept { return info_.status; }
    const std::uint8_t* data() const noexcept;
    std::size_t size() const noexcept { return info_.byte_count; }
    explicit operator bool() const noexcept { return status() == Status::Ok; }
    void reset() noexcept;

private:
    friend class CreditHistory;
    void release_storage() noexcept;
    SnapshotInfo info_{};
    std::shared_ptr<detail::SnapshotPool> pool_;
    std::size_t slot_ = 0;
};

class CreditHistory {
public:
    // Validates the budget before allocating any ring/slot payload. Allocation
    // failure propagates; no global pool or implicit fallback allocations exist.
    explicit CreditHistory(const CreditConfig& config);
    CreditHistory(const CreditHistory&) = delete;
    CreditHistory& operator=(const CreditHistory&) = delete;

    Status begin_epoch(const Stream& stream) { return history_.begin_epoch(stream); }
    Status append(const Stream& stream, std::uint64_t first_sample,
                  const void* bytes, std::size_t byte_count) {
        return history_.append(stream, first_sample, bytes, byte_count);
    }
    State state() const { return history_.state(); }
    // Exhausted credits return Busy before inspecting the requested interval.
    // Otherwise errors release the credit immediately; successful copies remain
    // immutable until their move-only lease is released.
    SnapshotLease snapshot(const Stream& stream, std::uint64_t first_sample,
                           std::uint64_t sample_count) const;
    // Tries the pool/ring mutex once per acquisition, returning Busy instead of
    // retrying. Cancelled/expired/overwritten copies return no lease payload and
    // return their credit. Whole-copy snapshot() retains its existing behavior.
    SnapshotLease snapshot_chunked(const Stream& stream, std::uint64_t first_sample,
                                   std::uint64_t sample_count, const ChunkCopyOptions& options) const;
    CreditStats credit_stats() const;

private:
    static std::size_t validate_config(const CreditConfig& config);
    History history_;
    std::shared_ptr<detail::SnapshotPool> pool_;
};

} // namespace xerax::experiment
