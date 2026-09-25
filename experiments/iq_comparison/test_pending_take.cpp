// SPDX-License-Identifier: GPL-3.0-or-later
// Independent observer-adapter checks using supplied ticks, never wall clocks.
#include "pending_take.h"
#include <array>
#include <cstdint>
#include <iostream>
#include <initializer_list>
#include <limits>
#include <stdexcept>

namespace {
namespace slabs = xerax::experiment::slabs;
namespace coord = xerax::experiment::coordinator;
namespace comparison = xerax::experiment::comparison;
std::size_t checks = 0;
std::size_t bytes_checked = 0;

void require(bool value, const char* message) {
    ++checks;
    if (!value) throw std::runtime_error(message);
}

struct Fixture {
    slabs::ProcessBudget source_budget;
    slabs::History history{source_budget};
    coord::Budget metadata_budget{coord::kMetadataCap};
    coord::Mailbox mailbox{history, metadata_budget};
    coord::Ticket pending;
    coord::Ticket cleanup_ticket;
    slabs::Stream stream{11, 7, 3072000, 451100000, slabs::Format::CU8};
    std::array<std::uint8_t, slabs::kSlabBytes> original{};

    Fixture() {
        for (std::size_t n = 0; n < original.size(); ++n)
            original[n] = static_cast<std::uint8_t>((n * 29U + 17U) % 256U);
        require(history.begin_epoch(stream) == slabs::Status::Ok, "source starts");
        require(history.append(stream, 0, original.data(), original.size()) == slabs::Status::Ok,
                "known independent bytes accepted");
    }
    ~Fixture() {
        // Failure cleanup deliberately uses the core API rather than the helper
        // being tested. The real current ticket is kept separately in stale tests.
        mailbox.close();
        const auto last = (std::numeric_limits<coord::Tick>::max)();
        for (unsigned n = 0; n < 8U && !mailbox.shutdown_acknowledged(); ++n) {
            if (mailbox.stage() == coord::Stage::Ready) {
                auto reply = mailbox.take(cleanup_ticket, last);
                reply.reset();
            }
            mailbox.service(last);
        }
    }
    slabs::Request request() const {
        const auto state = history.state();
        return {stream, state.generation, state.pool_id, 13, 1000};
    }
    void submit(const slabs::Request& wanted, coord::Tick now = 10) {
        const auto result = mailbox.submit(wanted, now, 100);
        require(result.status == coord::Status::Ok, "submission admitted");
        pending = result.ticket;
        cleanup_ticket = result.ticket;
    }
    void ready(coord::Tick first = 20) {
        require(mailbox.service(first).stage == coord::Stage::Acquired, "owner acquires");
        require(mailbox.service(first + 10).stage == coord::Stage::Granted, "owner grants");
        require(mailbox.service(first + 20).stage == coord::Stage::Ready, "owner publishes reply");
    }
    void close_ack(coord::Tick now = 60) {
        mailbox.close();
        mailbox.service(now);
        require(mailbox.shutdown_acknowledged(), "owner acknowledges drained close");
    }
    void bytes(const coord::Reply& reply) const {
        require(reply.lease_info().stream == stream && reply.lease_info().first_sample == 13 &&
                reply.lease_info().end_sample == 1013 && reply.lease_info().byte_count == 2000,
                "successful reply keeps requested interval and identity");
        std::size_t offset = 0;
        for (std::size_t n = 0; n < reply.span_count(); ++n) {
            const auto& span = reply.span(n);
            require(span.first_sample == 13 + offset / 2, "span source index is continuous");
            for (std::size_t j = 0; j < span.byte_count; ++j, ++offset) {
                require(offset < 2000 && span.data[j] == original[26 + offset], "independent byte oracle matches");
                ++bytes_checked;
            }
        }
        require(offset == 2000, "every requested byte checked");
    }
};

void empty_then_success() {
    Fixture f;
    f.submit(f.request());
    const auto identity = f.pending;
    auto empty = comparison::take_pending(f.mailbox, f.pending, 11);
    require(empty.status() == coord::Status::Empty, "pending take returns Empty");
    require(f.pending == identity && f.mailbox.stage() == coord::Stage::Pending,
            "Empty preserves the pending ticket and slot");
    f.ready();
    auto reply = comparison::take_pending(f.mailbox, f.pending, 50);
    require(reply.status() == coord::Status::Ok && !f.pending, "actual success consumes ticket");
    f.bytes(reply);
    reply.reset();
    f.close_ack();
}

struct Injected {};
void regression_exception_cleanup() {
    Fixture f;
    f.submit(f.request());
    const auto identity = f.pending;
    f.ready();
    bool caught = false;
    try {
        auto reply = comparison::take_pending(f.mailbox, f.pending, 35);
        require(reply.status() == coord::Status::TickRegression, "take before publish check is nonconsuming");
        require(f.pending == identity && f.mailbox.stage() == coord::Stage::Ready,
                "regression preserves Ready reply and exact ticket");
        require(f.history.state().snapshot_pinned_slabs > 0, "Ready source remains owned");
        throw Injected{};
    } catch (const Injected&) {
        caught = true;
        f.mailbox.close();
        auto discarded = comparison::take_pending(f.mailbox, f.pending, 50);
        require(discarded.status() == coord::Status::Closed && !f.pending,
                "fresh cleanup consumes closed reply using retained ticket");
        require(discarded.span_count() == 0, "closed cleanup exposes no payload");
        discarded.reset();
    }
    require(caught, "controlled exception reached cleanup");
    f.close_ack();
    f.history.reclaim();
    require(f.history.state().snapshot_pinned_slabs == 0, "cleanup releases source pins");
}

void stale_ticket_preserved_without_consuming_current() {
    Fixture f;
    f.submit(f.request());
    auto stale = f.pending;
    f.ready();
    auto first = comparison::take_pending(f.mailbox, f.pending, 50);
    require(first.status() == coord::Status::Ok && !f.pending, "first actual reply consumed");
    first.reset();
    require(f.mailbox.service(51).stage == coord::Stage::Idle, "credit becomes reusable");
    f.submit(f.request(), 52);
    f.ready(53);
    const auto stale_identity = stale;
    const auto current_identity = f.pending;
    auto wrong = comparison::take_pending(f.mailbox, stale, 74);
    require(wrong.status() == coord::Status::NotCurrent && stale == stale_identity,
            "NotCurrent does not erase caller's unconsumed token");
    require(f.pending == current_identity && f.mailbox.stage() == coord::Stage::Ready,
            "wrong token cannot consume newer reply");
    auto current = comparison::take_pending(f.mailbox, f.pending, 75);
    require(current.status() == coord::Status::Ok && !f.pending, "actual current ticket still consumes reply");
    f.bytes(current);
    current.reset();
    f.close_ack(80);
}

void consuming_error_statuses() {
    for (const auto status : {coord::Status::Closed, coord::Status::Cancelled,
                              coord::Status::DeadlineExpired, coord::Status::SourceError}) {
        Fixture f;
        auto request = f.request();
        if (status == coord::Status::SourceError) request.first_sample = 1000000;
        f.submit(request);
        if (status == coord::Status::Cancelled)
            require(f.mailbox.cancel(f.pending) == coord::Status::Ok, "current cancellation requested");
        f.ready();
        if (status == coord::Status::Closed) f.mailbox.close();
        const coord::Tick take_tick = status == coord::Status::DeadlineExpired ? 100 : 50;
        auto reply = comparison::take_pending(f.mailbox, f.pending, take_tick);
        require(reply.status() == status && !f.pending, "consuming error reply clears exact pending token");
        require(reply.span_count() == 0, "rejected reply has no owned payload");
        reply.reset();
        f.close_ack(take_tick + 1);
    }
}
} // namespace

int main() {
    try {
        empty_then_success();
        regression_exception_cleanup();
        stale_ticket_preserved_without_consuming_current();
        consuming_error_statuses();
        std::cout << "4 pending-take groups passed; " << checks << " checks; " << bytes_checked
                  << " independently checked bytes. Supplied ticks only; no timing claim.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Pending-take test failure: " << error.what() << '\n';
        return 1;
    }
}
