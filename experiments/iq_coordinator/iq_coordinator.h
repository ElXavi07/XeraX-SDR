// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include "immutable_slabs.h"
#include <cstddef>
#include <cstdint>
#include <limits>
#include <memory>

namespace xerax::experiment::coordinator {

using Tick = std::uint64_t;
inline constexpr std::size_t kMetadataCap = 8 * 1024;
namespace detail { struct Control; }
class Mailbox;

// An opaque domain identity plus sequence. Weak ownership preserves control-block
// identity across facade destruction without pinning the payload or comparing
// recycled addresses. Retained tickets keep that control allocation alive until
// their destruction; they are not serializable numeric handles.
class Ticket {
public:
    Ticket() = default;
    std::uint64_t sequence() const noexcept { return sequence_; }
    explicit operator bool() const noexcept { return sequence_ != 0; }
    bool operator==(const Ticket& other) const noexcept {
        return sequence_ == other.sequence_ && !domain_.owner_before(other.domain_) && !other.domain_.owner_before(domain_);
    }
    bool operator!=(const Ticket& other) const noexcept { return !(*this == other); }
private:
    friend class Mailbox;
    Ticket(std::uint64_t sequence, const std::shared_ptr<detail::Control>& domain) noexcept
        : sequence_(sequence), domain_(domain) {}
    bool belongs_to(const std::shared_ptr<detail::Control>& domain) const noexcept {
        return !domain_.owner_before(domain) && !domain.owner_before(domain_);
    }
    std::uint64_t sequence_ = 0;
    std::weak_ptr<detail::Control> domain_;
};

enum class Stage {
    Idle, Submitting, Pending, Acquired, Granted, Ready, Taking, Held, Consumed, Closed
};
enum class Status {
    Ok, Empty, Busy, Closed, Cancelled, DeadlineExpired, CounterExhausted,
    TickRegression, NotCurrent, TooLate, SourceError
};
struct Config {
    std::uint64_t max_ticket = (std::numeric_limits<std::uint64_t>::max)();
    // Separate metadata profile; NOT silently charged to the slab arena's cap.
    std::size_t metadata_cap = kMetadataCap;
};
struct Submission {
    Status status = Status::Empty;
    Ticket ticket{};
};
struct Step {
    Status status = Status::Empty;
    Stage stage = Stage::Idle;
};
struct ReplyInfo {
    Status status = Status::Empty;
    Ticket ticket{};
    slabs::Request request{}; // Exact original request, including failed replies.
    slabs::Status source_status = slabs::Status::NoEpoch;
    Tick submitted_check_tick = 0;
    Tick grant_check_tick = 0;
    Tick publish_check_tick = 0;
    Tick take_check_tick = 0;
};
struct MetadataStats {
    std::size_t control_allocation_bytes = 0; // Actual allocate_shared request.
    std::size_t coordinator_object_bytes = 0;
    std::size_t held_reply_object_bytes = 0;
    std::size_t reserved_bytes = 0; // Sum above; one operational reply per slot.
    std::size_t metadata_cap = 0;
};

// Move-only taken result. Its spans have the same borrowed lifetime rule as a
// slab Lease. Reset publishes completion AFTER releasing source ownership.
// Release may occur on another thread after synchronized ownership transfer.
// A taken result may outlive acknowledged mailbox shutdown and both facades.
class Reply {
public:
    Reply() = default;
    ~Reply();
    Reply(Reply&& other) noexcept;
    Reply& operator=(Reply&& other) noexcept;
    Reply(const Reply&) = delete;
    Reply& operator=(const Reply&) = delete;
    Status status() const noexcept { return info_.status; }
    const ReplyInfo& info() const noexcept { return info_; }
    explicit operator bool() const noexcept { return status() == Status::Ok; }
    const slabs::LeaseInfo& lease_info() const noexcept { return lease_.info(); }
    std::size_t span_count() const noexcept { return lease_.span_count(); }
    const slabs::Span& span(std::size_t index) const & { return lease_.span(index); }
    const slabs::Span& span(std::size_t) const && = delete;
    void reset() noexcept;
private:
    friend class Mailbox;
    ReplyInfo info_{};
    slabs::Lease lease_;
    std::shared_ptr<detail::Control> control_;
};

// Two roles only: a single client calls submit/cancel/take/close, and the same
// sole owner as slabs::History calls service. No method spawns a worker or reads
// a clock. Keep Mailbox and History alive until roles stop/join AND shutdown is
// acknowledged. Destroy on a control thread. Only a taken Reply can outlive it.
class Mailbox {
public:
    explicit Mailbox(slabs::History& history, Config config = {});
    ~Mailbox();
    Mailbox(const Mailbox&) = delete;
    Mailbox& operator=(const Mailbox&) = delete;
    Mailbox(Mailbox&&) = delete;
    Mailbox& operator=(Mailbox&&) = delete;

    // CLIENT ROLE. now/deadline are supplied ticks in ONE shared monotonic domain.
    // Deadline is expired at now >= deadline, including equality. Ticks must be
    // nondecreasing per role; no arithmetic is performed on deadline values.
    // Failed admission creates no ticket/reply. One credit spans pending,
    // granted, taken/held, release and owner acknowledgement before Idle reuse.
    Submission submit(const slabs::Request& request, Tick now, Tick deadline);
    // Current pending/acquired/granted/ready request only. Cancellation after
    // take returns TooLate and NEVER revokes the consumer's lease. Stale ticket
    // returns NotCurrent and cannot modify a newer slot.
    Status cancel(const Ticket& ticket) noexcept;
    // Checks now >= publish_check_tick in addition to per-client monotonicity.
    // Closed > Cancelled > DeadlineExpired > source outcome. These checks also
    // apply to an already Ready success, releasing its pins on rejection.
    // Empty/NotCurrent/TickRegression do not consume or alter the reply slot.
    Reply take(const Ticket& ticket, Tick now);
    // Sticky close request: rejects new submissions, but never drops a pending
    // reply. The client must take error/success responses to drain that slot.
    void close() noexcept;

    // OWNER ROLE. Exactly one phase per call, providing deterministic test pauses:
    // Pending->Acquired->Granted->Ready. Deadline/cancel/close checked at each.
    // Acquiring also requires now >= submission tick; otherwise TickRegression
    // leaves Pending intact. A retune AFTER grant does not relabel/revoke old
    // pinned data: source provenance remains the request's original epoch.
    Step service(Tick now);

    // Read-only atomic/immutable observations; these do not expose payload.
    Stage stage() const noexcept;
    bool shutdown_acknowledged() const noexcept;
    MetadataStats metadata() const noexcept;

    // Normal Held reuse waits for Reply.reset + owner acknowledgement. On close,
    // Held->Closed acknowledges MAILBOX quiescence, not reclamation of a consumer
    // lease: the independently shared completion token and slab lease survive.
    // Preemption after any supplied-tick check is unmeasured; no hard-deadline,
    // actual-publication timestamp, lock-free or performance guarantee is made.
private:
    bool client_tick(Tick now) noexcept;
    bool owner_tick(Tick now) noexcept;
    slabs::History& history_;
    std::shared_ptr<detail::Control> control_;
    std::uint64_t client_ticket_ = 0; // Accessed by client role only.
    Tick last_client_tick_ = 0, last_owner_tick_ = 0;
    bool has_client_tick_ = false, has_owner_tick_ = false;
};

} // namespace xerax::experiment::coordinator
