// SPDX-License-Identifier: GPL-3.0-or-later
#include "credit_history.h"

#include <stdexcept>
#include <utility>

namespace xerax::experiment {
namespace detail {
struct SnapshotPool {
    struct Slot {
        std::unique_ptr<std::uint8_t[]> bytes;
        bool leased = false;
    };
    explicit SnapshotPool(const CreditConfig& c) : config(c), slots(c.max_snapshots) {
        for (auto& slot : slots) slot.bytes = std::make_unique<std::uint8_t[]>(c.snapshot_capacity_bytes);
    }
    const CreditConfig config;
    std::vector<Slot> slots;
    std::mutex mutex;
    std::size_t outstanding = 0;
};
} // namespace detail

SnapshotLease::~SnapshotLease() { release_storage(); }

SnapshotLease::SnapshotLease(SnapshotLease&& other) noexcept
    : info_(other.info_), pool_(std::move(other.pool_)), slot_(other.slot_) {
    other.info_ = {};
    other.slot_ = 0;
}

SnapshotLease& SnapshotLease::operator=(SnapshotLease&& other) noexcept {
    if (this != &other) {
        release_storage();
        info_ = other.info_;
        pool_ = std::move(other.pool_);
        slot_ = other.slot_;
        other.info_ = {};
        other.slot_ = 0;
    }
    return *this;
}

const std::uint8_t* SnapshotLease::data() const noexcept {
    return pool_ && info_.status == Status::Ok ? pool_->slots[slot_].bytes.get() : nullptr;
}

void SnapshotLease::release_storage() noexcept {
    if (pool_) {
        // Unlock before releasing the last shared pool owner; its mutex may be
        // destroyed when pool_.reset() runs after CreditHistory has gone away.
        {
            std::lock_guard<std::mutex> lock(pool_->mutex);
            pool_->slots[slot_].leased = false;
            --pool_->outstanding;
        }
        pool_.reset();
    }
}

void SnapshotLease::reset() noexcept {
    release_storage();
    info_ = {};
    slot_ = 0;
}

std::size_t CreditHistory::validate_config(const CreditConfig& config) {
    if (!config.ring_capacity_bytes || !config.snapshot_capacity_bytes || !config.max_snapshots ||
        !config.payload_budget_bytes) throw std::invalid_argument("IQ credit capacities/count must be positive");
    if (config.ring_capacity_bytes > config.payload_budget_bytes ||
        config.snapshot_capacity_bytes >
            (config.payload_budget_bytes - config.ring_capacity_bytes) / config.max_snapshots)
        throw std::length_error("IQ ring and snapshot slots exceed the payload budget");
    return config.ring_capacity_bytes;
}

CreditHistory::CreditHistory(const CreditConfig& config)
    : history_(validate_config(config)), pool_(std::make_shared<detail::SnapshotPool>(config)) {}

SnapshotLease CreditHistory::snapshot(const Stream& stream, std::uint64_t first_sample,
                                      std::uint64_t sample_count) const {
    SnapshotLease result;
    {
        std::lock_guard<std::mutex> lock(pool_->mutex);
        for (std::size_t index = 0; index < pool_->slots.size(); ++index) {
            auto& slot = pool_->slots[index];
            if (slot.leased) continue;
            slot.leased = true;
            ++pool_->outstanding;
            result.pool_ = pool_;
            result.slot_ = index;
            break;
        }
    }
    if (!result.pool_) { result.info_.status = Status::Busy; return result; }
    // The lease is already an exception-safe owner. A throwing mutex operation
    // in History will unwind this local lease and return its pool credit.
    result.info_ = history_.snapshot_into(stream, first_sample, sample_count,
                                         pool_->slots[result.slot_].bytes.get(),
                                         pool_->config.snapshot_capacity_bytes);
    if (result.info_.status != Status::Ok) result.release_storage();
    return result;
}

CreditStats CreditHistory::credit_stats() const {
    std::lock_guard<std::mutex> lock(pool_->mutex);
    CreditStats stats;
    stats.ring_capacity_bytes = pool_->config.ring_capacity_bytes;
    stats.snapshot_capacity_bytes = pool_->config.snapshot_capacity_bytes;
    stats.slot_count = pool_->config.max_snapshots;
    stats.outstanding_count = pool_->outstanding;
    stats.outstanding_reserved_bytes = pool_->outstanding * pool_->config.snapshot_capacity_bytes;
    stats.preallocated_snapshot_bytes = pool_->config.max_snapshots * pool_->config.snapshot_capacity_bytes;
    stats.total_payload_bytes = stats.ring_capacity_bytes + stats.preallocated_snapshot_bytes;
    stats.payload_budget_bytes = pool_->config.payload_budget_bytes;
    return stats;
}

} // namespace xerax::experiment
