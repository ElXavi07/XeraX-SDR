// SPDX-License-Identifier: GPL-3.0-or-later
#include "iq_coordinator.h"

#include <atomic>
#include <new>
#include <stdexcept>
#include <utility>

namespace xerax::experiment::coordinator {
namespace detail {
struct Control {
    std::atomic<Stage> stage{Stage::Idle};
    std::atomic<bool> cancel{false};
    std::atomic<bool> closing{false};
    std::atomic<bool> released{false};
    Config config;
    MetadataStats metadata{};
    Tick deadline = 0;
    ReplyInfo reply{};
    slabs::Lease lease{};
    explicit Control(Config value) : config(value) {}
};

// allocate_shared invokes allocate synchronously during construction. The
// observer is NEVER dereferenced during delayed deallocation (including when
// weak ticket identities outlive both the mailbox facade and Control object).
template<class T> struct CountingAllocator {
    using value_type = T;
    std::size_t* observed;
    std::size_t cap;
    CountingAllocator(std::size_t* count, std::size_t limit) noexcept : observed(count), cap(limit) {}
    template<class U> CountingAllocator(const CountingAllocator<U>& other) noexcept
        : observed(other.observed), cap(other.cap) {}
    T* allocate(std::size_t count) {
        if (count > cap / sizeof(T)) throw std::invalid_argument("Coordinator metadata cap exceeded");
        const auto bytes = count * sizeof(T);
        if (*observed > cap - bytes) throw std::invalid_argument("Coordinator metadata cap exceeded");
        auto* memory = static_cast<T*>(::operator new(bytes));
        *observed += bytes;
        return memory;
    }
    void deallocate(T* memory, std::size_t) noexcept { ::operator delete(memory); }
    template<class U> bool operator==(const CountingAllocator<U>& other) const noexcept { return observed == other.observed; }
    template<class U> bool operator!=(const CountingAllocator<U>& other) const noexcept { return !(*this == other); }
};

Status gate(const Control& control, Tick now) noexcept {
    if (control.closing.load(std::memory_order_acquire)) return Status::Closed;
    if (control.cancel.load(std::memory_order_acquire)) return Status::Cancelled;
    if (now >= control.deadline) return Status::DeadlineExpired;
    return Status::Ok;
}
void discard(Control& control, Status status) noexcept {
    control.lease.reset();
    control.reply.status = status;
    control.reply.source_status = slabs::Status::NoEpoch;
}
} // namespace detail

Reply::~Reply() { reset(); }
Reply::Reply(Reply&& other) noexcept
    : info_(std::move(other.info_)), lease_(std::move(other.lease_)), control_(std::move(other.control_)) {
    other.info_ = {};
}
Reply& Reply::operator=(Reply&& other) noexcept {
    if (this != &other) {
        reset();
        info_ = std::move(other.info_);
        lease_ = std::move(other.lease_);
        control_ = std::move(other.control_);
        other.info_ = {};
    }
    return *this;
}
void Reply::reset() noexcept {
    lease_.reset();
    if (control_) {
        // Consumer is finished with all payload before publishing completion.
        // The sole owner must acquire this flag before reusing the credit.
        control_->released.store(true, std::memory_order_release);
        control_.reset();
    }
    info_ = {};
}

Mailbox::Mailbox(slabs::History& history, Config config) : history_(history) {
    constexpr auto external = sizeof(Mailbox) + sizeof(Reply);
    if (!config.max_ticket || config.metadata_cap > kMetadataCap || config.metadata_cap <= external)
        throw std::invalid_argument("Invalid coordinator metadata/ticket profile");
    std::size_t allocated = 0;
    control_ = std::allocate_shared<detail::Control>(
        detail::CountingAllocator<detail::Control>(&allocated, config.metadata_cap - external), config);
    control_->metadata = {allocated, sizeof(Mailbox), sizeof(Reply), allocated + external, config.metadata_cap};
}
Mailbox::~Mailbox() = default;

bool Mailbox::client_tick(Tick now) noexcept {
    if (has_client_tick_ && now < last_client_tick_) return false;
    has_client_tick_ = true;
    last_client_tick_ = now;
    return true;
}
bool Mailbox::owner_tick(Tick now) noexcept {
    if (has_owner_tick_ && now < last_owner_tick_) return false;
    has_owner_tick_ = true;
    last_owner_tick_ = now;
    return true;
}

Submission Mailbox::submit(const slabs::Request& request, Tick now, Tick deadline) {
    auto& control = *control_;
    if (control.closing.load(std::memory_order_acquire)) return {Status::Closed, {}};
    if (!client_tick(now)) return {Status::TickRegression, {}};
    if (now >= deadline) return {Status::DeadlineExpired, {}};
    if (client_ticket_ == control.config.max_ticket) return {Status::CounterExhausted, {}};
    auto expected = Stage::Idle;
    // Owner's release of Idle acknowledges all old reads/moves and completion.
    // Client acquire prevents overwriting old storage before that acknowledgement.
    if (!control.stage.compare_exchange_strong(expected, Stage::Submitting,
                                               std::memory_order_acq_rel, std::memory_order_acquire))
        return {expected == Stage::Closed ? Status::Closed : Status::Busy, {}};
    ++client_ticket_;
    const Ticket ticket(client_ticket_, control_);
    control.cancel.store(false, std::memory_order_relaxed);
    control.released.store(false, std::memory_order_relaxed);
    control.deadline = deadline;
    control.reply = {};
    control.reply.ticket = ticket;
    control.reply.request = request;
    control.reply.submitted_check_tick = now;
    // Publish all ordinary request fields to the owner that acquires Pending.
    control.stage.store(Stage::Pending, std::memory_order_release);
    return {Status::Ok, ticket};
}

Status Mailbox::cancel(const Ticket& ticket) noexcept {
    if (!ticket || !ticket.belongs_to(control_) || ticket.sequence() != client_ticket_) return Status::NotCurrent;
    const auto phase = control_->stage.load(std::memory_order_acquire);
    if (phase != Stage::Pending && phase != Stage::Acquired && phase != Stage::Granted && phase != Stage::Ready)
        return Status::TooLate;
    control_->cancel.store(true, std::memory_order_release);
    return Status::Ok;
}

Reply Mailbox::take(const Ticket& ticket, Tick now) {
    Reply result;
    if (!ticket || !ticket.belongs_to(control_) || ticket.sequence() != client_ticket_) {
        result.info_.status = Status::NotCurrent;
        return result;
    }
    if (!client_tick(now)) { result.info_.status = Status::TickRegression; return result; }
    auto& control = *control_;
    const auto phase = control.stage.load(std::memory_order_acquire);
    if (phase != Stage::Ready) {
        result.info_.status = phase == Stage::Closed ? Status::Closed : Status::Empty;
        return result;
    }
    // Ready's acquire exposes a complete immutable reply and move-only lease.
    // Owner does not touch ordinary slot fields until Consumed/released is acquired.
    if (now < control.reply.publish_check_tick) {
        result.info_.status = Status::TickRegression;
        return result;
    }
    control.stage.store(Stage::Taking, std::memory_order_release);
    const auto decision = detail::gate(control, now);
    if (decision != Status::Ok) detail::discard(control, decision);
    result.info_ = control.reply;
    result.info_.take_check_tick = now;
    if (result.info_.status == Status::Ok) {
        result.lease_ = std::move(control.lease);
        result.control_ = control_;
        // Publish completion of the move. Only the taken result owns source bytes.
        control.stage.store(Stage::Held, std::memory_order_release);
    } else {
        control.lease.reset();
        // Returning an error still requires owner's acknowledgement before reuse.
        control.stage.store(Stage::Consumed, std::memory_order_release);
    }
    return result;
}

void Mailbox::close() noexcept { control_->closing.store(true, std::memory_order_release); }

Step Mailbox::service(Tick now) {
    auto& control = *control_;
    auto phase = control.stage.load(std::memory_order_acquire);
    if (phase == Stage::Closed) return {Status::Closed, Stage::Closed};
    if (!owner_tick(now)) return {Status::TickRegression, phase};
    switch (phase) {
    case Stage::Idle:
        if (control.closing.load(std::memory_order_acquire)) {
            auto expected = Stage::Idle;
            if (control.stage.compare_exchange_strong(expected, Stage::Closed,
                                                      std::memory_order_acq_rel, std::memory_order_acquire))
                return {Status::Closed, Stage::Closed};
            return {Status::Busy, expected};
        }
        return {Status::Empty, Stage::Idle};
    case Stage::Pending:
        if (now < control.reply.submitted_check_tick) return {Status::TickRegression, Stage::Pending};
        control.reply.status = detail::gate(control, now);
        control.stage.store(Stage::Acquired, std::memory_order_release);
        return {Status::Ok, Stage::Acquired};
    case Stage::Acquired: {
        control.reply.grant_check_tick = now;
        const auto decision = detail::gate(control, now);
        if (decision != Status::Ok) detail::discard(control, decision);
        else {
            control.lease = history_.snapshot(control.reply.request);
            control.reply.source_status = control.lease.status();
            control.reply.status = control.lease ? Status::Ok : Status::SourceError;
        }
        control.stage.store(Stage::Granted, std::memory_order_release);
        return {Status::Ok, Stage::Granted};
    }
    case Stage::Granted: {
        const auto decision = detail::gate(control, now);
        if (decision != Status::Ok) {
            detail::discard(control, decision);
            history_.reclaim();
        }
        control.reply.publish_check_tick = now;
        // Publish reply ordinary fields + source ownership to client acquire.
        control.stage.store(Stage::Ready, std::memory_order_release);
        return {Status::Ok, Stage::Ready};
    }
    case Stage::Held:
        if (control.closing.load(std::memory_order_acquire)) {
            if (control.released.load(std::memory_order_acquire)) history_.reclaim();
            // No reply remains in this slot. A held consumer keeps its own source
            // lease + shared control token; shutdown never revokes those bytes.
            control.stage.store(Stage::Closed, std::memory_order_release);
            return {Status::Closed, Stage::Closed};
        }
        if (!control.released.load(std::memory_order_acquire)) return {Status::Busy, Stage::Held};
        [[fallthrough]];
    case Stage::Consumed:
        history_.reclaim();
        control.lease.reset();
        control.reply = {};
        phase = control.closing.load(std::memory_order_acquire) ? Stage::Closed : Stage::Idle;
        control.stage.store(phase, std::memory_order_release);
        return {phase == Stage::Closed ? Status::Closed : Status::Ok, phase};
    case Stage::Submitting: case Stage::Ready: case Stage::Taking:
        return {Status::Busy, phase};
    case Stage::Closed:
        return {Status::Closed, Stage::Closed};
    }
    return {Status::Busy, phase};
}

Stage Mailbox::stage() const noexcept { return control_->stage.load(std::memory_order_acquire); }
bool Mailbox::shutdown_acknowledged() const noexcept { return stage() == Stage::Closed; }
MetadataStats Mailbox::metadata() const noexcept { return control_->metadata; }

} // namespace xerax::experiment::coordinator
