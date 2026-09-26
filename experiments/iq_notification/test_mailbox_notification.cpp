// SPDX-License-Identifier: GPL-3.0-or-later
// Composition checks, not an observer integration or a performance workload.
#include "ready_notification.h"
#include "iq_coordinator.h"
#include <atomic>
#include <chrono>
#include <cstdint>
#include <exception>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <thread>
#include <vector>

namespace n = xerax::experiment::notification;
namespace c = xerax::experiment::coordinator;
namespace s = xerax::experiment::slabs;
namespace {
std::atomic<std::uint64_t> checks{0}, checked_bytes{0};
void require(bool value, const char* message) {
    ++checks;
    if (!value) throw std::runtime_error(message);
}
std::uint8_t expected(std::uint64_t offset) {
    // Independent byte oracle, unrelated to the performance observer's hash.
    return static_cast<std::uint8_t>((offset * 13U + offset / 251U + 47U) & 255U);
}
struct Fixture {
    s::ProcessBudget source_budget;
    s::History history{source_budget};
    c::Budget mailbox_budget{16U * 1024U};
    c::Mailbox mailbox{history, mailbox_budget};
    n::ReadyNotification notification;
    s::Stream stream{9, 17, 3072000, 451100000, s::Format::CF32LE};
    c::Ticket pending;
    std::size_t width = 8;
    explicit Fixture(s::Format format=s::Format::CF32LE) {
        stream.format = format;
        width = s::sample_bytes(format);
        require(history.begin_epoch(stream) == s::Status::Ok, "source epoch");
        std::vector<std::uint8_t> block(2 * s::kSlabBytes);
        for (std::size_t i=0;i<block.size();++i) block[i]=expected(i);
        require(history.append(stream,0,block.data(),block.size()) == s::Status::Ok, "known source append");
    }
    ~Fixture() {
        // Preserve a test assertion instead of masking it with mailbox abort.
        // No thread may survive Fixture's scope (joined by each test).
        try {
            notification.close();
            mailbox.close();
            const auto tick=(std::numeric_limits<c::Tick>::max)();
            for (unsigned i=0;i<12&&!mailbox.shutdown_acknowledged();++i) {
                if (mailbox.stage()==c::Stage::Ready && pending) {
                    auto discarded=mailbox.take(pending,tick);
                    discarded.reset();
                }
                mailbox.service(tick);
            }
        } catch (...) { std::terminate(); }
    }
    s::Request request() {
        const auto state=history.state();
        return {stream,state.generation,state.pool_id,11,4096};
    }
    c::Submission submit(const s::Request& request, c::Tick now, c::Tick deadline) {
        auto admission=mailbox.submit(request,now,deadline);
        if (admission.status==c::Status::Ok) pending=admission.ticket;
        return admission;
    }
    void ready(c::Tick start) {
        const c::Stage stages[]={c::Stage::Acquired,c::Stage::Granted,c::Stage::Ready};
        for (unsigned i=0;i<3;++i) {
            const auto result=mailbox.service(start+i);
            require(result.status==c::Status::Ok && result.stage==stages[i], "real owner transition");
        }
    }
    void bytes(const c::Reply& reply,const s::Request& requested) {
        require(reply.status()==c::Status::Ok, "successful real reply");
        const auto& info=reply.info();
        require(info.ticket==pending && info.request.stream==requested.stream &&
                info.request.generation==requested.generation && info.request.pool_id==requested.pool_id &&
                info.request.first_sample==requested.first_sample && info.request.sample_count==requested.sample_count,
                "source and request identities preserved");
        std::uint64_t offset=requested.first_sample*width, count=0;
        for (std::size_t i=0;i<reply.span_count();++i) {
            const auto& span=reply.span(i);
            require(span.first_sample*width==offset, "contiguous original source span");
            for (std::size_t j=0;j<span.byte_count;++j) {
                if (span.data[j]!=expected(offset+j)) throw std::runtime_error("known byte mismatch");
                ++count;
            }
            offset+=span.byte_count;
        }
        require(count==requested.sample_count*width, "all requested bytes checked");
        checked_bytes+=count;
    }
    void release(c::Reply& reply,c::Tick tick) {
        reply.reset();
        const auto result=mailbox.service(tick);
        require(result.stage==c::Stage::Idle, "core credit requires owner acknowledgement");
        require(history.state().snapshot_pinned_slabs==0, "source pins returned");
    }
};

void ready_is_not_a_payload_or_core_deadline_override() {
    for (auto format : {s::Format::CU8,s::Format::CF32LE,s::Format::CF32BE}) {
        Fixture f(format);
        const auto request=f.request();
        const auto armed=f.notification.arm();
        require(armed.status==n::Status::Ok, "arm before core submission");
        const auto admission=f.submit(request,10,100);
        require(admission.status==c::Status::Ok, "core admission");
        f.ready(20);
        require(f.notification.notify(armed.token)==n::Status::Ok, "matching terminal signal");
        require(f.notification.wait_until(armed.token,n::ReadyNotification::Clock::now()-std::chrono::seconds(1))==n::Status::Ready,
                "sticky signal wins expired wait deadline only");
        auto reply=f.mailbox.take(admission.ticket,30);
        f.bytes(reply,request);
        require(f.notification.state().armed==false && f.history.state().snapshot_pinned_slabs>0,
                "consuming notification never releases core ownership");
        f.notification.close();
        require(f.mailbox.submit(request,31,100).status==c::Status::Busy, "held core lease still excludes admission");
        f.bytes(reply,request);
        f.release(reply,40);
    }
    Fixture f;
    const auto armed=f.notification.arm();
    const auto admission=f.submit(f.request(),10,25);
    f.ready(20);
    require(f.notification.notify(armed.token)==n::Status::Ok, "signal ready before core deadline");
    require(f.notification.wait_until(armed.token,n::ReadyNotification::Clock::now())==n::Status::Ready, "notice ready");
    auto expired=f.mailbox.take(admission.ticket,25);
    require(expired.status()==c::Status::DeadlineExpired && expired.span_count()==0,
            "notification cannot override deadline equality in actual take");
    f.release(expired,40);
}

void terminal_errors_still_require_take_and_drain() {
    for (unsigned scenario=0;scenario<4;++scenario) {
        Fixture f;
        auto request=f.request();
        if (scenario==3) ++request.generation;
        const auto armed=f.notification.arm();
        const auto admission=f.submit(request,10,scenario==1?15:100);
        require(admission.status==c::Status::Ok, "error case admitted");
        if (scenario==0) require(f.mailbox.cancel(admission.ticket)==c::Status::Ok,"cancel admitted ticket");
        if (scenario==2) f.mailbox.close();
        f.ready(20);
        require(f.notification.notify(armed.token)==n::Status::Ok,"terminal error is ready, not successful payload");
        require(f.notification.wait_until(armed.token,n::ReadyNotification::Clock::now())==n::Status::Ready,"terminal notice consumed");
        auto reply=f.mailbox.take(admission.ticket,30);
        const c::Status expected_status[]={c::Status::Cancelled,c::Status::DeadlineExpired,c::Status::Closed,c::Status::SourceError};
        require(reply.status()==expected_status[scenario] && reply.span_count()==0,"actual error classification retained");
        require(reply.info().ticket==admission.ticket,"error identity retained");
        reply.reset();
        f.mailbox.service(40);
        require(f.history.state().snapshot_pinned_slabs==0,"failed handoff releases source pins");
        require(f.mailbox.stage()==(scenario==2?c::Stage::Closed:c::Stage::Idle),"error credit drained");
    }
}

void timeout_and_stale_notifications_do_not_reset_core_work() {
    Fixture f;
    const auto request=f.request();
    auto armed=f.notification.arm();
    auto admission=f.submit(request,10,100);
    require(f.notification.wait_until(armed.token,n::ReadyNotification::Clock::now())==n::Status::TimedOut,"unready wait timeout");
    require(f.mailbox.stage()==c::Stage::Pending && f.notification.arm().status==n::Status::Busy,"timeout retains both independent reservations");
    f.ready(20);
    require(f.notification.notify(armed.token)==n::Status::Ok,"same generation can still complete");
    require(f.notification.wait_until(armed.token,n::ReadyNotification::Clock::now())==n::Status::Ready,"late notification retained");
    auto reply=f.mailbox.take(admission.ticket,30);f.bytes(reply,request);f.release(reply,40);
    const auto old=armed.token;
    armed=f.notification.arm();
    admission=f.submit(request,50,100);
    require(f.notification.notify(old)==n::Status::NotCurrent,"late old-generation signal rejected");
    require(f.notification.wait_until(armed.token,n::ReadyNotification::Clock::now())==n::Status::TimedOut,"old signal cannot make new core Pending ready");
    f.notification.close();
    require(f.mailbox.stage()==c::Stage::Pending,"notification close does not drop a core request");
    f.mailbox.close();f.ready(60);
    reply=f.mailbox.take(admission.ticket,70);
    require(reply.status()==c::Status::Closed,"explicit core close still requires terminal take");
    reply.reset();f.mailbox.service(80);
    require(f.mailbox.shutdown_acknowledged(),"core shutdown acknowledged separately");
}

void concurrent_real_handoffs() {
    Fixture f;
    const auto request=f.request();
    for (std::uint64_t iteration=0;iteration<128;++iteration) {
        const auto tick=iteration*100;
        const auto armed=f.notification.arm();
        require(armed.status==n::Status::Ok,"bounded sequence arm");
        const auto admission=f.submit(request,tick+10,tick+90);
        require(admission.status==c::Status::Ok,"bounded sequence admission");
        std::exception_ptr owner_error;
        std::thread owner([&,token=armed.token] {
            try {
                // Token is captured immutably before publishing Ready. The
                // constructor's thread-start synchronization publishes it.
                f.ready(tick+20);
                require(f.notification.notify(token)==n::Status::Ok,"matched concurrent readiness");
            } catch (...) {
                owner_error=std::current_exception();
                // Preserve the first failure if std-library wake cleanup also
                // throws. The client's finite safety wait will still end.
                try { f.notification.close(); } catch (...) {}
            }
        });
        struct Join {std::thread& thread;~Join(){if(thread.joinable())thread.join();}} join{owner};
        const auto notified=f.notification.wait_until(armed.token,n::ReadyNotification::Clock::now()+std::chrono::seconds(10));
        if (notified!=n::Status::Ready) {
            owner.join();
            if(owner_error) std::rethrow_exception(owner_error);
            require(false,"real concurrent signal failed to reach consumer");
        }
        require(notified==n::Status::Ready,"real concurrent signal reached consumer");
        auto reply=f.mailbox.take(admission.ticket,tick+30);
        // Verify BEFORE join so source publication cannot borrow its ordering.
        // The owner only finishes the notification operation at this point.
        f.bytes(reply,request);
        owner.join();
        if(owner_error) std::rethrow_exception(owner_error);
        // Transfer owner duties back only after the worker has joined.
        f.release(reply,tick+40);
    }
}
}
int main() {
    try {
        ready_is_not_a_payload_or_core_deadline_override();
        terminal_errors_still_require_take_and_drain();
        timeout_and_stale_notifications_do_not_reset_core_work();
        concurrent_real_handoffs();
        std::cout<<"4 mailbox-composition groups passed; "<<checks.load()<<" checks; "<<checked_bytes.load()<<" exact bytes. No performance claim.\n";
        return 0;
    } catch(const std::exception& error) {
        std::cerr<<"Composition failure: "<<error.what()<<'\n';return 1;
    }
}
