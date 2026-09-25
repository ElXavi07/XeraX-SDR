// SPDX-License-Identifier: GPL-3.0-or-later
// Independent coordinator checks: source bytes are generated before submission,
// and expected intervals never come from a returned candidate snapshot.
// Explicit owner steps and atomic handshakes create the tested interleavings.
// There are no sleeps, wall-clock thresholds, radio signals or speed claims.

#include "iq_coordinator.h"
#include "test_support.h"

namespace {
using independent::require;
using independent::no_allocation;
using independent::check_bytes;
namespace slabs = xerax::experiment::slabs;
namespace coord = xerax::experiment::coordinator;
using coord::Mailbox;
using coord::Reply;
using coord::Status;
using coord::Stage;
using coord::Tick;
using coord::Ticket;

static_assert(!std::is_copy_constructible_v<Reply> && !std::is_copy_assignable_v<Reply>);
static_assert(std::is_nothrow_move_constructible_v<Reply> && std::is_nothrow_move_assignable_v<Reply>);

void status(Status actual, Status expected, const char* context) {
    require(actual == expected, context);
}

bool same_request(const slabs::Request& first, const slabs::Request& second) {
    return first.stream == second.stream && first.pool_id == second.pool_id &&
           first.generation == second.generation && first.first_sample == second.first_sample &&
           first.sample_count == second.sample_count;
}

struct Fixture {
    slabs::ProcessBudget budget;
    slabs::History history;
    Mailbox box;
    Ticket current{};

    explicit Fixture(coord::Config config = {}) : history(budget), box(history, config) {}
    ~Fixture() {
        // Always close/drain on the control thread, also after a failed assertion.
        // Tests join every worker before their Fixture's lifetime ends.
        box.close();
        for (unsigned n = 0; n < 8 && !box.shutdown_acknowledged(); ++n) {
            if (box.stage() == Stage::Ready) { auto reply = box.take(current, (std::numeric_limits<Tick>::max)()); reply.reset(); }
            box.service((std::numeric_limits<Tick>::max)());
        }
    }

    void begin(const slabs::Stream& source) {
        slabs::Status result{};
        no_allocation([&] { result = history.begin_epoch(source); });
        require(result == slabs::Status::Ok, "known source epoch accepted");
    }

    void append(const slabs::Stream& source, std::uint64_t first, std::size_t samples, std::uint64_t nonce = 1) {
        auto bytes = independent::bytes(source, first, samples, nonce);
        slabs::Status result{};
        no_allocation([&] { result = history.append(source, first, bytes.data(), bytes.size()); });
        require(result == slabs::Status::Ok, "independent continuous source data accepted");
        std::fill(bytes.begin(), bytes.end(), std::uint8_t{0xA7}); // Never rely on borrowed caller input.
    }

    void fill(const slabs::Stream& source, std::size_t slabs_count = 4, std::uint64_t first = 0,
              std::uint64_t nonce = 1) {
        begin(source);
        const auto samples = slabs::kSlabBytes / independent::width(source.format);
        for (std::size_t n = 0; n < slabs_count; ++n) append(source, first + n * samples, samples, nonce);
    }

    slabs::Request request(std::uint64_t first = 1, std::uint64_t count = 1000) const {
        const auto state = history.state();
        return {state.stream, state.generation, state.pool_id, first, count};
    }

    coord::Submission submit(const slabs::Request& request, Tick now = 10, Tick deadline = 100) {
        coord::Submission result;
        no_allocation([&] { result = box.submit(request, now, deadline); });
        if (result.status == Status::Ok) current = result.ticket;
        return result;
    }

    coord::Step step(Tick now) {
        coord::Step result;
        no_allocation([&] { result = box.service(now); });
        return result;
    }

    Reply take(Ticket ticket, Tick now) {
        Reply result;
        no_allocation([&] { result = box.take(ticket, now); });
        return result;
    }

    Status cancel(Ticket ticket) {
        Status result{};
        no_allocation([&] { result = box.cancel(ticket); });
        return result;
    }

    void ready(Tick now = 20) {
        for (unsigned n = 0; n < 3 && box.stage() != Stage::Ready; ++n) {
            const auto before = box.stage();
            const auto expected = before == Stage::Pending ? Stage::Acquired :
                                  before == Stage::Acquired ? Stage::Granted : Stage::Ready;
            require(before == Stage::Pending || before == Stage::Acquired || before == Stage::Granted,
                    "only admitted owner phases can reach Ready");
            const auto result = step(now);
            require(result.status == Status::Ok && result.stage == expected && box.stage() == expected,
                    "success and error requests both progress exactly one declared phase per call");
        }
        require(box.stage() == Stage::Ready, "bounded owner phases eventually produce exactly one reply");
    }

    void release(Reply& reply, Tick now = 40) {
        no_allocation([&] { reply.reset(); });
        step(now);
        require(box.stage() == Stage::Idle, "slot reusable only after reply reset and owner acknowledgement");
        require(history.state().snapshot_pinned_slabs == 0, "completion acknowledgement releases source pins");
    }
};

void error_reply(const Reply& reply, Status expected, Ticket ticket, const slabs::Request& request) {
    status(reply.status(), expected, "reply has the independently expected terminal failure");
    require(!reply && reply.span_count() == 0 && reply.lease_info().byte_count == 0,
            "failed reply exposes no payload or spans");
    require(reply.info().ticket == ticket && same_request(reply.info().request, request),
            "terminal error retains exact original ticket and source request provenance");
}

void expect_idle(Fixture& fixture) {
    require(fixture.box.stage() == Stage::Idle, "expected idle mailbox");
    require(fixture.history.state().snapshot_pinned_slabs == 0, "idle request has no orphan snapshot pins");
}

void exact_handoff_and_credit() {
    for (const auto format : {slabs::Format::CU8, slabs::Format::CF32LE, slabs::Format::CF32BE}) {
        Fixture f;
        const auto source = independent::stream(format);
        f.fill(source, 4, 107);
        const auto requested = f.request(108, slabs::kSlabBytes / independent::width(format) + 17);
        const auto admission = f.submit(requested);
        status(admission.status, Status::Ok, "idle client request admitted");
        require(static_cast<bool>(admission.ticket) && f.box.stage() == Stage::Pending, "submission publishes a nonzero ticket");
        status(f.submit(requested, 11).status, Status::Busy, "pending slot cannot be replaced");
        auto early = f.take(admission.ticket, 12);
        status(early.status(), Status::Empty, "pending result cannot expose unfinished reply");
        const Stage phases[] = {Stage::Acquired, Stage::Granted, Stage::Ready};
        for (unsigned index = 0; index < 3; ++index) {
            f.step(20 + index);
            require(f.box.stage() == phases[index], "healthy request follows declared three-phase handoff");
            status(f.submit(requested, 23 + index).status, Status::Busy, "owner/reply stage consumes admission credit");
        }
        require(f.history.state().snapshot_pinned_slabs > 0, "ready but untaken reply protects payload");
        auto reply = f.take(admission.ticket, 30);
        check_bytes(reply, source, requested.first_sample, requested.sample_count);
        require(same_request(reply.info().request, requested), "successful reply preserves full request");
        require(reply.info().submitted_check_tick == 10 && reply.info().grant_check_tick == 21 &&
                reply.info().publish_check_tick == 22 && reply.info().take_check_tick == 30,
                "reported check ticks name actual declared phases without invented clock measurements");
        require(f.box.stage() == Stage::Held, "taken lease keeps slot held");
        auto duplicate = f.take(admission.ticket, 31);
        status(duplicate.status(), Status::Empty, "taken reply cannot be delivered twice");
        require(!duplicate.info().ticket && duplicate.span_count() == 0, "duplicate take invents no response ownership");
        status(f.submit(requested, 31).status, Status::Busy, "consumer-held lease excludes new request");
        status(f.cancel(admission.ticket), Status::TooLate, "cancellation never revokes already-taken bytes");
        check_bytes(reply, source, requested.first_sample, requested.sample_count);
        no_allocation([&] { reply.reset(); });
        status(f.submit(requested, 32).status, Status::Busy, "completion requires owner acknowledgement before slot reuse");
        f.step(40);
        expect_idle(f);
        const auto second = f.submit(requested, 41);
        status(second.status, Status::Ok, "acknowledged completion admits new request");
        require(second.ticket.sequence() > admission.ticket.sequence(), "reused request slot changes identity");
        f.ready(42);
        auto result = f.take(second.ticket, 43);
        check_bytes(result, source, requested.first_sample, requested.sample_count);
        f.release(result, 44);
    }
}

void cancellation_at_every_handoff() {
    for (unsigned phase = 0; phase <= 3; ++phase) {
        Fixture f;
        const auto source = independent::stream();
        f.fill(source);
        const auto requested = f.request();
        const auto admission = f.submit(requested);
        for (unsigned n = 0; n < phase; ++n) f.step(20);
        status(f.cancel(admission.ticket), Status::Ok, "current untaken request accepts cancellation");
        status(f.cancel(admission.ticket), Status::Ok, "duplicate current cancellation is idempotent");
        status(f.submit(requested, 21).status, Status::Busy, "cancelled unconsumed reply still owns request slot");
        f.ready(22);
        auto reply = f.take(admission.ticket, 23);
        error_reply(reply, Status::Cancelled, admission.ticket, requested);
        f.release(reply, 24);
    }
}

void deadline_boundaries_and_maximum() {
    // Deadline equality must be expired at every owner handoff and client take.
    for (unsigned phase = 0; phase <= 3; ++phase) {
        Fixture f;
        f.fill(independent::stream());
        const auto requested = f.request();
        const auto admission = f.submit(requested, 10, 50);
        for (unsigned n = 0; n < phase; ++n) f.step(49);
        if (phase < 3) f.ready(50);
        auto reply = f.take(admission.ticket, 50);
        error_reply(reply, Status::DeadlineExpired, admission.ticket, requested);
        f.release(reply, 51);
    }
    {
        Fixture f;
        f.fill(independent::stream());
        const auto requested = f.request();
        const auto deadline = (std::numeric_limits<Tick>::max)();
        const auto admission = f.submit(requested, deadline - 1, deadline);
        status(admission.status, Status::Ok, "maximum tick deadline admission never overflows");
        f.ready(deadline - 1);
        auto reply = f.take(admission.ticket, deadline - 1);
        check_bytes(reply, requested.stream, requested.first_sample, requested.sample_count);
        f.release(reply, deadline);
    }
    {
        Fixture f;
        f.fill(independent::stream());
        const auto requested = f.request();
        const auto admission = f.submit(requested, 50, 50);
        // Expired admission can be a no-ticket rejection; it cannot be a success.
        status(admission.status, Status::DeadlineExpired, "already-expired submission rejected at equality");
        require(!admission.ticket && f.box.stage() == Stage::Idle, "expired admission creates no reply");
    }
}

void close_at_every_handoff_and_precedence() {
    for (unsigned phase = 0; phase <= 3; ++phase) {
        Fixture f;
        f.fill(independent::stream());
        const auto requested = f.request();
        const auto admission = f.submit(requested, 10, 50);
        for (unsigned n = 0; n < phase; ++n) f.step(20);
        f.cancel(admission.ticket);
        no_allocation([&] { f.box.close(); f.box.close(); });
        status(f.submit(requested, 51).status, Status::Closed, "sticky close rejects admission");
        require(!f.box.shutdown_acknowledged(), "close cannot discard unconsumed pending/ready reply");
        f.ready(51);
        auto reply = f.take(admission.ticket, 52);
        error_reply(reply, Status::Closed, admission.ticket, requested);
        no_allocation([&] { reply.reset(); });
        f.step(53);
        require(f.box.shutdown_acknowledged() && f.box.stage() == Stage::Closed,
                "closed terminal reply acknowledgement completes shutdown");
        require(f.history.state().snapshot_pinned_slabs == 0, "closed error frees any prior grant");
        f.box.close();
        f.step(54);
        require(f.box.shutdown_acknowledged(), "repeated close/service cannot reopen terminal state");
    }
    {
        Fixture f;
        f.box.close();
        f.step(0);
        require(f.box.shutdown_acknowledged(), "idle close acknowledges without an invented reply");
    }
}

void tick_regression_is_nonconsuming() {
    Fixture f;
    f.fill(independent::stream());
    const auto requested = f.request();
    const auto admission = f.submit(requested, 50, 100);
    status(f.step(49).status, Status::TickRegression, "owner acquire cannot precede request submission check");
    require(f.box.stage() == Stage::Pending, "invalid owner tick leaves request pending");
    f.step(60);
    status(f.step(59).status, Status::TickRegression, "owner ticks cannot regress");
    require(f.box.stage() == Stage::Acquired, "owner regression does not skip a handoff");
    f.step(61); f.step(62);
    auto early = f.take(admission.ticket, 61);
    status(early.status(), Status::TickRegression, "take cannot precede publication check");
    require(f.box.stage() == Stage::Ready, "invalid take retains ready reply");
    auto older = f.take(admission.ticket, 49);
    status(older.status(), Status::TickRegression, "client tick cannot precede earlier client check");
    auto reply = f.take(admission.ticket, 63);
    check_bytes(reply, requested.stream, requested.first_sample, requested.sample_count);
    f.release(reply, 64);
    status(f.submit(requested, 62).status, Status::TickRegression, "later request cannot regress client tick");
    expect_idle(f);
}

void invalid_and_stale_tickets_never_modify_current() {
    Fixture f;
    f.fill(independent::stream());
    const auto requested = f.request();
    status(f.cancel(Ticket{}), Status::NotCurrent, "zero cancellation ticket rejected");
    const auto first = f.submit(requested);
    Fixture foreign;
    foreign.fill(independent::stream());
    const auto foreign_ticket = foreign.submit(foreign.request()).ticket;
    require(foreign_ticket.sequence() == first.ticket.sequence() && foreign_ticket != first.ticket,
            "identical sequence from another coordinator is a distinct ownership domain");
    status(f.cancel(foreign_ticket), Status::NotCurrent, "foreign ticket cannot cancel current request");
    auto invalid = f.take(foreign_ticket, 11);
    status(invalid.status(), Status::NotCurrent, "foreign ticket cannot take current request");
    require(!invalid.info().ticket && invalid.span_count() == 0, "invalid ticket has no legitimate reply provenance");
    f.ready(20);
    auto reply = f.take(first.ticket, 21);
    f.release(reply, 22);
    const auto second = f.submit(requested, 23);
    require(second.ticket != first.ticket, "new generation differs from old ticket");
    status(f.cancel(first.ticket), Status::NotCurrent, "old ticket cannot cancel replacement request");
    auto stale = f.take(first.ticket, 24);
    status(stale.status(), Status::NotCurrent, "old ticket cannot consume replacement request");
    f.ready(25);
    auto current = f.take(second.ticket, 26);
    check_bytes(current, requested.stream, requested.first_sample, requested.sample_count);
    f.release(current, 27);
}

void source_changes_before_grant_and_after_grant() {
    // Before pinning: fail rather than substitute data from the new epoch.
    for (unsigned phase = 0; phase <= 1; ++phase) {
        Fixture f;
        const auto old_source = independent::stream();
        f.fill(old_source);
        const auto requested = f.request();
        const auto admission = f.submit(requested);
        if (phase) f.step(20);
        auto replacement = independent::stream(slabs::Format::CU8, 2);
        replacement.sample_rate_hz = 2400000;
        f.fill(replacement, 4, 0, 7);
        f.ready(21);
        auto reply = f.take(admission.ticket, 22);
        error_reply(reply, Status::SourceError, admission.ticket, requested);
        require(reply.info().source_status == slabs::Status::EpochMismatch, "stale source failure names exact cause");
        f.release(reply, 23);
    }
    // After pinning and while Ready: preserve exactly the old source through
    // retune, A -> B -> A public identity reuse and eviction of all current data.
    for (unsigned phase = 2; phase <= 3; ++phase) {
        Fixture f;
        const auto old_source = independent::stream();
        f.fill(old_source, 4, 0, 17);
        const auto requested = f.request();
        const auto admission = f.submit(requested);
        for (unsigned n = 0; n < phase; ++n) f.step(20);
        auto replacement = independent::stream(slabs::Format::CU8, 1);
        replacement.stream_id = old_source.stream_id + 1;
        replacement.sample_rate_hz = 2400000;
        f.fill(replacement, 2, 0, 23);
        f.fill(old_source, 150, 0, 99);
        require(f.history.state().first_sample > requested.first_sample + requested.sample_count,
                "new history fully evicts original request interval");
        f.ready(21);
        auto reply = f.take(admission.ticket, 22);
        check_bytes(reply, old_source, requested.first_sample, requested.sample_count, 17);
        require(same_request(reply.info().request, requested), "reply kept old pool/generation after public identity reuse");
        f.release(reply, 23);
    }
}

void gap_and_rejected_input_provenance() {
    for (unsigned phase = 0; phase <= 3; ++phase) {
        Fixture f;
        const auto source = independent::stream();
        f.fill(source);
        const auto requested = f.request();
        const auto admission = f.submit(requested);
        for (unsigned n = 0; n < phase; ++n) f.step(20);
        const auto before = f.history.state();
        auto input = independent::bytes(source, before.accepted_end_sample + 1, 1);
        slabs::Status outcome{};
        no_allocation([&] { outcome = f.history.append(source, before.accepted_end_sample + 1, input.data(), input.size()); });
        require(outcome == slabs::Status::Discontinuity && f.history.state().requires_new_epoch,
                "rejected source gap is explicit and does not get filled");
        f.ready(21);
        auto reply = f.take(admission.ticket, 22);
        if (phase < 2) {
            error_reply(reply, Status::SourceError, admission.ticket, requested);
            require(reply.info().source_status == slabs::Status::Discontinuity, "pre-grant gap reports actual continuity failure");
        } else check_bytes(reply, source, requested.first_sample, requested.sample_count);
        f.release(reply, 23);
    }
    Fixture f;
    const auto source = independent::stream();
    f.fill(source);
    const auto requested = f.request();
    const auto admission = f.submit(requested);
    const auto before = f.history.state();
    auto input = independent::bytes(source, before.accepted_end_sample, 1);
    auto stale_source = source; ++stale_source.epoch;
    require(f.history.append(stale_source, before.accepted_end_sample, input.data(), input.size()) == slabs::Status::EpochMismatch,
            "unrelated stale append rejected");
    require(f.history.state().end_sample == before.end_sample, "non-gap rejection preserves current interval");
    f.ready(20);
    auto reply = f.take(admission.ticket, 21);
    check_bytes(reply, source, requested.first_sample, requested.sample_count);
    f.release(reply, 22);
}

void source_failure_and_precedence() {
    for (unsigned mode = 0; mode < 4; ++mode) {
        Fixture f;
        f.fill(independent::stream());
        auto requested = f.request();
        requested.first_sample = f.history.state().end_sample;
        const auto admission = f.submit(requested, 10, 50);
        f.ready(20);
        if (mode == 1 || mode == 3) f.cancel(admission.ticket);
        auto reply = f.take(admission.ticket, mode >= 2 ? 50 : 21);
        error_reply(reply, mode == 1 || mode == 3 ? Status::Cancelled : mode == 2 ? Status::DeadlineExpired : Status::SourceError,
                    admission.ticket, requested);
        if (mode == 0) require(reply.info().source_status == slabs::Status::NotRetained, "unavailable request cannot be replaced by nearby samples");
        f.release(reply, 51);
    }
}

void counter_and_metadata_limits() {
    {
        Fixture f({2, coord::kMetadataCap});
        f.fill(independent::stream());
        const auto requested = f.request();
        for (unsigned n = 0; n < 2; ++n) {
            const auto admission = f.submit(requested, 10 + n * 10, 100);
            status(admission.status, Status::Ok, "bounded ticket generation available");
            require(admission.ticket.sequence() == n + 1, "initial ticket sequence has unique monotonic identities");
            f.ready(11 + n * 10);
            auto reply = f.take(admission.ticket, 12 + n * 10);
            check_bytes(reply, requested.stream, requested.first_sample, requested.sample_count);
            f.release(reply, 13 + n * 10);
        }
        const auto rejected = f.submit(requested, 40, 100);
        status(rejected.status, Status::CounterExhausted, "ticket generation must fail before reuse or wrap");
        require(!rejected.ticket, "exhaustion creates no ticket");
        expect_idle(f);
    }
    {
        slabs::ProcessBudget budget;
        slabs::History history(budget);
        bool rejected = false;
        try { Mailbox undersized(history, {10, 1}); }
        catch (const std::exception&) { rejected = true; }
        require(rejected, "metadata profile rejects a cap smaller than fixed coordinator storage");
        require(budget.stats().payload_bytes == slabs::kPayloadBytes && budget.stats().arenas == 1,
                "failed coordinator construction cannot allocate another source arena");
    }
    Fixture f;
    const auto memory = f.box.metadata();
    require(memory.control_allocation_bytes > 0 && memory.coordinator_object_bytes == sizeof(Mailbox) &&
            memory.held_reply_object_bytes == sizeof(Reply), "metadata accounting reports actual fixed objects");
    require(memory.reserved_bytes == memory.control_allocation_bytes + sizeof(Mailbox) + sizeof(Reply) &&
            memory.reserved_bytes <= memory.metadata_cap && memory.metadata_cap == coord::kMetadataCap,
            "coordinator metadata has its own bounded profile, separate from source payload");
    std::cout << "Coordinator metadata: control=" << memory.control_allocation_bytes
              << ", mailbox=" << memory.coordinator_object_bytes << ", reply=" << memory.held_reply_object_bytes
              << ", total=" << memory.reserved_bytes << " bytes.\n";
}

void held_reply_survives_shutdown_and_facades() {
    slabs::ProcessBudget budget;
    auto history = std::make_unique<slabs::History>(budget);
    auto box = std::make_unique<Mailbox>(*history);
    const auto source = independent::stream();
    require(history->begin_epoch(source) == slabs::Status::Ok, "lifetime source starts");
    auto input = independent::bytes(source, 0, slabs::kSlabBytes / 8, 91);
    require(history->append(source, 0, input.data(), input.size()) == slabs::Status::Ok, "lifetime data appended");
    const auto state = history->state();
    const slabs::Request requested{source, state.generation, state.pool_id, 7, 1000};
    const auto admission = box->submit(requested, 10, 100);
    box->service(20); box->service(21); box->service(22);
    auto reply = box->take(admission.ticket, 30);
    check_bytes(reply, source, 7, 1000, 91);
    box->close(); box->service(31);
    require(box->shutdown_acknowledged(), "held reply permits mailbox-only shutdown acknowledgement");
    box.reset(); history.reset();
    require(budget.stats().arenas == 1 && budget.stats().payload_bytes == slabs::kPayloadBytes,
            "taken reply keeps retired source arena charged after facade destruction");
    check_bytes(reply, source, 7, 1000, 91);
    bool refused = false;
    try { slabs::History replacement(budget); } catch (const slabs::budget_exhausted&) { refused = true; }
    require(refused, "retired arena cannot be bypassed by replacement service");
    std::exception_ptr failure;
    std::thread consumer([moved = std::move(reply), &failure, source]() mutable {
        try { check_bytes(moved, source, 7, 1000, 91); no_allocation([&] { moved.reset(); moved.reset(); }); }
        catch (...) { failure = std::current_exception(); }
    });
    consumer.join();
    if (failure) std::rethrow_exception(failure);
    require(budget.stats().arenas == 0 && budget.stats().payload_bytes == 0,
            "final detached completion safely refunds arena after owner destruction");
}

void stale_domain_survives_reconstruction() {
    slabs::ProcessBudget budget;
    slabs::History history(budget);
    const auto source = independent::stream();
    require(history.begin_epoch(source) == slabs::Status::Ok, "reconstruction source starts");
    auto input = independent::bytes(source, 0, slabs::kSlabBytes / 8);
    require(history.append(source, 0, input.data(), input.size()) == slabs::Status::Ok, "reconstruction source data");
    const auto state = history.state();
    const slabs::Request requested{source, state.generation, state.pool_id, 9, 1000};
    Ticket saved;
    {
        Mailbox first(history);
        saved = first.submit(requested, 10, 100).ticket;
        first.close();
        first.service(20); first.service(21); first.service(22);
        auto terminal = first.take(saved, 23);
        error_reply(terminal, Status::Closed, saved, requested);
        terminal.reset(); first.service(24);
        require(first.shutdown_acknowledged(), "first domain drained before reconstruction");
    }
    Mailbox second(history);
    const auto fresh = second.submit(requested, 10, 100);
    require(fresh.ticket.sequence() == saved.sequence() && fresh.ticket != saved,
            "reconstructed coordinator rejects same-number ticket from destroyed ownership domain");
    status(second.cancel(saved), Status::NotCurrent, "retained weak ticket cannot cancel reconstructed mailbox");
    auto stale = second.take(saved, 11);
    status(stale.status(), Status::NotCurrent, "retained weak ticket cannot take reconstructed reply");
    second.service(20); second.service(21); second.service(22);
    auto reply = second.take(fresh.ticket, 23);
    check_bytes(reply, source, 9, 1000);
    reply.reset(); second.service(24); second.close(); second.service(25);
    require(second.shutdown_acknowledged(), "replacement domain drains independently");
}

void reply_moves_and_exception_completion() {
    Fixture f;
    const auto source = independent::stream();
    f.fill(source);
    const auto requested = f.request();
    const auto admission = f.submit(requested);
    f.ready(20);
    auto first = f.take(admission.ticket, 21);
    Reply moved;
    no_allocation([&] { moved = std::move(first); });
    require(!first && first.span_count() == 0, "move assignment empties original reply");
    check_bytes(moved, source, requested.first_sample, requested.sample_count);
    auto& self = moved;
    no_allocation([&] { moved = std::move(self); });
    check_bytes(moved, source, requested.first_sample, requested.sample_count);
    status(f.submit(requested, 22).status, Status::Busy, "move does not create an extra admission credit");
    bool caught = false;
    try {
        Reply inner(std::move(moved));
        check_bytes(inner, source, requested.first_sample, requested.sample_count);
        throw 17;
    } catch (int value) { caught = value == 17; }
    require(caught, "test exercises exception unwinding of taken reply");
    f.step(23);
    expect_idle(f);
    no_allocation([&] { first.reset(); moved.reset(); });
    f.step(24);
    expect_idle(f);
}

void concurrent_publication_and_completion() {
    Fixture f;
    const auto source = independent::stream();
    f.fill(source, 8, 0, 83);
    const auto source_identity = f.request();
    // The source owner migrates once at thread creation, before concurrent work.
    // The only synchronization carrying requests/replies is the actual mailbox;
    // there is no test command publication after each submit/reset to mask a
    // missing request/reply/completion release-acquire edge.
    std::atomic<bool> owner_started{false}, stop{false}, owner_finished{false}, owner_allocated{false};
    std::exception_ptr worker_failure;
    std::thread owner([&] {
        owner_started.store(true, std::memory_order_release);
        try {
            while (!stop.load(std::memory_order_acquire)) {
                // Observe every service call, but assert only once after join;
                // scheduler-dependent polling must not change assertion totals.
                allocation_probe::calls = 0;
                allocation_probe::active = allocation_probe::available;
                f.box.service(50);
                allocation_probe::active = false;
                if (allocation_probe::calls) owner_allocated.store(true, std::memory_order_relaxed);
                std::this_thread::yield();
            }
        } catch (...) { allocation_probe::active = false; worker_failure = std::current_exception(); }
        owner_finished.store(true, std::memory_order_release);
    });
    auto wait_stage = [&](Stage expected) {
        while (f.box.stage() != expected && !owner_finished.load(std::memory_order_acquire)) std::this_thread::yield();
        require(!owner_finished.load(std::memory_order_acquire), "owner remains active until test shutdown");
    };
    try {
        while (!owner_started.load(std::memory_order_acquire)) std::this_thread::yield();
        // All requests are created before calling submit; source state is never
        // read by the client while owner service may be reclaiming History.
        const auto state = f.box.metadata();
        require(state.reserved_bytes > 0, "immutable metadata safe to observe across roles");
        for (unsigned n = 0; n < 64; ++n) {
            wait_stage(Stage::Idle);
            // The immutable source identity is retained separately, not read
            // from a candidate reply or mutable history table.
            auto requested = source_identity;
            requested.first_sample = 1 + n * 7U;
            requested.sample_count = 1000 + n;
            const auto admission = f.submit(requested, 50, 1000);
            status(admission.status, Status::Ok, "concurrent client publishes one admitted request");
            if (n % 2) status(f.cancel(admission.ticket), Status::Ok, "cancellation races actual owner phases safely");
            wait_stage(Stage::Ready);
            auto reply = f.take(admission.ticket, 50);
            if (n % 2) error_reply(reply, Status::Cancelled, admission.ticket, requested);
            else {
                check_bytes(reply, source, requested.first_sample, requested.sample_count, 83);
                require(same_request(reply.info().request, requested), "cross-thread reply request metadata published fully");
            }
            no_allocation([&] { reply.reset(); });
            wait_stage(Stage::Idle);
        }
        no_allocation([&] { f.box.close(); });
        while (!f.box.shutdown_acknowledged() && !owner_finished.load(std::memory_order_acquire)) std::this_thread::yield();
        require(f.box.shutdown_acknowledged(), "owner acknowledges client-published shutdown");
    } catch (...) {
        stop.store(true, std::memory_order_release);
        owner.join();
        throw;
    }
    stop.store(true, std::memory_order_release);
    owner.join();
    if (worker_failure) std::rethrow_exception(worker_failure);
    if constexpr (allocation_probe::available)
        require(!owner_allocated.load(std::memory_order_relaxed), "concurrent owner service allocates no C++ storage");
    else
        ++allocation_probe::omitted_assertions;
    require(f.history.state().snapshot_pinned_slabs == 0, "joined owner has reclaimed every concurrent completion");
}

void maximum_snapshot_waits_while_history_changes() {
    for (const auto format : {slabs::Format::CU8, slabs::Format::CF32LE, slabs::Format::CF32BE}) {
        Fixture f;
        const auto source = independent::stream(format);
        f.fill(source, 160, 107, 107);
        const auto first = f.history.state().end_sample - 768001;
        const auto requested = f.request(first, 768000);
        const auto admission = f.submit(requested, 10, 100);
        f.ready(20);
        const auto expected_spans = format == slabs::Format::CU8 ? 26U : 101U;
        require(f.history.state().snapshot_pinned_slabs == expected_spans,
                "untaken arbitrary-alignment250ms grant has exact physical pin count");
        auto replacement = source; ++replacement.epoch;
        f.fill(replacement, 160, 0, 211);
        require(f.history.state().retained_bytes == 8388608 &&
                f.history.state().snapshot_pinned_slabs == expected_spans,
                "max queued old-epoch reply preserves full current history and fixed pins");
        status(f.submit(f.request(), 21).status, Status::Busy, "queued maximum grant cannot lose credit under retune");
        auto reply = f.take(admission.ticket, 22);
        check_bytes(reply, source, first, 768000, 107);
        require(reply.span_count() == expected_spans, "maximum reply publishes complete original span list");
        f.release(reply, 23);
        require(f.budget.stats().payload_bytes == slabs::kPayloadBytes && f.budget.stats().arenas == 1,
                "maximum queued reply never needs a fallback source arena");
    }
}
}

int main() {
    struct Test { const char* name; void (*run)(); };
    const Test tests[] = {
        {"exact handoff and one credit", exact_handoff_and_credit},
        {"cancellation at every handoff", cancellation_at_every_handoff},
        {"deadline equality and maximum", deadline_boundaries_and_maximum},
        {"close at every handoff and precedence", close_at_every_handoff_and_precedence},
        {"nonconsuming tick regression", tick_regression_is_nonconsuming},
        {"invalid and stale tickets", invalid_and_stale_tickets_never_modify_current},
        {"source changes before/after grant", source_changes_before_grant_and_after_grant},
        {"gap and rejected input provenance", gap_and_rejected_input_provenance},
        {"source failure and precedence", source_failure_and_precedence},
        {"counter and metadata limits", counter_and_metadata_limits},
        {"held reply lifetime", held_reply_survives_shutdown_and_facades},
        {"reconstructed ticket domain ABA", stale_domain_survives_reconstruction},
        {"reply move and exception completion", reply_moves_and_exception_completion},
        {"concurrent publication/completion", concurrent_publication_and_completion},
        {"maximum queued snapshot across retune", maximum_snapshot_waits_while_history_changes}
    };
    unsigned failures = 0;
    for (const auto& test : tests) {
        try { test.run(); }
        catch (const std::exception& error) {
            ++failures;
            std::cerr << "FAIL " << test.name << ": " << error.what() << '\n';
        }
    }
    std::cout << "Independent coordinator contract: " << sizeof(tests) / sizeof(tests[0])
              << " groups, " << failures << " failures, " << independent::assertions.load()
              << " assertions, " << independent::exact_bytes.load() << " exact bytes.\n"
              << "Scope: supplied-tick ownership correctness; no wall-clock, RF or decoder-speed result.\n";
    if constexpr (!allocation_probe::available)
        std::cout << "Allocation probe unavailable under TSan; use ordinary/ASan builds for allocation validation. "
                  << allocation_probe::omitted_assertions.load() << " allocation assertions omitted; "
                  << "ownership and byte checks remain enabled.\n";
    return failures ? 1 : 0;
}
