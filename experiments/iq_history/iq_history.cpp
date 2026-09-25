// SPDX-License-Identifier: GPL-3.0-or-later
#include "iq_history.h"

#include <algorithm>
#include <cstring>
#include <limits>
#include <stdexcept>

namespace xerax::experiment {

History::History(std::size_t capacity_bytes) : storage_(capacity_bytes) {
    if (capacity_bytes == 0) throw std::invalid_argument("IQ history capacity must be positive");
}

bool History::valid_metadata(const Stream& s) {
    return s.sample_rate_hz != 0 &&
           (s.bytes_per_complex_sample == 2 || s.bytes_per_complex_sample == 8);
}

bool History::same_identity(const Stream& a, const Stream& b) {
    return a.stream_id == b.stream_id && a.epoch == b.epoch;
}

bool History::same_metadata(const Stream& a, const Stream& b) {
    return same_identity(a, b) && a.sample_rate_hz == b.sample_rate_hz &&
           a.center_frequency_hz == b.center_frequency_hz &&
           a.bytes_per_complex_sample == b.bytes_per_complex_sample;
}

Status History::begin_epoch(const Stream& stream) {
    if (!valid_metadata(stream) || storage_.size() < stream.bytes_per_complex_sample)
        return Status::InvalidMetadata;
    std::lock_guard<std::mutex> lock(mutex_);
    if (state_.active && state_.stream.stream_id == stream.stream_id &&
        stream.epoch <= state_.stream.epoch) return Status::EpochMismatch;
    state_ = {};
    state_.stream = stream;
    state_.active = true;
    state_.usable_capacity_bytes = storage_.size() - storage_.size() % stream.bytes_per_complex_sample;
    head_ = 0;
    return Status::Ok;
}

void History::invalidate_locked() {
    state_.requires_new_epoch = true;
    state_.has_samples = false;
    state_.first_sample = state_.end_sample = 0;
    state_.retained_bytes = 0;
    head_ = 0;
}

Status History::append(const Stream& stream, std::uint64_t first_sample,
                       const void* bytes, std::size_t byte_count) {
    if (!valid_metadata(stream)) return Status::InvalidMetadata;
    if (!bytes || byte_count == 0 || byte_count % stream.bytes_per_complex_sample != 0)
        return Status::InvalidArgument;
    const auto count = byte_count / stream.bytes_per_complex_sample;
    if (count > std::numeric_limits<std::uint64_t>::max() - first_sample)
        return Status::ArithmeticOverflow;
    const auto end = first_sample + static_cast<std::uint64_t>(count);

    std::lock_guard<std::mutex> lock(mutex_);
    if (!state_.active) return Status::NoEpoch;
    if (!same_identity(stream, state_.stream)) return Status::EpochMismatch;
    if (!same_metadata(stream, state_.stream)) {
        invalidate_locked();
        return Status::MetadataMismatch;
    }
    if (state_.requires_new_epoch) return Status::Discontinuity;
    if (state_.has_samples && first_sample != state_.end_sample) {
        invalidate_locked();
        return Status::Discontinuity;
    }

    const auto* input = static_cast<const std::uint8_t*>(bytes);
    const auto capacity = state_.usable_capacity_bytes;
    const bool truncated = byte_count > capacity;
    if (byte_count >= capacity) {
        std::memcpy(storage_.data(), input + (byte_count - capacity), capacity);
        head_ = 0;
        state_.retained_bytes = capacity;
    } else {
        // Subtraction avoids overflowing size_t when capacity is near its limit.
        const auto free = capacity - state_.retained_bytes;
        const auto discard = byte_count > free ? byte_count - free : 0;
        if (discard != 0) {
            head_ = discard >= capacity - head_ ? discard - (capacity - head_) : head_ + discard;
            state_.retained_bytes -= discard;
        }
        const auto tail = state_.retained_bytes >= capacity - head_
            ? state_.retained_bytes - (capacity - head_) : head_ + state_.retained_bytes;
        const auto first = std::min(byte_count, capacity - tail);
        std::memcpy(storage_.data() + tail, input, first);
        if (first != byte_count) std::memcpy(storage_.data(), input + first, byte_count - first);
        state_.retained_bytes += byte_count;
    }
    state_.end_sample = end;
    state_.first_sample = end - state_.retained_bytes / stream.bytes_per_complex_sample;
    state_.has_samples = true;
    return truncated ? Status::Truncated : Status::Ok;
}

void History::copy_out_locked(std::size_t offset, void* out, std::size_t count) const {
    const auto capacity = state_.usable_capacity_bytes;
    const auto start = offset >= capacity - head_ ? offset - (capacity - head_) : head_ + offset;
    const auto first = std::min(count, capacity - start);
    auto* output = static_cast<std::uint8_t*>(out);
    std::memcpy(output, storage_.data() + start, first);
    if (first != count) std::memcpy(output + first, storage_.data(), count - first);
}

Snapshot History::snapshot(const Stream& stream, std::uint64_t first_sample,
                           std::uint64_t sample_count) const {
    Snapshot result;
    if (!valid_metadata(stream)) { result.status = Status::InvalidMetadata; return result; }
    if (!sample_count) { result.status = Status::InvalidArgument; return result; }
    if (sample_count > std::numeric_limits<std::uint64_t>::max() - first_sample ||
        sample_count > std::numeric_limits<std::size_t>::max() / stream.bytes_per_complex_sample) {
        result.status = Status::ArithmeticOverflow;
        return result;
    }
    const auto end = first_sample + sample_count;
    std::lock_guard<std::mutex> lock(mutex_);
    if (!state_.active) return result;
    if (!same_identity(stream, state_.stream)) { result.status = Status::EpochMismatch; return result; }
    if (!same_metadata(stream, state_.stream)) { result.status = Status::MetadataMismatch; return result; }
    if (state_.requires_new_epoch) { result.status = Status::Discontinuity; return result; }
    if (!state_.has_samples || first_sample < state_.first_sample || end > state_.end_sample) {
        result.status = Status::NotRetained;
        return result;
    }
    const auto count = static_cast<std::size_t>(sample_count) * stream.bytes_per_complex_sample;
    const auto offset = static_cast<std::size_t>(first_sample - state_.first_sample) * stream.bytes_per_complex_sample;
    result.bytes.resize(count);
    copy_out_locked(offset, result.bytes.data(), count);
    result.stream = state_.stream;
    result.first_sample = first_sample;
    result.end_sample = end;
    result.status = Status::Ok;
    return result;
}

State History::state() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return state_;
}

SnapshotInfo History::snapshot_into(const Stream& stream, std::uint64_t first_sample,
                                    std::uint64_t sample_count, void* out,
                                    std::size_t out_capacity) const {
    SnapshotInfo result;
    if (!valid_metadata(stream)) { result.status = Status::InvalidMetadata; return result; }
    if (!out || !sample_count) { result.status = Status::InvalidArgument; return result; }
    if (sample_count > std::numeric_limits<std::uint64_t>::max() - first_sample ||
        sample_count > std::numeric_limits<std::size_t>::max() / stream.bytes_per_complex_sample) {
        result.status = Status::ArithmeticOverflow;
        return result;
    }
    const auto count = static_cast<std::size_t>(sample_count) * stream.bytes_per_complex_sample;
    if (count > out_capacity) { result.status = Status::OutputTooSmall; return result; }
    const auto end = first_sample + sample_count;
    std::lock_guard<std::mutex> lock(mutex_);
    if (!state_.active) return result;
    if (!same_identity(stream, state_.stream)) { result.status = Status::EpochMismatch; return result; }
    if (!same_metadata(stream, state_.stream)) { result.status = Status::MetadataMismatch; return result; }
    if (state_.requires_new_epoch) { result.status = Status::Discontinuity; return result; }
    if (!state_.has_samples || first_sample < state_.first_sample || end > state_.end_sample) {
        result.status = Status::NotRetained;
        return result;
    }
    const auto offset = static_cast<std::size_t>(first_sample - state_.first_sample) * stream.bytes_per_complex_sample;
    copy_out_locked(offset, out, count);
    result.stream = state_.stream;
    result.first_sample = first_sample;
    result.end_sample = end;
    result.byte_count = count;
    result.status = Status::Ok;
    return result;
}

} // namespace xerax::experiment
