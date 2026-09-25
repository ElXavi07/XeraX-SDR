// SPDX-License-Identifier: GPL-3.0-or-later
// Independent coordinator test support. No library-generated expected bytes.
#pragma once

#include "../iq_slabs/immutable_slabs.h"

#include <algorithm>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
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

// Observe C++ allocation calls only while an individual API operation runs.
// This does not intercept arbitrary C allocation or measure process RSS.
namespace allocation_probe {
inline thread_local bool active = false;
inline thread_local std::size_t calls = 0;
inline void record() noexcept { if (active) ++calls; }
}

#if defined(_MSC_VER)
#define PROBE_NOINLINE __declspec(noinline)
#elif defined(__GNUC__)
#define PROBE_NOINLINE __attribute__((noinline))
#else
#define PROBE_NOINLINE
#endif
PROBE_NOINLINE void* operator new(std::size_t bytes) {
    allocation_probe::record();
    if (auto* result = std::malloc(bytes ? bytes : 1)) return result;
    throw std::bad_alloc();
}
PROBE_NOINLINE void* operator new[](std::size_t bytes) { return ::operator new(bytes); }
PROBE_NOINLINE void operator delete(void* pointer) noexcept { std::free(pointer); }
PROBE_NOINLINE void operator delete[](void* pointer) noexcept { ::operator delete(pointer); }
PROBE_NOINLINE void operator delete(void* pointer, std::size_t) noexcept { ::operator delete(pointer); }
PROBE_NOINLINE void operator delete[](void* pointer, std::size_t) noexcept { ::operator delete(pointer); }
PROBE_NOINLINE void* operator new(std::size_t bytes, std::align_val_t alignment) {
    allocation_probe::record();
    void* result = nullptr;
#ifdef _WIN32
    result = _aligned_malloc(bytes ? bytes : 1, static_cast<std::size_t>(alignment));
#else
    if (posix_memalign(&result, static_cast<std::size_t>(alignment), bytes ? bytes : 1) != 0) result = nullptr;
#endif
    if (!result) throw std::bad_alloc();
    return result;
}
PROBE_NOINLINE void* operator new[](std::size_t bytes, std::align_val_t alignment) { return ::operator new(bytes, alignment); }
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

namespace independent {
namespace slabs = xerax::experiment::slabs;
inline std::atomic<std::size_t> assertions{0};
inline std::atomic<std::size_t> exact_bytes{0};

inline void require(bool condition, const char* message) {
    ++assertions;
    if (!condition) throw std::runtime_error(message);
}

template<class Operation>
void no_allocation(Operation&& operation) {
    allocation_probe::calls = 0;
    allocation_probe::active = true;
    try { operation(); }
    catch (...) { allocation_probe::active = false; throw; }
    allocation_probe::active = false;
    require(allocation_probe::calls == 0, "normal coordinator operation must not allocate C++ storage");
}

inline unsigned width(slabs::Format format) { return format == slabs::Format::CU8 ? 2U : 8U; }
inline slabs::Stream stream(slabs::Format format = slabs::Format::CF32LE, std::uint64_t epoch = 1) {
    return {271, epoch, 3072000, 451100000, format};
}

inline std::uint64_t mix(std::uint64_t value) {
    value ^= value >> 30U; value *= UINT64_C(0xbf58476d1ce4e5b9);
    value ^= value >> 27U; value *= UINT64_C(0x94d049bb133111eb);
    return value ^ (value >> 31U);
}

inline std::uint8_t byte_at(const slabs::Stream& source, std::uint64_t sample,
                           unsigned component, std::uint64_t nonce) {
    const auto key = mix(source.stream_id) ^ mix(source.epoch + UINT64_C(0x946735)) ^ mix(nonce);
    return static_cast<std::uint8_t>(mix(sample ^ key) >> (component * 8U));
}

inline std::vector<std::uint8_t> bytes(const slabs::Stream& source, std::uint64_t first,
                                     std::size_t samples, std::uint64_t nonce = 1) {
    const auto sample_width = width(source.format);
    std::vector<std::uint8_t> result(samples * sample_width);
    for (std::size_t index = 0; index < result.size(); ++index)
        result[index] = byte_at(source, first + index / sample_width,
                               static_cast<unsigned>(index % sample_width), nonce);
    return result;
}

template<class Buffer>
void check_bytes(const Buffer& lease, const slabs::Stream& source,
                        std::uint64_t first, std::uint64_t samples, std::uint64_t nonce = 1) {
    require(static_cast<bool>(lease), "successful reply owns a slab lease");
    const auto& info = lease.lease_info();
    require(info.stream == source && info.first_sample == first && info.end_sample == first + samples,
            "reply preserves independent exact source interval and every metadata field");
    const auto sample_width = width(source.format);
    require(info.byte_count == samples * sample_width, "lease byte count is exact");
    std::uint64_t cursor = first;
    std::size_t total = 0;
    require(lease.span_count() > 0 && lease.span_count() <= 101, "reply span count is bounded");
    for (std::size_t index = 0; index < lease.span_count(); ++index) {
        const auto& span = lease.span(index);
        require(span.data && span.first_sample == cursor && span.byte_count > 0 && span.byte_count % sample_width == 0,
                "published lease contains complete continuous spans");
        for (std::size_t offset = 0; offset < span.byte_count; ++offset)
            if (span.data[offset] != byte_at(source, cursor + offset / sample_width,
                                           static_cast<unsigned>(offset % sample_width), nonce))
                throw std::runtime_error("reply differs from independent source-index/epoch/nonce byte oracle");
        cursor += span.byte_count / sample_width;
        total += span.byte_count;
    }
    require(cursor == first + samples && total == info.byte_count, "reply has no duplicated or missing source bytes");
    exact_bytes.fetch_add(total, std::memory_order_relaxed);
}

// Explicit atomic rendezvous; the test never uses elapsed sleeps to force a race.
// Its enclosing test owns the thread and must always release/join on exceptions.
struct Gate {
    std::atomic<bool> entered{false};
    std::atomic<bool> released{false};
    void arrive_and_wait() noexcept {
        entered.store(true, std::memory_order_release);
        while (!released.load(std::memory_order_acquire)) std::this_thread::yield();
    }
    void wait() const noexcept { while (!entered.load(std::memory_order_acquire)) std::this_thread::yield(); }
    void release() noexcept { released.store(true, std::memory_order_release); }
};
}
