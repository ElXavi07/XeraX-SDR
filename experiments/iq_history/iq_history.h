// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <atomic>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <mutex>
#include <vector>

namespace xerax::experiment {

// Indices count complex samples, not bytes or individual I/Q components.
// Epoch changes are explicit: increment epoch on a source discontinuity, retune,
// rate or format change. Different receivers should own different History objects.
struct Stream {
    std::uint64_t stream_id = 0;
    std::uint64_t epoch = 0;
    std::uint32_t sample_rate_hz = 0;
    std::uint64_t center_frequency_hz = 0;
    std::uint32_t bytes_per_complex_sample = 0; // 2 = CU8; 8 = CF32; bytes remain opaque.
};

enum class Status {
    Ok,
    Truncated,
    InvalidMetadata,
    InvalidArgument,
    ArithmeticOverflow,
    NoEpoch,
    EpochMismatch,
    MetadataMismatch,
    Discontinuity,
    NotRetained,
    OutputTooSmall,
    Busy,
    Cancelled,
    DeadlineExpired,
};

struct State {
    Stream stream{};
    bool active = false;
    bool requires_new_epoch = false;
    bool has_samples = false;
    std::uint64_t first_sample = 0;
    std::uint64_t end_sample = 0; // exclusive
    std::size_t retained_bytes = 0;
    std::size_t usable_capacity_bytes = 0;
};

struct Snapshot {
    Status status = Status::NoEpoch;
    Stream stream{};
    std::uint64_t first_sample = 0;
    std::uint64_t end_sample = 0; // exclusive
    std::vector<std::uint8_t> bytes;
};

struct SnapshotInfo {
    Status status = Status::NoEpoch;
    Stream stream{};
    std::uint64_t first_sample = 0;
    std::uint64_t end_sample = 0; // exclusive
    std::size_t byte_count = 0;
};

struct ChunkCopyOptions {
    std::size_t chunk_bytes = 64 * 1024;
    std::chrono::steady_clock::time_point deadline = std::chrono::steady_clock::time_point::max();
    // Optional cancellation flag must outlive the call.
    const std::atomic<bool>* cancelled = nullptr;
    // Test-only interleaving hook: called between chunks, outside all locks.
    // The byte count is copied progress, never an independently valid result.
    void (*test_after_chunk)(void* context, std::size_t copied_bytes) = nullptr;
    void* test_context = nullptr;
};

class History {
public:
    // Fixed payload storage: exactly capacity_bytes bytes, allocated once.
    // Throws invalid_argument for zero capacity; allocation failure propagates.
    explicit History(std::size_t capacity_bytes);
    History(const History&) = delete;
    History& operator=(const History&) = delete;

    // Replaces all retained data. For the same stream ID, epoch must increase.
    // A new stream ID is an explicit source replacement, not automatic discovery.
    Status begin_epoch(const Stream& stream);

    // Copies whole complex samples. Oversized blocks retain their newest suffix
    // and return Truncated; the prefix is deliberately not represented as retained.
    // Same-epoch metadata changes or noncontiguous indices invalidate history and
    // require begin_epoch with a new epoch. Stale/wrong epochs leave current data intact.
    Status append(const Stream& stream, std::uint64_t first_sample,
                  const void* bytes, std::size_t byte_count);

    // Returns an owned byte-exact copy, or an error with an empty payload. It never
    // returns partial intervals, zero fills gaps, or silently substitutes another epoch.
    Snapshot snapshot(const Stream& stream, std::uint64_t first_sample,
                      std::uint64_t sample_count) const;
    // Copies into caller-owned, non-overlapping storage without allocating.
    // Errors leave that storage unchanged. Used by the separate credit-pool variant.
    SnapshotInfo snapshot_into(const Stream& stream, std::uint64_t first_sample,
                               std::uint64_t sample_count, void* out,
                               std::size_t out_capacity) const;
    // Nonwaiting ring acquisition per chunk; validates the ORIGINAL full interval
    // and epoch each time. chunk_bytes rounds down to whole complex samples.
    // Failure returns no valid metadata/byte_count, but private destination bytes
    // may already have been copied. Caller must discard them on any error.
    // Deadlines/cancellation are cooperative, not wall-clock latency guarantees.
    SnapshotInfo snapshot_chunked_into(const Stream& stream, std::uint64_t first_sample,
                                       std::uint64_t sample_count, void* out,
                                       std::size_t out_capacity, const ChunkCopyOptions& options) const;
    State state() const;
    std::size_t capacity_bytes() const noexcept { return storage_.size(); }

private:
    static bool valid_metadata(const Stream& stream);
    static bool same_identity(const Stream& a, const Stream& b);
    static bool same_metadata(const Stream& a, const Stream& b);
    void invalidate_locked();
    void copy_out_locked(std::size_t offset, void* out, std::size_t count) const;

    std::vector<std::uint8_t> storage_;
    mutable std::mutex mutex_;
    State state_{};
    std::size_t head_ = 0;
    // Detect explicit A->B->A source replacement between chunks even if a caller
    // reuses its public stream/epoch IDs. Never wraps into an old generation.
    std::uint64_t generation_ = 0;
};

} // namespace xerax::experiment
