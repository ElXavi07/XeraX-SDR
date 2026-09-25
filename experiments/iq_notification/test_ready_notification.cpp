// SPDX-License-Identifier: GPL-3.0-or-later
// Explicit checks remain active with NDEBUG. Handshakes establish ordering;
// safety deadlines only bound hangs and do not establish timing performance.
#include "ready_notification.h"
#include "iq_coordinator.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <exception>
#include <functional>
#include <initializer_list>
#include <iostream>
#include <limits>
#include <memory>
#include <thread>
#include <type_traits>
#include <utility>

namespace xerax::experiment::notification {
struct ReadyNotificationTestAccess {
    static void spurious_wake(ReadyNotification& notice) { notice.cv_.notify_all(); }
    static std::uint64_t local_domain(std::atomic<std::uint64_t>& counter, std::uint64_t maximum) {
        return ReadyNotification::reserve_domain(counter, maximum);
    }
};
}

namespace {
namespace notification = xerax::experiment::notification;
namespace slabs = xerax::experiment::slabs;
namespace coordinator = xerax::experiment::coordinator;
using notification::ReadyNotification;
using notification::ReadyNotificationTestAccess;
using notification::Status;
using notification::Token;
using Clock = ReadyNotification::Clock;
std::atomic<std::size_t> checks{0};
std::atomic<std::size_t> checked_bytes{0};

static_assert(!std::is_copy_constructible_v<ReadyNotification> && !std::is_move_constructible_v<ReadyNotification>);
static_assert(!std::is_copy_assignable_v<ReadyNotification> && !std::is_move_assignable_v<ReadyNotification>);

void require(bool condition, const char* message) {
    checks.fetch_add(1, std::memory_order_relaxed);
    if (!condition) throw std::runtime_error(message);
}
auto safety_deadline() { return Clock::now() + std::chrono::seconds(30); }
auto expired_deadline() { return Clock::now() - std::chrono::seconds(1); }

template<class Predicate>
void await(Predicate predicate, const char* message) {
    const auto until = safety_deadline();
    while (!predicate()) {
        if (Clock::now() >= until) throw std::runtime_error(message);
        std::this_thread::yield();
    }
    checks.fetch_add(1, std::memory_order_relaxed);
}

// Always close/join before the notification object can be destroyed, even when
// an assertion fails in the controlling role. Worker errors are rethrown only
// after joining; no detached callers can outlive their referenced objects.
class Worker {
public:
    template<class Function>
    Worker(ReadyNotification& notice, Function function, std::function<void()> unblock = {})
        : notice_(notice), unblock_(std::move(unblock)), thread_([this, function = std::move(function)] {
            try { function(); } catch (...) { error_ = std::current_exception(); }
        }) {}
    ~Worker() {
        if (unblock_) unblock_();
        notice_.close();
        if (thread_.joinable()) thread_.join();
    }
    void join() {
        if (thread_.joinable()) thread_.join();
        if (error_) std::rethrow_exception(error_);
    }
private:
    ReadyNotification& notice_;
    std::function<void()> unblock_;
    std::exception_ptr error_;
    std::thread thread_;
};

Token armed(ReadyNotification& notice) {
    const auto result = notice.arm();
    require(result.status == Status::Ok && static_cast<bool>(result.token), "arm returns a real token");
    return result.token;
}

void initial_state_and_accounting() {
    ReadyNotification notice;
    const auto state = notice.state();
    require(state.domain != 0 && state.last_generation == 0 && !state.current && !state.armed &&
            !state.ready && !state.waiting && !state.closed, "new domain starts unarmed without fabricated readiness");
    require(notice.notify({}) == Status::NotCurrent, "empty signal rejected");
    require(notice.wait_until({}, expired_deadline()) == Status::NotCurrent, "empty wait rejected before timeout");
    require(notice.abandon({}) == Status::NotCurrent, "empty abandon rejected");
    const auto accounting = ReadyNotification::accounting();
    require(ReadyNotification::metadata_bytes() == sizeof(ReadyNotification) &&
            accounting.object_bytes == sizeof(ReadyNotification) && accounting.token_bytes == sizeof(Token) &&
            accounting.state_value_bytes == sizeof(notification::State) &&
            accounting.shared_domain_counter_bytes == sizeof(std::atomic<std::uint64_t>),
            "reported inline accounting follows actual ABI sizes");
    for (const auto config : {notification::Config{0, 1}, notification::Config{1, 0}}) {
        bool rejected = false;
        try { ReadyNotification invalid(config); } catch (const std::invalid_argument&) { rejected = true; }
        require(rejected, "zero counter budgets rejected");
    }
}

void signal_before_wait_and_duplicate_coalescing() {
    ReadyNotification notice;
    const auto token = armed(notice);
    require(notice.arm().status == Status::Busy, "one armed generation uses sole credit");
    require(notice.notify(token) == Status::Ok, "signal before wait is retained");
    require(notice.notify(token) == Status::AlreadyReady, "duplicate signal does not add credits");
    require(notice.wait_until(token, expired_deadline()) == Status::Ready, "already ready wins over expired deadline");
    require(notice.state().last_generation == token.generation && !notice.state().armed,
            "consumption does not reset generation");
    require(notice.wait_until(token, safety_deadline()) == Status::NotCurrent, "consumed token cannot be consumed twice");
    require(notice.notify(token) == Status::NotCurrent, "consumed token cannot signal future work");
    const auto next = armed(notice);
    require(next.domain == token.domain && next.generation == token.generation + 1, "next generation is monotonic");
    require(notice.notify(token) == Status::NotCurrent && notice.wait_until(token, expired_deadline()) == Status::NotCurrent,
            "previous generation cannot signal or consume newly armed interest");
    require(notice.state().current == next && !notice.state().ready, "stale operations preserve current unready generation");
    require(notice.abandon(next) == Status::Ok, "new interest can be abandoned");
}

void signal_after_wait_handoff() {
    ReadyNotification notice;
    const auto token = armed(notice);
    std::array<std::uint8_t, 256> payload{};
    Worker reader(notice, [&] {
        require(notice.wait_until(token, safety_deadline()) == Status::Ready, "blocked waiter observes signal");
        for (std::size_t i = 0; i < payload.size(); ++i) {
            require(payload[i] == static_cast<std::uint8_t>((i * 37U + 11U) % 256U),
                    "writes before notification are visible after synchronized readiness");
            checked_bytes.fetch_add(1, std::memory_order_relaxed);
        }
    });
    await([&] { return notice.state().waiting; }, "waiter did not reach guarded wait handoff");
    // state() acquires the same mutex as wait. Seeing waiting=true proves the
    // reader released it into the CV wait, without a sleep or guessed delay.
    for (std::size_t i = 0; i < payload.size(); ++i)
        payload[i] = static_cast<std::uint8_t>((i * 37U + 11U) % 256U);
    require(notice.notify(token) == Status::Ok, "signal during wait succeeds");
    reader.join();
    require(!notice.state().waiting && !notice.state().armed, "completed wait leaves no pending credit");
}

void acknowledged_spurious_wakes() {
    ReadyNotification notice;
    const auto token = armed(notice);
    std::atomic<bool> returned{false};
    Worker reader(notice, [&] {
        require(notice.wait_until(token, safety_deadline()) == Status::Ready, "spurious wake cannot fabricate readiness or timeout");
        returned.store(true, std::memory_order_release);
    });
    await([&] { return notice.state().waiting; }, "spurious test waiter not ready");
    require(notice.arm().status == Status::Busy && notice.abandon(token) == Status::Busy &&
            notice.wait_until(token, expired_deadline()) == Status::Busy,
            "active waiter rejects a second consumer operation without abandoning interest");
    for (unsigned attempt = 0; attempt < 8U; ++attempt) {
        const auto previous = notice.state().predicate_checks;
        ReadyNotificationTestAccess::spurious_wake(notice);
        await([&] { return notice.state().predicate_checks > previous; }, "false predicate was not rechecked after wake");
        const auto state = notice.state();
        require(state.waiting && state.armed && !state.ready && !returned.load(std::memory_order_acquire),
                "acknowledged false-ready wake keeps waiter and generation intact");
    }
    require(notice.notify(token) == Status::Ok, "real signal follows acknowledged spurious wakes");
    reader.join();
    require(returned.load(std::memory_order_acquire), "reader completes only after actual predicate change");
}

void sticky_close_before_and_during_wait() {
    {
        ReadyNotification notice;
        const auto token = armed(notice);
        require(notice.notify(token) == Status::Ok, "ready before close");
        notice.close();
        notice.close();
        require(notice.wait_until(token, expired_deadline()) == Status::Closed, "close wins over ready and timeout");
        require(notice.wait_until({}, expired_deadline()) == Status::Closed, "close wins over invalid token");
        require(notice.arm().status == Status::Closed && notice.notify(token) == Status::Closed &&
                notice.abandon(token) == Status::Closed, "close is sticky across every mutating operation");
        require(notice.state().closed && !notice.state().armed && !notice.state().ready, "closed state drops notification interest");
    }
    ReadyNotification notice;
    const auto token = armed(notice);
    Worker reader(notice, [&] { require(notice.wait_until(token, safety_deadline()) == Status::Closed,
                                         "controller close wakes blocked waiter without granting source work"); });
    await([&] { return notice.state().waiting; }, "close test waiter not ready");
    notice.close();
    reader.join();
    require(!notice.state().waiting && notice.state().closed, "wait cleared before joined destruction");
}

void timeout_retains_generation_and_abandon_is_explicit() {
    ReadyNotification notice;
    const auto token = armed(notice);
    require(notice.wait_until(token, expired_deadline()) == Status::TimedOut, "expired unready wait times out");
    require(notice.state().armed && notice.state().current == token && !notice.state().waiting,
            "timeout retains the exact generation without a waiter");
    require(notice.arm().status == Status::Busy, "timed-out request still owns its notification slot");
    require(notice.notify(token) == Status::Ok, "late readiness retains original token");
    require(notice.wait_until(token, expired_deadline()) == Status::Ready, "retry can consume readiness despite expired deadline");
    const auto abandoned = armed(notice);
    require(notice.abandon(abandoned) == Status::Ok, "explicit abandon frees only notification interest");
    require(notice.notify(abandoned) == Status::NotCurrent && notice.wait_until(abandoned, expired_deadline()) == Status::NotCurrent,
            "abandoned generation cannot reappear");
    const auto next = armed(notice);
    require(next.generation == abandoned.generation + 1, "abandon never resets generation");
    // This exercises a real clock deadline without a notification. No elapsed
    // time, scheduler precision or minimum blocking interval is asserted.
    require(notice.wait_until(next, Clock::now() + std::chrono::milliseconds(1)) == Status::TimedOut,
            "unready wait expires at an actual clock deadline");
    require(notice.state().current == next && !notice.state().waiting, "clock timeout leaves generation retained and caller out of wait");
    require(notice.abandon(next) == Status::Ok, "final generation abandoned");
}

void stale_future_and_reconstructed_domains() {
    Token old{};
    {
        ReadyNotification notice;
        old = armed(notice);
        for (const auto wrong : {Token{}, Token{old.domain, 0}, Token{old.domain, old.generation + 1},
                                  Token{old.domain + 1, old.generation}}) {
            require(notice.notify(wrong) == Status::NotCurrent, "future/foreign signal rejected");
            require(notice.wait_until(wrong, expired_deadline()) == Status::NotCurrent, "future/foreign wait rejected");
            require(notice.abandon(wrong) == Status::NotCurrent, "future/foreign abandon rejected");
            require(notice.state().current == old && !notice.state().ready, "invalid token cannot mutate current interest");
        }
        require(notice.abandon(old) == Status::Ok, "old domain interest discarded before destruction");
    }
    ReadyNotification replacement;
    const auto current = armed(replacement);
    require(current.domain != old.domain && current.generation == old.generation, "reconstruction changes domain even when generation matches");
    require(replacement.notify(old) == Status::NotCurrent && replacement.wait_until(old, expired_deadline()) == Status::NotCurrent,
            "old domain cannot cause ABA readiness");
    require(replacement.abandon(current) == Status::Ok, "replacement cleanup");
}

void generation_and_predicate_exhaustion_do_not_wrap() {
    ReadyNotification notice({2, 2});
    const auto first = armed(notice);
    require(notice.wait_until(first, expired_deadline()) == Status::TimedOut, "first predicate check consumed");
    require(notice.wait_until(first, expired_deadline()) == Status::TimedOut, "second predicate check consumed");
    require(notice.wait_until(first, expired_deadline()) == Status::CounterExhausted, "predicate budget refuses wrap");
    require(notice.state().predicate_checks == 2 && notice.state().current == first, "exhaustion retains identity and exact counter");
    require(notice.notify(first) == Status::Ok && notice.wait_until(first, expired_deadline()) == Status::Ready,
            "already-ready state still wins over predicate exhaustion");
    const auto second = armed(notice);
    require(second.generation == 2 && notice.wait_until(second, expired_deadline()) == Status::CounterExhausted,
            "new generation does not reset lifetime predicate budget");
    require(notice.abandon(second) == Status::Ok, "exhausted interest explicitly abandoned");
    const auto overflow = notice.arm();
    require(overflow.status == Status::CounterExhausted && !overflow.token && notice.state().last_generation == 2,
            "generation overflow returns no wrapped token");
    notice.close();
    require(notice.arm().status == Status::Closed, "close still wins over exhausted counters");
}

void local_domain_overflow_and_concurrent_uniqueness() {
    const auto maximum = (std::numeric_limits<std::uint64_t>::max)();
    std::atomic<std::uint64_t> local{maximum - 1};
    require(ReadyNotificationTestAccess::local_domain(local, maximum) == maximum, "last domain value can be reserved once");
    bool rejected = false;
    try { (void)ReadyNotificationTestAccess::local_domain(local, maximum); }
    catch (const std::overflow_error&) { rejected = true; }
    require(rejected && local.load() == maximum, "domain allocator refuses wrap and never resets");
    std::atomic<std::uint64_t> concurrent{0};
    std::array<std::uint64_t, 64> values{};
    std::array<std::exception_ptr, 4> errors{};
    std::array<std::thread, 4> threads;
    try {
        for (std::size_t index = 0; index < threads.size(); ++index) {
            threads[index] = std::thread([&, index] {
                try {
                    for (std::size_t n = 0; n < 16; ++n)
                        values[index * 16 + n] = ReadyNotificationTestAccess::local_domain(concurrent, 64);
                } catch (...) { errors[index] = std::current_exception(); }
            });
        }
    } catch (...) {
        for (auto& thread : threads) if (thread.joinable()) thread.join();
        throw;
    }
    for (auto& thread : threads) thread.join();
    for (const auto& error : errors) if (error) std::rethrow_exception(error);
    std::sort(values.begin(), values.end());
    for (std::size_t index = 0; index < values.size(); ++index)
        require(values[index] == index + 1, "concurrent domain reservations are unique and gap-free");
    require(concurrent.load() == 64, "local counter preserves all bounded reservations");
}

// A bounded one-message channel is test scaffolding, not the candidate's API.
class Handoff {
public:
    void post(Token token, unsigned sequence) {
        std::lock_guard<std::mutex> lock(mutex_);
        token_ = token; sequence_ = sequence; posted_ = true;
        cv_.notify_all();
    }
    std::pair<Token, unsigned> receive() {
        std::unique_lock<std::mutex> lock(mutex_);
        if (!cv_.wait_until(lock, safety_deadline(), [&] { return posted_ || closed_; }) || closed_)
            throw std::runtime_error("test handoff stopped before all controlled iterations");
        posted_ = false;
        return {token_, sequence_};
    }
    void acknowledged(unsigned sequence) {
        std::lock_guard<std::mutex> lock(mutex_);
        acknowledged_ = sequence; cv_.notify_all();
    }
    void await_ack(unsigned sequence) {
        std::unique_lock<std::mutex> lock(mutex_);
        if (!cv_.wait_until(lock, safety_deadline(), [&] { return acknowledged_ >= sequence || closed_; }) || closed_)
            throw std::runtime_error("test producer did not acknowledge controlled notification");
    }
    void close() { std::lock_guard<std::mutex> lock(mutex_); closed_ = true; cv_.notify_all(); }
private:
    std::mutex mutex_;
    std::condition_variable cv_;
    Token token_{};
    unsigned sequence_ = 0, acknowledged_ = 0;
    bool posted_ = false, closed_ = false;
};

void repeated_bounded_cross_thread_lifecycle() {
    ReadyNotification notice;
    Handoff channel;
    std::array<std::uint32_t, 64> payload{};
    Worker producer(notice, [&] {
        for (unsigned index = 0; index < 64U; ++index) {
            const auto message = channel.receive();
            require(message.second == index + 1, "test handoff sequence is exact");
            if (index % 2U != 0) await([&] { return notice.state().waiting || notice.state().closed; }, "lifecycle consumer did not wait");
            payload[index] = (index + 1U) * 997U;
            require(notice.notify(message.first) == Status::Ok, "one exact signal per bounded generation");
            channel.acknowledged(index + 1);
        }
    }, [&] { channel.close(); });
    for (unsigned index = 0; index < 64U; ++index) {
        const auto token = armed(notice);
        require(token.generation == index + 1, "independent generation model matches current arm");
        channel.post(token, index + 1);
        if (index % 2U == 0) channel.await_ack(index + 1);
        require(notice.wait_until(token, safety_deadline()) == Status::Ready, "both controlled signal orders complete");
        require(payload[index] == (index + 1U) * 997U, "cross-thread payload follows actual readiness");
        channel.await_ack(index + 1);
    }
    producer.join();
    require(!notice.state().armed && !notice.state().waiting && notice.state().last_generation == 64,
            "bounded lifecycle has no pending generation after joined completion");
}

void joined_destruction_after_controller_stop() {
    for (unsigned iteration = 0; iteration < 8U; ++iteration) {
        auto notice = std::make_unique<ReadyNotification>();
        const auto token = armed(*notice);
        {
            Worker reader(*notice, [&] {
                require(notice->wait_until(token, safety_deadline()) == Status::Closed,
                        "each controlled stop wakes before joined destruction");
            });
            await([&] { return notice->state().waiting; }, "destruction test waiter not waiting");
            notice->close();
            reader.join();
        }
        require(!notice->state().waiting, "no caller remains inside wait at destruction");
        notice.reset();
    }
}

struct MailboxCleanup {
    coordinator::Mailbox& mailbox;
    coordinator::Ticket ticket;
    ~MailboxCleanup() {
        mailbox.close();
        const auto last = (std::numeric_limits<coordinator::Tick>::max)();
        for (unsigned n = 0; n < 8U && !mailbox.shutdown_acknowledged(); ++n) {
            if (mailbox.stage() == coordinator::Stage::Ready) { auto discarded = mailbox.take(ticket, last); discarded.reset(); }
            mailbox.service(last);
        }
    }
};

void real_mailbox_ready_then_take_preserves_source_bytes() {
    slabs::ProcessBudget source_budget;
    slabs::History history(source_budget);
    coordinator::Budget metadata_budget(coordinator::kMetadataCap);
    coordinator::Mailbox mailbox(history, metadata_budget);
    ReadyNotification notice;
    const slabs::Stream stream{77, 3, 3072000, 451100000, slabs::Format::CU8};
    std::array<std::uint8_t, slabs::kSlabBytes> input{};
    for (std::size_t i = 0; i < input.size(); ++i) input[i] = static_cast<std::uint8_t>((i * 53U + 7U) % 256U);
    require(history.begin_epoch(stream) == slabs::Status::Ok && history.append(stream, 0, input.data(), input.size()) == slabs::Status::Ok,
            "real immutable source is filled before owner/client role transfer");
    input.fill(std::uint8_t{0xEE});
    const auto state = history.state();
    const slabs::Request request{stream, state.generation, state.pool_id, 19, 1000};
    const auto token = armed(notice); // Arm before work submission: essential ordering.
    const auto admitted = mailbox.submit(request, 10, 100);
    require(admitted.status == coordinator::Status::Ok, "real mailbox admits controlled request");
    MailboxCleanup cleanup{mailbox, admitted.ticket};
    Worker reader(notice, [&] {
        require(notice.wait_until(token, safety_deadline()) == Status::Ready, "real owner readiness wakes client");
        auto reply = mailbox.take(admitted.ticket, 50);
        require(reply.status() == coordinator::Status::Ok && reply.lease_info().stream == stream &&
                reply.lease_info().first_sample == 19 && reply.lease_info().end_sample == 1019 &&
                reply.lease_info().byte_count == 2000, "real reply keeps original source provenance");
        std::size_t offset = 0;
        for (std::size_t index = 0; index < reply.span_count(); ++index) {
            const auto& span = reply.span(index);
            require(span.first_sample == 19 + offset / 2, "real spans cover contiguous requested samples");
            for (std::size_t i = 0; i < span.byte_count; ++i, ++offset) {
                const auto expected = static_cast<std::uint8_t>(((38 + offset) * 53U + 7U) % 256U);
                require(offset < 2000 && span.data[i] == expected, "real source byte verified independently of notification");
                checked_bytes.fetch_add(1, std::memory_order_relaxed);
            }
        }
        require(offset == 2000, "real reply verified completely");
        notice.close();
        require(reply.span_count() > 0, "notification close cannot revoke held source ownership");
        reply.reset();
        mailbox.close();
    });
    await([&] { return notice.state().waiting; }, "real integration reader not waiting");
    require(mailbox.service(20).stage == coordinator::Stage::Acquired, "actual owner acquisition precedes notification");
    require(mailbox.service(30).stage == coordinator::Stage::Granted, "actual owner source grant precedes notification");
    require(mailbox.service(40).stage == coordinator::Stage::Ready, "only terminal real reply is notified");
    require(notice.notify(token) == Status::Ok, "matching terminal reply signal succeeds");
    reader.join();
    mailbox.service(60);
    history.reclaim();
    require(mailbox.shutdown_acknowledged() && history.state().snapshot_pinned_slabs == 0,
            "notification and source shutdown are separately drained and acknowledged");
}
} // namespace

int main() {
    try {
        initial_state_and_accounting();
        signal_before_wait_and_duplicate_coalescing();
        signal_after_wait_handoff();
        acknowledged_spurious_wakes();
        sticky_close_before_and_during_wait();
        timeout_retains_generation_and_abandon_is_explicit();
        stale_future_and_reconstructed_domains();
        generation_and_predicate_exhaustion_do_not_wrap();
        local_domain_overflow_and_concurrent_uniqueness();
        repeated_bounded_cross_thread_lifecycle();
        joined_destruction_after_controller_stop();
        real_mailbox_ready_then_take_preserves_source_bytes();
        std::cout << "12 readiness notification groups passed; " << checks.load() << " checks; "
                  << checked_bytes.load() << " independent source bytes. NDEBUG checks remain active.\n"
                  << "Object bytes=" << ReadyNotification::metadata_bytes()
                  << "; module domain counter bytes=" << ReadyNotification::accounting().shared_domain_counter_bytes
                  << ". OS synchronization allocation overhead is not measured. No performance claim.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Readiness notification test failure: " << error.what() << '\n';
        return 1;
    }
}
