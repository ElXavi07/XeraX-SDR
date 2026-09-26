// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <mutex>
#include <stdexcept>

namespace xerax::experiment::notification {

enum class Status {
    Ok,
    Ready,
    AlreadyReady,
    Busy,
    NotCurrent,
    TimedOut,
    Closed,
    CounterExhausted
};

// Plain value identity, not an owning handle or an authentication credential.
// Domains are unique within this module's allocator lifetime, not across
// independently loaded module copies or processes. Neither counter is reset.
struct Token {
    std::uint64_t domain = 0;
    std::uint64_t generation = 0;
    explicit operator bool() const noexcept { return domain != 0 && generation != 0; }
};
inline bool operator==(Token a, Token b) noexcept {
    return a.domain == b.domain && a.generation == b.generation;
}
inline bool operator!=(Token a, Token b) noexcept { return !(a == b); }

struct Config {
    std::uint64_t max_generation = (std::numeric_limits<std::uint64_t>::max)();
    // A lifetime budget for false-ready predicate evaluations. Exposed so
    // deterministic tests can acknowledge a spurious wake without callbacks.
    // Exhaustion refuses further waiting; it never wraps or invents readiness.
    std::uint64_t max_predicate_checks = (std::numeric_limits<std::uint64_t>::max)();
};
struct ArmResult {
    Status status = Status::NotCurrent;
    Token token{};
};
struct State {
    Token current{};
    std::uint64_t domain = 0;
    std::uint64_t last_generation = 0;
    std::uint64_t predicate_checks = 0;
    std::uint64_t max_generation = 0;
    std::uint64_t max_predicate_checks = 0;
    bool armed = false;
    bool ready = false;
    bool waiting = false;
    bool closed = false;
};
struct Accounting {
    std::size_t object_bytes;
    std::size_t shared_domain_counter_bytes;
    std::size_t token_bytes;
    std::size_t state_value_bytes;
};

// Tests may define this friend to issue a predicate-neutral CV wake and to
// exercise reserve_domain with a separate local atomic. No production callback,
// alternate mutex, mutable public counter, or global-domain reset is provided.
struct ReadyNotificationTestAccess;

// One consumer calls arm/wait_until/abandon; one producer calls notify.
// A controller may call close concurrently with either role. state() is a
// synchronized observation, not a promise that the state remains unchanged.
//
// Lifetime: close is not a join. Join/stop every caller before destruction.
// This object never acquires, transfers, releases or revokes a source lease.
class ReadyNotification final {
public:
    using Clock = std::chrono::steady_clock;
    using TimePoint = Clock::time_point;

    explicit ReadyNotification(Config config = {})
        : config_(checked(config)), domain_(reserve_domain(domains_,
              (std::numeric_limits<std::uint64_t>::max)())) {}
    ~ReadyNotification() = default;
    ReadyNotification(const ReadyNotification&) = delete;
    ReadyNotification& operator=(const ReadyNotification&) = delete;
    ReadyNotification(ReadyNotification&&) = delete;
    ReadyNotification& operator=(ReadyNotification&&) = delete;

    // Arm BEFORE submitting corresponding work to its owner. A rejected source
    // submission may be followed by abandon; source cleanup is still separate.
    ArmResult arm() {
        std::lock_guard<std::mutex> lock(mutex_);
        if (closed_) return {Status::Closed, {}};
        if (armed_ || waiting_) return {Status::Busy, {}};
        if (generation_ == config_.max_generation) return {Status::CounterExhausted, {}};
        ++generation_;
        armed_ = true;
        ready_ = false;
        return {Status::Ok, {domain_, generation_}};
    }

    // Signal only the terminal readiness of this exact armed request. Repeated
    // signals coalesce into one token and report AlreadyReady; they do not add
    // credits. Predicate change and wait release share the SAME mutex.
    Status notify(Token token) {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            if (closed_) return Status::Closed;
            if (!matches(token)) return Status::NotCurrent;
            if (ready_) return Status::AlreadyReady;
            ready_ = true;
        }
        cv_.notify_one();
        return Status::Ok;
    }

    // Precedence under the mutex: Closed > NotCurrent > another waiter(Busy)
    // > Ready > predicate-budget exhaustion > timeout. Ready consumes the
    // notification slot even for an already expired deadline. TimedOut and
    // CounterExhausted retain its generation. This is a cooperative wait, not
    // a hard return deadline: acquiring/reacquiring the mutex may be delayed.
    Status wait_until(Token token, TimePoint deadline) {
        std::unique_lock<std::mutex> lock(mutex_);
        if (closed_) return Status::Closed;
        if (!matches(token)) return Status::NotCurrent;
        if (waiting_) return Status::Busy;
        waiting_ = true;
        struct WaitingGuard {
            bool& waiting;
            ~WaitingGuard() { waiting = false; }
        } guard{waiting_};
        for (;;) {
            if (closed_) return Status::Closed;
            if (ready_) {
                ready_ = false;
                armed_ = false;
                return Status::Ready;
            }
            if (predicate_checks_ == config_.max_predicate_checks)
                return Status::CounterExhausted;
            ++predicate_checks_;
            if (Clock::now() >= deadline) return Status::TimedOut;
            // Return/spurious wake/timeout all recheck the guarded predicate.
            // WaitingGuard clears the diagnostic on a propagated exception.
            cv_.wait_until(lock, deadline);
        }
    }

    // Consumer discards notification interest only. It must still drain/release
    // any associated source request separately. A concurrently blocked wait
    // cannot be abandoned by a second consumer; close is the control operation.
    Status abandon(Token token) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (closed_) return Status::Closed;
        if (!matches(token)) return Status::NotCurrent;
        if (waiting_) return Status::Busy;
        armed_ = false;
        ready_ = false;
        return Status::Ok;
    }

    // Stop wins over both pending and already-ready notifications. This is
    // sticky and idempotent; it wakes a current waiter without granting work.
    void close() {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            closed_ = true;
            armed_ = false;
            ready_ = false;
        }
        cv_.notify_all();
    }

    State state() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return {armed_ ? Token{domain_, generation_} : Token{}, domain_, generation_,
                predicate_checks_, config_.max_generation, config_.max_predicate_checks,
                armed_, ready_, waiting_, closed_};
    }
    static constexpr std::size_t metadata_bytes() noexcept { return sizeof(ReadyNotification); }
    static constexpr Accounting accounting() noexcept {
        return {sizeof(ReadyNotification), sizeof(domains_), sizeof(Token), sizeof(State)};
    }

private:
    friend struct ReadyNotificationTestAccess;
    static Config checked(Config config) {
        if (!config.max_generation || !config.max_predicate_checks)
            throw std::invalid_argument("Notification counter limits must be positive");
        return config;
    }
    static std::uint64_t reserve_domain(std::atomic<std::uint64_t>& counter,
                                        std::uint64_t maximum) {
        auto previous = counter.load(std::memory_order_relaxed);
        for (;;) {
            if (previous >= maximum) throw std::overflow_error("Notification domain exhausted");
            if (counter.compare_exchange_weak(previous, previous + 1,
                    std::memory_order_relaxed, std::memory_order_relaxed)) return previous + 1;
        }
    }
    bool matches(Token token) const noexcept {
        return armed_ && token.domain == domain_ && token.generation == generation_;
    }

    Config config_;
    const std::uint64_t domain_;
    mutable std::mutex mutex_;
    std::condition_variable cv_;
    std::uint64_t generation_ = 0;
    std::uint64_t predicate_checks_ = 0;
    bool armed_ = false;
    bool ready_ = false;
    bool waiting_ = false;
    bool closed_ = false;
    inline static std::atomic<std::uint64_t> domains_{0};
};

} // namespace xerax::experiment::notification
