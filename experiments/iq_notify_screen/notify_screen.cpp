// SPDX-License-Identifier: GPL-3.0-or-later
// Schema 5 readiness-wait comparison. Frozen schema 4 and all cores remain unchanged.
#include "credit_history.h"
#include "iq_coordinator.h"
#include "notification_trace.h"
#include "../iq_comparison/pending_take.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iostream>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <thread>
#include <limits>
#include <cerrno>
#ifndef _WIN32
#include <time.h>
#endif
#include <vector>
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

namespace {
namespace iq = xerax::experiment;
namespace slabs = xerax::experiment::slabs;
namespace coord = xerax::experiment::coordinator;
namespace notice = xerax::experiment::notification;
namespace side = xerax::experiment::notification_trace;
using xerax::experiment::comparison::take_pending;
using Clock = std::chrono::steady_clock;
using Ns = std::chrono::nanoseconds;
using I = std::int64_t;
constexpr I rate = 3072000, samples = 30720, window = 768000;
constexpr I period = 10000000, request_period = 100000000, deadline_span = 50000000;
constexpr unsigned prefill_count = 140, drain_limit = 1000;
constexpr I safety_wait_timeout = 2000000000;
I now_ns() { return std::chrono::duration_cast<Ns>(Clock::now().time_since_epoch()).count(); }
struct CpuSample { I before=0, after=0; std::optional<I> value; int error=0; };
CpuSample cpu_sample() {
    CpuSample s;s.before=now_ns();
#ifdef _WIN32
    FILETIME creation{},exit{},kernel{},user{};
    if(GetProcessTimes(GetCurrentProcess(),&creation,&exit,&kernel,&user)) {
        const auto bits=[](FILETIME f){return (static_cast<std::uint64_t>(f.dwHighDateTime)<<32U)|f.dwLowDateTime;};
        const auto k=bits(kernel),u=bits(user),limit=static_cast<std::uint64_t>((std::numeric_limits<I>::max)())/100U;
        if(k<=limit&&u<=limit-k)s.value=static_cast<I>((k+u)*100U);else s.error=EOVERFLOW;
    } else s.error=static_cast<int>(GetLastError());
#else
    timespec value{};
    if(clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&value)==0) {
        const auto limit=(std::numeric_limits<I>::max)();
        if(value.tv_sec>=0&&value.tv_nsec>=0&&value.tv_nsec<1000000000&&static_cast<I>(value.tv_sec)<=(limit-static_cast<I>(value.tv_nsec))/1000000000)
            s.value=static_cast<I>(value.tv_sec)*1000000000+static_cast<I>(value.tv_nsec);
        else s.error=EOVERFLOW;
    } else s.error=errno;
#endif
    s.after=now_ns();return s;
}
std::optional<I> cpu_resolution() {
#ifdef _WIN32
    return 100; // FILETIME storage unit, NOT a measured accounting resolution.
#else
    timespec value{};
    if(clock_getres(CLOCK_PROCESS_CPUTIME_ID,&value)!=0||value.tv_sec<0||value.tv_nsec<0)return {};
    return static_cast<I>(value.tv_sec)*1000000000+static_cast<I>(value.tv_nsec);
#endif
}
enum F : std::size_t { Id, Parent, SourceStatus, EventId, RequestId, StreamId, Epoch, Rate,
    Frequency, Width, Pool, Generation, First, End, Bytes, Before, After, Due, Check,
    Deadline, Verified, Expected, Actual, Offset, FieldCount };
struct Row {
    const char* kind = ""; const char* role = ""; const char* phase = "";
    const char* status = ""; const char* field = "";
    std::array<std::optional<I>, FieldCount> n{};
};
struct Trace {
    std::vector<Row> rows;
    std::size_t bound;
    std::size_t dropped = 0;
    const char* role;
    Trace(std::size_t capacity, const char* name) : bound(capacity), role(name) { rows.reserve(capacity); }
    Row& add(const char* kind, const char* phase = "", std::optional<I> parent = {}) {
        if (rows.size() == bound) { ++dropped; throw std::runtime_error("Trace capacity exhausted"); }
        rows.push_back({}); auto& row = rows.back(); row.kind = kind; row.role = role;
        row.phase = phase; row.n[Id] = static_cast<I>(rows.size()); row.n[Parent] = parent;
        return row;
    }
};
struct Descriptor {
    I event = 0, first = 0, end = 0, width = 0;
    std::optional<I> pool, generation;
};
void source(Row& row, const Descriptor& d) {
    row.n[EventId] = d.event; row.n[StreamId] = 1; row.n[Epoch] = 1;
    row.n[Rate] = rate; row.n[Frequency] = 451100000; row.n[Width] = d.width;
    row.n[Pool] = d.pool; row.n[Generation] = d.generation;
    row.n[First] = d.first; row.n[End] = d.end; row.n[Bytes] = (d.end - d.first) * d.width;
}
void interval(Row& row, const Descriptor& d, I first, I end) {
    source(row, d); row.n[First] = first; row.n[End] = end; row.n[Bytes] = (end - first) * d.width;
}
std::uint8_t pattern(std::uint64_t byte) {
    byte ^= byte >> 13U; byte *= UINT64_C(0x9e3779b97f4a7c15);
    return static_cast<std::uint8_t>((byte >> 48U) ^ (byte >> 24U) ^ byte);
}
const char* status_name(coord::Status s) {
    switch (s) {
    case coord::Status::Ok: return "ok"; case coord::Status::Empty: return "empty";
    case coord::Status::Busy: return "busy"; case coord::Status::Closed: return "closed";
    case coord::Status::Cancelled: return "cancelled"; case coord::Status::DeadlineExpired: return "deadline_expired";
    case coord::Status::CounterExhausted: return "counter_exhausted"; case coord::Status::TickRegression: return "tick_regression";
    case coord::Status::NotCurrent: return "not_current"; case coord::Status::TooLate: return "too_late";
    case coord::Status::SourceError: return "source_error";
    } return "unknown";
}
const char* stage_name(coord::Stage s) {
    switch (s) {
    case coord::Stage::Idle:return "idle"; case coord::Stage::Submitting:return "submitting";
    case coord::Stage::Pending:return "pending"; case coord::Stage::Acquired:return "acquired";
    case coord::Stage::Granted:return "granted"; case coord::Stage::Ready:return "ready";
    case coord::Stage::Taking:return "taking"; case coord::Stage::Held:return "held";
    case coord::Stage::Consumed:return "consumed"; case coord::Stage::Closed:return "closed";
    } return "unknown";
}
struct Failure {
    bool present = false;
    std::string role, message, field;
    std::optional<I> request, expected, actual, offset;
};
struct VerifyError : std::runtime_error {
    const char* field; I expected, actual; std::optional<I> offset;
    VerifyError(const char* f, I e, I a, std::optional<I> o = {})
        : std::runtime_error("Source verification failed"), field(f), expected(e), actual(a), offset(o) {}
};
struct Adapter {
    std::unique_ptr<iq::CreditHistory> whole;
    std::unique_ptr<slabs::ProcessBudget> slab_budget;
    std::unique_ptr<slabs::History> history;
    std::unique_ptr<coord::Budget> mailbox_budget;
    std::unique_ptr<coord::Mailbox> mailbox;
    iq::Stream whole_stream;
    slabs::Stream slab_stream;
    I width;
    Adapter(bool coordinated, I bytes) : whole_stream{1,1,static_cast<std::uint32_t>(rate),451100000,static_cast<std::uint32_t>(bytes)},
        slab_stream{1,1,static_cast<std::uint32_t>(rate),451100000,bytes == 2 ? slabs::Format::CU8 : slabs::Format::CF32LE}, width(bytes) {
        if (coordinated) {
            slab_budget = std::make_unique<slabs::ProcessBudget>();
            history = std::make_unique<slabs::History>(*slab_budget);
            if (history->begin_epoch(slab_stream) != slabs::Status::Ok) throw std::runtime_error("Slab epoch rejected");
            mailbox_budget = std::make_unique<coord::Budget>(16U * 1024U);
            mailbox = std::make_unique<coord::Mailbox>(*history, *mailbox_budget);
        } else {
            constexpr std::size_t mib = 1024U * 1024U;
            whole = std::make_unique<iq::CreditHistory>(iq::CreditConfig{8U*mib,7U*mib,1U,15U*mib});
            if (whole->begin_epoch(whole_stream) != iq::Status::Ok) throw std::runtime_error("Whole epoch rejected");
        }
    }
    I append(I first, const std::vector<std::uint8_t>& bytes, bool corrupt) {
        const auto size = bytes.size() - (corrupt ? 1U : 0U);
        return history ? static_cast<I>(history->append(slab_stream,static_cast<std::uint64_t>(first),bytes.data(),size))
                       : static_cast<I>(whole->append(whole_stream,static_cast<std::uint64_t>(first),bytes.data(),size));
    }
    Descriptor state() const {
        Descriptor d; d.width = width;
        if (history) {
            const auto s = history->state(); d.first=static_cast<I>(s.first_sample);d.end=static_cast<I>(s.end_sample);
            d.pool=static_cast<I>(s.pool_id);d.generation=static_cast<I>(s.generation);
        } else {const auto s=whole->state();d.first=static_cast<I>(s.first_sample);d.end=static_cast<I>(s.end_sample);}
        return d;
    }
};
struct Memory {
    I before=0,after=0;
    bool coordinated=false;
    iq::State whole_state{};iq::CreditStats whole{};
    slabs::State slab_state{};slabs::BudgetStats slabs{};
    coord::BudgetStats coordinator{};coord::MetadataStats mailbox{};
};
Memory memory_sample(const Adapter& a) {
    Memory m;m.before=now_ns();m.coordinated=static_cast<bool>(a.mailbox);
    if(m.coordinated){m.slab_state=a.history->state();m.slabs=a.slab_budget->stats();m.coordinator=a.mailbox_budget->stats();m.mailbox=a.mailbox->metadata();}
    else{m.whole_state=a.whole->state();m.whole=a.whole->credit_stats();}
    m.after=now_ns();return m;
}
bool memory_quiescent_full(const Memory& m) {
    if(m.coordinated)return m.slab_state.retained_bytes==slabs::kRetentionBytes&&m.slab_state.active&&
        m.slab_state.snapshot_pinned_slabs==0&&m.slab_state.live_pinned_slabs==0&&m.slab_state.outstanding_live_leases==0&&m.slab_state.filling_bytes==0;
    return m.whole_state.retained_bytes==slabs::kRetentionBytes&&m.whole_state.active&&m.whole.outstanding_count==0&&m.whole.outstanding_reserved_bytes==0;
}
void write_memory(std::ostream& out,const Memory& m,I origin) {
    const auto n=[&](const char* name,std::size_t value){out<<",\""<<name<<"\":"<<value;};
    const auto first=m.coordinated?m.slab_state.first_sample:m.whole_state.first_sample;
    const auto end=m.coordinated?m.slab_state.end_sample:m.whole_state.end_sample;
    out<<"{\"before_ns\":"<<m.before-origin<<",\"after_ns\":"<<m.after-origin;
    n("retention_capacity_bytes",slabs::kRetentionBytes);n("retained_bytes",m.coordinated?m.slab_state.retained_bytes:m.whole_state.retained_bytes);
    out<<",\"first_sample\":"<<first<<",\"end_sample\":"<<end<<",\"accepted_end_sample\":"<<(m.coordinated?m.slab_state.accepted_end_sample:end);
    out<<",\"source_active\":"<<((m.coordinated?m.slab_state.active:m.whole_state.active)?"true":"false")
       <<",\"source_metadata_opaque\":"<<(m.coordinated?"false":"true");
    n("unreserved_facade_bytes",m.coordinated?sizeof(slabs::History)+sizeof(slabs::ProcessBudget)+sizeof(coord::Budget):sizeof(iq::CreditHistory));
    out<<",\"whole\":";
    if(m.coordinated)out<<"null";else{
        out<<"{\"ring_capacity_bytes\":"<<m.whole.ring_capacity_bytes;
        n("snapshot_capacity_bytes",m.whole.snapshot_capacity_bytes);n("slot_count",m.whole.slot_count);n("outstanding_count",m.whole.outstanding_count);
        n("outstanding_reserved_bytes",m.whole.outstanding_reserved_bytes);n("preallocated_snapshot_bytes",m.whole.preallocated_snapshot_bytes);
        n("total_payload_bytes",m.whole.total_payload_bytes);n("payload_budget_bytes",m.whole.payload_budget_bytes);out<<'}';
    }
    out<<",\"slabs\":";
    if(!m.coordinated)out<<"null";else{
        out<<"{\"payload_bytes\":"<<m.slabs.payload_bytes;n("metadata_bytes",m.slabs.metadata_bytes);n("budget_control_bytes",m.slabs.budget_control_bytes);
        n("payload_limit",m.slabs.payload_limit);n("metadata_limit",m.slabs.metadata_limit);n("arenas",m.slabs.arenas);
        n("snapshot_pinned_slabs",m.slab_state.snapshot_pinned_slabs);n("live_pinned_slabs",m.slab_state.live_pinned_slabs);
        n("outstanding_live_leases",m.slab_state.outstanding_live_leases);n("filling_bytes",m.slab_state.filling_bytes);
        n("history_slabs",m.slab_state.history_slabs);n("free_slabs",m.slab_state.free_slabs);out<<'}';
    }
    out<<",\"coordinator\":";
    if(!m.coordinated)out<<"null";else{
        out<<"{\"reservation_limit\":"<<m.coordinator.reservation_limit;n("current_reserved_bytes",m.coordinator.current_reserved_bytes);
        n("high_water_reserved_bytes",m.coordinator.high_water_reserved_bytes);n("ledger_allocation_bytes",m.coordinator.ledger_allocation_bytes);
        n("control_allocation_bytes",m.coordinator.control_allocation_bytes);n("fixed_reservation_bytes",m.coordinator.fixed_reservation_bytes);
        n("control_reservations",m.coordinator.control_reservations);n("high_water_control_reservations",m.coordinator.high_water_control_reservations);out<<'}';
    }
    out<<",\"mailbox_metadata\":";
    if(!m.coordinated)out<<"null";else{
        out<<"{\"control_allocation_bytes\":"<<m.mailbox.control_allocation_bytes;n("coordinator_object_bytes",m.mailbox.coordinator_object_bytes);
        n("held_reply_object_bytes",m.mailbox.held_reply_object_bytes);n("reserved_bytes",m.mailbox.reserved_bytes);n("metadata_cap",m.mailbox.metadata_cap);out<<'}';
    }out<<'}';
}
struct Grant {
    iq::SnapshotLease whole;
    coord::Reply reply;
    bool coordinated = false;
    bool valid() const {return coordinated ? static_cast<bool>(reply) : static_cast<bool>(whole);}
    void reset() {whole.reset();reply.reset();}
};
void observed(Row& row, const Grant& g, I event) {
    row.n[EventId]=event;
    if (g.coordinated) {
        const auto& m=g.reply.lease_info();row.n[StreamId]=static_cast<I>(m.stream.stream_id);row.n[Epoch]=static_cast<I>(m.stream.epoch);
        row.n[Rate]=m.stream.sample_rate_hz;row.n[Frequency]=static_cast<I>(m.stream.center_frequency_hz);
        row.n[Width]=static_cast<I>(slabs::sample_bytes(m.stream.format));row.n[Pool]=static_cast<I>(m.pool_id);row.n[Generation]=static_cast<I>(m.generation);
        row.n[First]=static_cast<I>(m.first_sample);row.n[End]=static_cast<I>(m.end_sample);row.n[Bytes]=static_cast<I>(m.byte_count);
    } else {
        const auto& m=g.whole.info();row.n[StreamId]=static_cast<I>(m.stream.stream_id);row.n[Epoch]=static_cast<I>(m.stream.epoch);
        row.n[Rate]=m.stream.sample_rate_hz;row.n[Frequency]=static_cast<I>(m.stream.center_frequency_hz);row.n[Width]=m.stream.bytes_per_complex_sample;
        row.n[First]=static_cast<I>(m.first_sample);row.n[End]=static_cast<I>(m.end_sample);row.n[Bytes]=static_cast<I>(m.byte_count);
    }
}
void verify(Grant& grant, Row& row, const Descriptor& selected, I first, bool inject) {
    observed(row,grant,selected.event);row.n[Verified]=0;
    const auto check=[&](F f,const char* name,I wanted){if(!row.n[f]||*row.n[f]!=wanted)throw VerifyError(name,wanted,row.n[f].value_or(-1));};
    check(StreamId,"stream_id",1);check(Epoch,"epoch",1);check(Rate,"rate_hz",rate);check(Frequency,"frequency_hz",451100000);
    check(Width,"width",selected.width);check(First,"first_sample",first);check(End,"end_sample",first+window);check(Bytes,"byte_count",window*selected.width);
    if (grant.coordinated) {check(Pool,"pool_id",*selected.pool);check(Generation,"generation",*selected.generation);}
    I offset=0;
    const auto bytes=[&](const std::uint8_t* data,std::size_t size,I start) {
        if(start!=first+offset/selected.width)throw VerifyError("span_first",first+offset/selected.width,start);
        if(!data||size==0||size%static_cast<std::size_t>(selected.width)!=0)throw std::runtime_error("Invalid leased span");
        for(std::size_t i=0;i<size;++i,++offset) {
            const auto expected=pattern(static_cast<std::uint64_t>(first*selected.width+offset));
            auto actual=data[i];if(inject&&offset==17)actual^=1U;
            if(actual!=expected)throw VerifyError("byte",expected,actual,offset);
            row.n[Verified]=offset+1;
        }
    };
    if(grant.coordinated)for(std::size_t i=0;i<grant.reply.span_count();++i){const auto& s=grant.reply.span(i);bytes(s.data,s.byte_count,static_cast<I>(s.first_sample));}
    else bytes(grant.whole.data(),grant.whole.size(),first);
    if(offset!=window*selected.width)throw VerifyError("verified_bytes",window*selected.width,offset);
}
void quoted(std::ostream& out,const std::string& value) {
    out << '"';for(unsigned char c:value){if(c=='"'||c=='\\')out<<'\\'<<static_cast<char>(c);else if(c<32U){char escaped[7];std::snprintf(escaped,sizeof escaped,"\\u%04x",static_cast<unsigned>(c));out<<escaped;}else out<<static_cast<char>(c);}out<<'"';
}
void write_trace(const std::string& path,const Trace& producer,const Trace& consumer,I origin) {
    std::ofstream out(path);if(!out)throw std::runtime_error("Cannot open trace output");
    out<<"kind,role,id,parent_id,phase,status,source_status,event_id,request_id,stream_id,epoch,rate_hz,frequency_hz,width,pool_id,generation,first_sample,end_sample,byte_count,before_ns,after_ns,due_ns,check_ns,deadline_ns,verified_bytes,field,expected,actual,offset\n";
    for(const auto* trace:{&producer,&consumer})for(const auto& r:trace->rows) {
        const auto n=[&](F f){if(r.n[f])out<<(*r.n[f]-((f>=Before&&f<=Deadline)?origin:0));};
        out<<r.kind<<','<<r.role<<',';n(Id);out<<',';n(Parent);out<<','<<r.phase<<','<<r.status<<',';
        for(std::size_t f=SourceStatus;f<=Verified;++f){n(static_cast<F>(f));out<<',';}
        out<<r.field<<',';n(Expected);out<<',';n(Actual);out<<',';n(Offset);out<<'\n';
    }
    out.flush();if(!out)throw std::runtime_error("Trace output write failed");
    out.close();if(!out)throw std::runtime_error("Trace output close failed");
}
struct Options {std::string variant="coordinator",format="cf32",csv,sidecar,wait_mode="poll",fault="none";unsigned duration=200;};
Options options(int argc,char** argv) {
    Options o;for(int i=1;i<argc;i+=2){if(i+1>=argc)throw std::invalid_argument("Options require values");const std::string key(argv[i]),value(argv[i+1]);
        if(key=="--variant")o.variant=value;else if(key=="--format")o.format=value;else if(key=="--csv")o.csv=value;else if(key=="--fault")o.fault=value;else if(key=="--sidecar")o.sidecar=value;else if(key=="--wait-mode")o.wait_mode=value;
        else if(key=="--duration-ms"){if(value.empty()||value.find_first_not_of("0123456789")!=std::string::npos)throw std::invalid_argument("Unsigned duration required");const auto v=std::stoul(value);if(v<100||v>60000||v%10!=0)throw std::invalid_argument("Duration must be100..60000 ms, divisible by10");o.duration=static_cast<unsigned>(v);}else throw std::invalid_argument("Unknown option");}
    if(o.csv.empty()||o.sidecar.empty()||o.csv==o.sidecar||o.variant!="coordinator"||(o.wait_mode!="poll"&&o.wait_mode!="notify")||(o.format!="cu8"&&o.format!="cf32"))throw std::invalid_argument("Invalid source/output options");
    const std::array<std::string,8> faults{"none","append","byte","publication-pause","producer-exception","consumer-exception","pending-shutdown","held-shutdown"};
    if(std::find(faults.begin(),faults.end(),o.fault)==faults.end()||(o.variant=="none"&&o.fault!="none"&&o.fault!="append"&&o.fault!="producer-exception")||((o.fault=="pending-shutdown"||o.fault=="held-shutdown")&&o.variant!="coordinator"))throw std::invalid_argument("Unsupported fault/variant");
    return o;
}
} // namespace

int main(int argc,char** argv) {
    try {
        const auto o=options(argc,argv);const bool coordinated=true,use_notification=o.wait_mode=="notify";const I width=o.format=="cu8"?2:8;
        const unsigned owner_count=o.duration/10U, request_count=o.variant=="none"?0U:(o.duration+94U)/100U;
        Adapter adapter(coordinated,width);
        std::optional<notice::ReadyNotification> notification;if(use_notification)notification.emplace();
        side::Trace producer_side(static_cast<std::size_t>(request_count)*3U+32U,"producer"),consumer_side(static_cast<std::size_t>(request_count)*7U+32U,"consumer");
        std::vector<side::Mapping> mappings(static_cast<std::size_t>(request_count)+1U);
        std::atomic<I> announced_request{0};side::Mapping owner_binding{};
        Trace producer((static_cast<std::size_t>(prefill_count)+owner_count+drain_limit)*10U+16U,"producer"),consumer(static_cast<std::size_t>(request_count)*12U+32U,"consumer");
        std::vector<Descriptor> events(static_cast<std::size_t>(prefill_count)+owner_count+1U);
        std::vector<std::uint8_t> block(static_cast<std::size_t>(samples*width));
        std::atomic<I> latest{0};std::atomic<bool> stop{false},consumer_done{request_count==0},owner_done{false},pause_stored{false},pause_observed{false};
        std::array<Failure,3> failures{};std::array<unsigned,3> secondary_failures{};unsigned completed_owner=0,completed_requests=0,accepted=0,verified=0,eligible=0;
        std::uint64_t normal_stage_loads=0,normal_yield_calls=0,cleanup_stage_loads=0,cleanup_yield_calls=0;
        unsigned mapping_published_count=0,owner_binding_count=0,notification_count=0;
        coord::Ticket orphan;bool emergency_cleanup=false;
        I next_first=0,next_event=0;const I tick_base=now_ns();I origin=tick_base;
        const auto tick=[&](I now){return static_cast<coord::Tick>(now-tick_base);};
        const auto fail=[&](std::size_t slot,const char* role,const std::exception& error,std::optional<I> request={}){stop.store(true,std::memory_order_release);if(failures[slot].present){++secondary_failures[slot];return;}failures[slot].present=true;failures[slot].role=role;failures[slot].message=error.what();failures[slot].request=request;};
        const auto close_notice=[&](side::Trace& trace,const char* phase){if(!notification)return;auto& row=trace.add("close",phase);row.before=now_ns();notification->close();row.after=now_ns();row.status="closed";};
        const auto services=[&](I parent){if(!adapter.mailbox)return;for(unsigned i=0;i<3U;++i){auto& row=producer.add("service",i==0?"step1":i==1?"step2":"step3",parent);row.n[Before]=now_ns();row.n[Check]=row.n[Before];const auto result=adapter.mailbox->service(tick(*row.n[Before]));row.n[After]=now_ns();row.status=status_name(result.status);row.field=stage_name(result.stage);
            if(notification&&result.status==coord::Status::Ok&&result.stage==coord::Stage::Acquired){
                auto& bind=producer_side.add("bind","acquired");bind.owner=parent;bind.service=row.n[Id];bind.before=now_ns();
                const I selected_request=announced_request.load(std::memory_order_acquire);
                if(selected_request<=0||static_cast<std::size_t>(selected_request)>=mappings.size()){bind.after=now_ns();bind.status="failed";throw std::runtime_error("Invalid notification mapping identity");}
                owner_binding=mappings[static_cast<std::size_t>(selected_request)];++owner_binding_count;side::identity(bind,owner_binding);bind.after=now_ns();bind.status="ok";
                if(owner_binding.request!=selected_request||!owner_binding.token)throw std::runtime_error("Incomplete notification mapping");
            }
            if(notification&&result.status==coord::Status::Ok&&result.stage==coord::Stage::Ready){
                auto& signalled=producer_side.add("notify","ready");side::identity(signalled,owner_binding);signalled.owner=parent;signalled.service=row.n[Id];signalled.before=now_ns();
                const auto result_notice=notification->notify(owner_binding.token);++notification_count;signalled.after=now_ns();signalled.status=side::status_name(result_notice);
                if(result_notice!=notice::Status::Ok&&result_notice!=notice::Status::Closed)throw std::runtime_error("Matching readiness notification rejected");
                owner_binding={};
            }
        }
            auto& row=producer.add("reclaim","owner",parent);row.n[Before]=now_ns();adapter.history->reclaim();row.n[After]=now_ns();row.status="ok";};
        const auto iteration=[&](const char* phase,std::optional<I> due,bool timed,bool first_timed){
            auto& work=producer.add("owner",phase);const I parent=*work.n[Id];work.n[Due]=due;work.n[Before]=now_ns();work.status="running";
            try {
                if(timed||std::strcmp(phase,"prefill")==0) {
                    auto& generated=producer.add("generate","input",parent);generated.n[Before]=now_ns();generated.n[First]=next_first;generated.n[End]=next_first+samples;generated.n[Bytes]=static_cast<I>(block.size());
                    for(std::size_t i=0;i<block.size();++i)block[i]=pattern(static_cast<std::uint64_t>(next_first*width)+i);
                    generated.n[After]=now_ns();generated.status="ok";
                    if(first_timed&&o.fault=="producer-exception")throw std::runtime_error("Injected producer exception after generation");
                    auto& append=producer.add("append","input",parent);const auto current=adapter.state();interval(append,current,next_first,next_first+samples);append.n[EventId].reset();append.n[Bytes]=static_cast<I>(block.size())-(first_timed&&o.fault=="append"?1:0);append.n[Before]=now_ns();
                    const auto result=adapter.append(next_first,block,first_timed&&o.fault=="append");append.n[After]=now_ns();append.n[SourceStatus]=result;append.status=result==0?"ok":"rejected";
                    if(result!=0)throw std::runtime_error("Ingress append rejected; no replacement samples published");
                    next_first+=samples;
                    auto& state=producer.add("state","published_frontier",parent);state.n[Before]=now_ns();auto descriptor=adapter.state();state.n[After]=now_ns();state.status="ok";
                    descriptor.event=++next_event;source(state,descriptor);events[static_cast<std::size_t>(next_event)]=descriptor;
                    auto& pub=producer.add("publication","release_store",parent);source(pub,descriptor);pub.n[Before]=now_ns();latest.store(next_event,std::memory_order_release);
                    if(first_timed&&o.fault=="publication-pause") {
                        pause_stored.store(true,std::memory_order_release);const auto expires=Clock::now()+std::chrono::seconds(1);
                        while(!pause_observed.load(std::memory_order_acquire)&&!stop.load(std::memory_order_acquire)&&Clock::now()<expires)std::this_thread::yield();
                        if(!pause_observed.load(std::memory_order_acquire)){pub.n[After]=now_ns();pub.status="failed";throw std::runtime_error("Publication pause was not observed");}
                    }
                    pub.n[After]=now_ns();pub.status="ok";
                }
                if(timed||std::strcmp(phase,"drain")==0)services(parent);
                work.n[After]=now_ns();work.status="ok";
            }catch(...){work.n[After]=now_ns();work.status="failed";throw;}
        };
        for(unsigned i=0;i<prefill_count;++i)iteration("prefill",{},false,false);
        const auto memory_before=memory_sample(adapter);
        if(!memory_quiescent_full(memory_before))throw std::runtime_error("Prefill did not establish full quiescent retention");
        const unsigned logical_cpus=std::thread::hardware_concurrency();const auto resolution=cpu_resolution();
        const auto start=Clock::now()+std::chrono::milliseconds(20);origin=std::chrono::duration_cast<Ns>(start.time_since_epoch()).count();
        std::thread producer_thread,consumer_thread;
        const auto cpu_start=cpu_sample();
        try {
            producer_thread=std::thread([&]{
                try {for(unsigned i=0;i<owner_count&&!stop.load(std::memory_order_acquire);++i){const I due=origin+static_cast<I>(i)*period;std::this_thread::sleep_until(Clock::time_point(Ns(due)));if(stop.load(std::memory_order_acquire))break;iteration("timed",due,true,i==0);++completed_owner;}}
                catch(const std::exception& e){fail(0,"producer",e);}catch(...){const std::runtime_error e("Unknown producer exception");fail(0,"producer",e);}
                if(stop.load(std::memory_order_acquire)){try{close_notice(producer_side,"failure");}catch(const std::exception& e){fail(0,"producer-notification-close",e);}catch(...){const std::runtime_error e("Unknown notification close exception");fail(0,"producer-notification-close",e);}}
                try {
                    if(adapter.mailbox){for(unsigned i=0;i<drain_limit&&(!consumer_done.load(std::memory_order_acquire)||!adapter.mailbox->shutdown_acknowledged());++i){iteration("drain",{},false,false);std::this_thread::sleep_for(std::chrono::milliseconds(1));}
                        if(!adapter.mailbox->shutdown_acknowledged())throw std::runtime_error("Bounded coordinator shutdown drain exhausted");}
                    auto& end=producer.add("shutdown","owner");end.n[Before]=now_ns();end.n[After]=now_ns();end.status="ok";
                }catch(const std::exception& e){fail(0,"producer",e);}catch(...){const std::runtime_error e("Unknown producer drain exception");fail(0,"producer",e);}
                try{close_notice(producer_side,"shutdown");}catch(const std::exception& e){fail(0,"producer-notification-close",e);}catch(...){const std::runtime_error e("Unknown notification close exception");fail(0,"producer-notification-close",e);}
                owner_done.store(true,std::memory_order_release);
            });
            if(request_count)consumer_thread=std::thread([&]{
                coord::Ticket pending;I pending_id=0;Grant grant;grant.coordinated=coordinated;side::Mapping consumer_binding{};
                const auto poll_for_ready=[&](side::Row& observed_wait,bool cleanup){
                    observed_wait.stage_loads=0;observed_wait.yield_calls=0;
                    auto& total_loads=cleanup?cleanup_stage_loads:normal_stage_loads;auto& total_yields=cleanup?cleanup_yield_calls:normal_yield_calls;
                    const auto stage=[&]{++*observed_wait.stage_loads;++total_loads;return adapter.mailbox->stage();};
                    while(stage()!=coord::Stage::Ready&&!owner_done.load(std::memory_order_acquire)){++*observed_wait.yield_calls;++total_yields;std::this_thread::yield();}
                    const bool ready=stage()==coord::Stage::Ready;observed_wait.status=ready?"ready":"owner_ended";observed_wait.after=now_ns();return ready;
                };
                try {
                    for(unsigned i=0;i<request_count&&!stop.load(std::memory_order_acquire);++i) {
                        const I request=static_cast<I>(i)+1,due=origin+5000000+static_cast<I>(i)*request_period;
                        std::this_thread::sleep_until(Clock::time_point(Ns(due)));if(stop.load(std::memory_order_acquire))break;
                        if(i==0&&o.fault=="publication-pause"){const auto expires=Clock::now()+std::chrono::seconds(1);while(!pause_stored.load(std::memory_order_acquire)&&!stop.load(std::memory_order_acquire)&&Clock::now()<expires)std::this_thread::yield();if(!pause_stored.load(std::memory_order_acquire))throw std::runtime_error("Publication pause store absent");}
                        auto& selection=consumer.add("selection","acquire_load");selection.n[RequestId]=request;selection.n[Due]=due;selection.n[Before]=now_ns();const I selected=latest.load(std::memory_order_acquire);selection.n[After]=now_ns();
                        if(selected<=0||static_cast<std::size_t>(selected)>=events.size())throw std::runtime_error("Invalid publication event identity");
                        const auto descriptor=events[static_cast<std::size_t>(selected)];source(selection,descriptor);selection.status="ok";
                        if(i==0&&o.fault=="publication-pause")pause_observed.store(true,std::memory_order_release);
                        const I first=descriptor.end-window,deadline=*selection.n[After]+deadline_span;
                        auto& pre=consumer.add("eligibility","pre_call");interval(pre,descriptor,first,descriptor.end);pre.n[RequestId]=request;pre.n[Before]=now_ns();pre.n[Check]=pre.n[Before];pre.n[After]=now_ns();pre.n[Deadline]=deadline;pre.status=*pre.n[Check]>=deadline?"deadline_expired":"ok";
                        const char* outcome=pre.status;I post_check=*pre.n[Check];bool admitted=false;
                        if(*pre.n[Check]<deadline) {
                            if(notification){
                                consumer_binding={};auto& arm=consumer_side.add("arm","request");arm.request=request;arm.event=selected;arm.before=now_ns();const auto armed=notification->arm();arm.after=now_ns();arm.status=side::status_name(armed.status);
                                if(armed.status!=notice::Status::Ok){const std::runtime_error e("Notification arm rejected");fail(1,"consumer",e,request);adapter.mailbox->close();}
                                else{consumer_binding={armed.token,request,selected};side::identity(arm,consumer_binding);
                                    auto& published=consumer_side.add("map_publish","request");side::identity(published,consumer_binding);published.before=now_ns();mappings[static_cast<std::size_t>(request)]=consumer_binding;announced_request.store(request,std::memory_order_release);++mapping_published_count;published.after=now_ns();published.status="ok";}

                            }
                            auto& call=consumer.add("request",coordinated?"submit":"whole_copy");interval(call,descriptor,first,descriptor.end);call.n[RequestId]=request;call.n[Deadline]=deadline;call.n[Before]=now_ns();call.n[Check]=call.n[Before];
                            if(coordinated){const slabs::Request r{adapter.slab_stream,static_cast<std::uint64_t>(*descriptor.generation),static_cast<std::uint64_t>(*descriptor.pool),static_cast<std::uint64_t>(first),static_cast<std::uint64_t>(window)};
                                const auto submitted=adapter.mailbox->submit(r,tick(*call.n[Before]),tick(deadline));call.n[After]=now_ns();call.status=status_name(submitted.status);pending=submitted.ticket;pending_id=request;admitted=submitted.status==coord::Status::Ok;
                                if(i==0&&o.fault=="pending-shutdown")adapter.mailbox->close();
                                if(admitted){
                                    auto& wait=consumer_side.add("wait",use_notification?"notify":"poll");wait.request=request;wait.event=selected;wait.base=call.n[Id];wait.before=now_ns();wait.stage_loads=0;wait.yield_calls=0;
                                    if(notification){side::identity(wait,consumer_binding);wait.deadline=*wait.before+safety_wait_timeout;const auto waited=notification->wait_until(consumer_binding.token,Clock::time_point(Ns(*wait.deadline)));wait.after=now_ns();wait.status=side::status_name(waited);if(waited!=notice::Status::Ready){
                                        const std::runtime_error e("Notification safety wait did not become ready");fail(1,"consumer",e,request);adapter.mailbox->close();
                                        auto& cleanup=consumer_side.add("wait","cleanup_poll");side::identity(cleanup,consumer_binding);cleanup.base=call.n[Id];cleanup.before=now_ns();
                                        if(!poll_for_ready(cleanup,true))throw std::runtime_error("Owner ended before failed notification request could be taken");
                                    }}
                                    else{poll_for_ready(wait,false);}
                                    if(adapter.mailbox->stage()!=coord::Stage::Ready)throw std::runtime_error("Owner ended before pending response");
                                    auto& take=consumer.add("take","mailbox");interval(take,descriptor,first,descriptor.end);take.n[RequestId]=request;take.n[Deadline]=deadline;take.n[Before]=now_ns();take.n[Check]=take.n[Before];grant.reply=take_pending(*adapter.mailbox,pending,tick(*take.n[Before]));take.n[After]=now_ns();take.status=status_name(grant.reply.status());take.n[SourceStatus]=static_cast<I>(grant.reply.info().source_status);if(grant.valid())observed(take,grant,selected);outcome=take.status;
                                    if(pending)throw std::runtime_error("Non-consuming take rejected; pending ticket retained for cleanup");}
                                else{outcome=call.status;if(notification&&consumer_binding.token){auto& abandoned=consumer_side.add("abandon","rejected");side::identity(abandoned,consumer_binding);abandoned.base=call.n[Id];abandoned.before=now_ns();const auto discarded=notification->abandon(consumer_binding.token);abandoned.after=now_ns();abandoned.status=side::status_name(discarded);if(discarded!=notice::Status::Ok&&discarded!=notice::Status::Closed)throw std::runtime_error("Rejected admission notification cleanup failed");consumer_binding={};}}
                            }else{grant.whole=adapter.whole->snapshot(adapter.whole_stream,static_cast<std::uint64_t>(first),static_cast<std::uint64_t>(window));call.n[After]=now_ns();call.n[SourceStatus]=static_cast<I>(grant.whole.status());call.status=grant.valid()?"ok":grant.whole.status()==iq::Status::Busy?"busy":"source_error";outcome=call.status;}
                            auto& post=consumer.add("eligibility","post_call");interval(post,descriptor,first,descriptor.end);post.n[RequestId]=request;post.n[Deadline]=deadline;post.n[Before]=now_ns();post_check=*post.n[Before];post.n[Check]=post_check;post.n[After]=now_ns();post.status=post_check>=deadline?"deadline_expired":"ok";
                            if(post_check>=deadline&&grant.valid())outcome="deadline_expired";
                        }
                        if(grant.valid()) {
                            ++accepted;if(i==0&&o.fault=="held-shutdown")adapter.mailbox->close();
                            auto& verification=consumer.add("verification","exact_bytes");verification.n[RequestId]=request;verification.n[Before]=now_ns();verification.n[Deadline]=deadline;observed(verification,grant,selected);
                            try {if(i==0&&o.fault=="consumer-exception")throw std::runtime_error("Injected consumer exception while holding grant");verify(grant,verification,descriptor,first,i==0&&o.fault=="byte");verification.status="ok";++verified;}
                            catch(const VerifyError& e){verification.status="mismatch";verification.field=e.field;verification.n[Expected]=e.expected;verification.n[Actual]=e.actual;verification.n[Offset]=e.offset;fail(1,"consumer",e,request);failures[1].field=e.field;failures[1].expected=e.expected;failures[1].actual=e.actual;failures[1].offset=e.offset;outcome="failed";}
                            catch(const std::exception& e){verification.status="aborted";fail(1,"consumer",e,request);outcome="failed";}
                            catch(...){verification.status="aborted";const std::runtime_error e("Unknown verifier exception");fail(1,"consumer",e,request);outcome="failed";}
                            verification.n[After]=now_ns();
                            auto& release=consumer.add("release",stop.load(std::memory_order_acquire)?"failure":(o.fault=="held-shutdown"?"shutdown":"normal"));observed(release,grant,selected);release.n[RequestId]=request;release.n[Before]=now_ns();grant.reset();release.n[After]=now_ns();release.status="ok";
                        }
                        auto& finished=consumer.add("outcome","request");interval(finished,descriptor,first,descriptor.end);finished.n[RequestId]=request;finished.n[Before]=now_ns();finished.n[After]=now_ns();finished.n[Check]=post_check;finished.n[Deadline]=deadline;finished.status=outcome;++completed_requests;if(std::strcmp(outcome,"ok")==0)++eligible;
                    }
                }catch(const std::exception& e){fail(1,"consumer",e,pending_id?std::optional<I>(pending_id):std::nullopt);}catch(...){const std::runtime_error e("Unknown consumer exception");fail(1,"consumer",e);}
                try {
                    if(adapter.mailbox)adapter.mailbox->close();
                    if(pending){auto& cleanup=consumer_side.add("wait","cleanup_poll");if(consumer_binding.token)side::identity(cleanup,consumer_binding);cleanup.request=pending_id;cleanup.before=now_ns();if(poll_for_ready(cleanup,true)){auto& row=consumer.add("take","shutdown");row.n[RequestId]=pending_id;row.n[Before]=now_ns();row.n[Check]=row.n[Before];auto discarded=take_pending(*adapter.mailbox,pending,tick(*row.n[Before]));row.n[After]=now_ns();row.status=status_name(discarded.status());discarded.reset();}}
                    grant.reset();close_notice(consumer_side,"shutdown");auto& end=consumer.add("shutdown","client");end.n[Before]=now_ns();end.n[After]=now_ns();end.status="ok";
                }catch(const std::exception& e){fail(1,"consumer",e,pending_id);}catch(...){const std::runtime_error e("Unknown client cleanup exception");fail(1,"consumer",e,pending_id);}
                // Joined main may assume both roles only if exceptional cleanup
                // exhausted its trace/drain budget. This never counts as a run.
                grant.reset();orphan=pending;consumer_done.store(true,std::memory_order_release);
            });
        }catch(const std::exception& e){fail(2,"launch",e);consumer_done.store(true,std::memory_order_release);if(adapter.mailbox)adapter.mailbox->close();}
        if(consumer_thread.joinable())consumer_thread.join();
        if(producer_thread.joinable())producer_thread.join();
        if(notification&&!notification->state().closed){
            emergency_cleanup=true;
            try{close_notice(producer_side,"postjoin");const std::runtime_error e("Post-join notification close required");fail(2,"notification-cleanup",e);}
            catch(const std::exception& e){fail(2,"notification-cleanup",e);}catch(...){const std::runtime_error e("Unknown post-join notification close exception");fail(2,"notification-cleanup",e);}
        }
        const auto cpu_end=cpu_sample();
        const auto memory_after=memory_sample(adapter);
        const bool cpu_valid=cpu_start.value&&cpu_end.value&&*cpu_end.value>=*cpu_start.value;
        if(!cpu_valid){const std::runtime_error e("Process CPU accounting unavailable or regressed");fail(2,"measurement",e);}
        if(!memory_quiescent_full(memory_after)){const std::runtime_error e("Final ownership/retention endpoint is not quiescent and full");fail(2,"measurement",e);}
        if(adapter.mailbox&&!adapter.mailbox->shutdown_acknowledged()) {
            emergency_cleanup=true;adapter.mailbox->close();
            for(unsigned i=0;i<8U&&!adapter.mailbox->shutdown_acknowledged();++i){
                if(adapter.mailbox->stage()==coord::Stage::Ready&&orphan){auto discarded=take_pending(*adapter.mailbox,orphan,tick(now_ns()));discarded.reset();}
                adapter.mailbox->service(tick(now_ns()));
            }
            const std::runtime_error error("Exceptional post-join cleanup required; excluded from measured owner iterations");fail(2,"cleanup",error);
        }
        const bool ack=!adapter.mailbox||adapter.mailbox->shutdown_acknowledged();
        bool sidecar_written=false;std::string sidecar_error;try{side::write(o.sidecar,producer_side,consumer_side,origin);sidecar_written=true;}catch(const std::exception& e){sidecar_error=e.what();fail(2,"sidecar",e);}
        const auto notification_after=notification?notification->state():notice::State{};
        bool trace_written=false;std::string trace_error;try{write_trace(o.csv,producer,consumer,origin);trace_written=true;}catch(const std::exception& e){trace_error=e.what();fail(2,"trace",e);}
        bool any_failure=false;for(const auto& f:failures)any_failure=any_failure||f.present;
        const bool complete=!any_failure&&completed_owner==owner_count&&completed_requests==request_count&&ack&&trace_written&&sidecar_written;
        I qpf=0;
#ifdef _WIN32
        LARGE_INTEGER frequency{};if(QueryPerformanceFrequency(&frequency))qpf=frequency.QuadPart;
#endif
        const I tolerance=qpf>0?(std::max)(I{1000},static_cast<I>(std::ceil(1000000000.0/static_cast<double>(qpf)))):1000;
        auto& out=std::cout;out<<"{\"schema_version\":5,\"variant\":";quoted(out,o.variant);out<<",\"format\":";quoted(out,o.format);out<<",\"duration_ms\":"<<o.duration<<",\"producer_period_ns\":"<<period<<",\"request_period_ns\":"<<request_period<<",\"snapshot_samples\":"<<window<<",\"deadline_ns\":"<<deadline_span<<",\"width\":"<<width<<",\"rate_hz\":"<<rate<<",\"stream_id\":1,\"epoch\":1,\"frequency_hz\":451100000,\"prefill_iterations\":"<<prefill_count<<",\"expected_owner_iterations\":"<<owner_count<<",\"expected_requests\":"<<request_count<<",\"completed_owner_iterations\":"<<completed_owner<<",\"completed_requests\":"<<completed_requests<<",\"accepted\":"<<accepted<<",\"verified\":"<<verified<<",\"eligible\":"<<eligible<<",\"complete\":"<<(complete?"true":"false")<<",\"shutdown_acknowledged\":"<<(ack?"true":"false")<<",\"fault\":";quoted(out,o.fault);
        out<<",\"base_projection_schema_version\":4,\"wait_mode\":";quoted(out,o.wait_mode);out<<",\"safety_wait_timeout_ns\":"<<safety_wait_timeout<<",\"sidecar_written\":"<<(sidecar_written?"true":"false")<<",\"sidecar_error\":";if(sidecar_error.empty())out<<"null";else quoted(out,sidecar_error);
        const auto accounting=notice::ReadyNotification::accounting();
        out<<",\"wait_counts\":{\"normal_stage_loads\":"<<normal_stage_loads<<",\"normal_yield_calls\":"<<normal_yield_calls<<",\"cleanup_stage_loads\":"<<cleanup_stage_loads<<",\"cleanup_yield_calls\":"<<cleanup_yield_calls<<"},\"mapping_published_count\":"<<mapping_published_count<<",\"owner_binding_count\":"<<owner_binding_count<<",\"notification_count\":"<<notification_count;
        out<<",\"notification_accounting\":{\"object_storage_bytes\":"<<sizeof(notification)<<",\"active_object_bytes\":"<<(use_notification?accounting.object_bytes:0)<<",\"shared_domain_counter_bytes\":"<<accounting.shared_domain_counter_bytes<<",\"token_value_bytes\":"<<accounting.token_bytes<<",\"mapping_entry_bytes\":"<<sizeof(side::Mapping)<<",\"mapping_capacity\":"<<mappings.capacity()<<",\"mapping_reserved_bytes\":"<<mappings.capacity()*sizeof(side::Mapping)<<",\"mapping_publication_atomic_bytes\":"<<sizeof(announced_request)<<",\"owner_binding_bytes\":"<<sizeof(owner_binding)<<",\"consumer_binding_bytes\":"<<sizeof(side::Mapping)<<",\"mapping_vector_object_bytes\":"<<sizeof(mappings)<<",\"sidecar_trace_object_bytes\":"<<sizeof(producer_side)+sizeof(consumer_side)<<",\"sidecar_row_bytes\":"<<sizeof(side::Row)<<",\"producer_reserved_capacity\":"<<producer_side.rows.capacity()<<",\"consumer_reserved_capacity\":"<<consumer_side.rows.capacity()<<",\"producer_trace_capacity\":"<<producer_side.bound<<",\"consumer_trace_capacity\":"<<consumer_side.bound<<",\"sidecar_reserved_bytes\":"<<(producer_side.rows.capacity()+consumer_side.rows.capacity())*sizeof(side::Row)<<",\"producer_rows\":"<<producer_side.rows.size()<<",\"consumer_rows\":"<<consumer_side.rows.size()<<",\"dropped_event_count\":"<<producer_side.dropped+consumer_side.dropped<<",\"opaque_runtime_allocation\":true}";
        out<<",\"notification_state_after\":";if(!notification)out<<"null";else out<<"{\"domain\":"<<notification_after.domain<<",\"last_generation\":"<<notification_after.last_generation<<",\"predicate_checks\":"<<notification_after.predicate_checks<<",\"armed\":"<<(notification_after.armed?"true":"false")<<",\"ready\":"<<(notification_after.ready?"true":"false")<<",\"waiting\":"<<(notification_after.waiting?"true":"false")<<",\"closed\":"<<(notification_after.closed?"true":"false")<<'}';
        out<<",\"secondary_failure_count\":"<<secondary_failures[0]+secondary_failures[1]+secondary_failures[2]<<",\"cpu_time_ns\":";if(cpu_valid)out<<*cpu_end.value-*cpu_start.value;else out<<"null";
        out<<",\"process_cpu\":{\"api\":";
#ifdef _WIN32
        out<<"\"GetProcessTimes\",\"resolution_kind\":\"storage_unit_not_accounting_resolution\"";
#else
        out<<"\"CLOCK_PROCESS_CPUTIME_ID\",\"resolution_kind\":\"clock_getres\"";
#endif
        out<<",\"scope\":\"before_thread_launch_through_join\",\"start_before_ns\":"<<cpu_start.before-origin<<",\"start_after_ns\":"<<cpu_start.after-origin<<",\"end_before_ns\":"<<cpu_end.before-origin<<",\"end_after_ns\":"<<cpu_end.after-origin;
        out<<",\"start_value_ns\":";if(cpu_start.value)out<<*cpu_start.value;else out<<"null";
        out<<",\"end_value_ns\":";if(cpu_end.value)out<<*cpu_end.value;else out<<"null";
        out<<",\"elapsed_ns\":";if(cpu_valid)out<<*cpu_end.value-*cpu_start.value;else out<<"null";
        out<<",\"wall_elapsed_min_ns\":"<<cpu_end.before-cpu_start.after<<",\"wall_elapsed_max_ns\":"<<cpu_end.after-cpu_start.before;
        out<<",\"api_resolution_ns\":";if(resolution)out<<*resolution;else out<<"null";
        out<<",\"logical_cpu_count\":";if(logical_cpus)out<<logical_cpus;else out<<"null";
        out<<",\"sanity_allowance_per_logical_cpu_ns\":20000000,\"start_error\":"<<cpu_start.error<<",\"end_error\":"<<cpu_end.error<<",\"valid\":"<<(cpu_valid?"true":"false")<<'}';
        out<<",\"source_memory_before\":";write_memory(out,memory_before,origin);out<<",\"source_memory_after\":";write_memory(out,memory_after,origin);
        out<<",\"abi\":{\"pointer_bytes\":"<<sizeof(void*)<<",\"credit_history_bytes\":"<<sizeof(iq::CreditHistory)<<",\"snapshot_lease_bytes\":"<<sizeof(iq::SnapshotLease)<<",\"slab_history_bytes\":"<<sizeof(slabs::History)<<",\"slab_budget_bytes\":"<<sizeof(slabs::ProcessBudget)<<",\"coordinator_budget_bytes\":"<<sizeof(coord::Budget)<<",\"mailbox_bytes\":"<<sizeof(coord::Mailbox)<<",\"reply_bytes\":"<<sizeof(coord::Reply)<<'}';
        out<<",\"emergency_cleanup\":"<<(emergency_cleanup?"true":"false")<<",\"trace_written\":"<<(trace_written?"true":"false")<<",\"trace_error\":";if(trace_error.empty())out<<"null";else quoted(out,trace_error);
        out<<",\"csv_rows\":"<<producer.rows.size()+consumer.rows.size()<<",\"producer_trace_capacity\":"<<producer.bound<<",\"consumer_trace_capacity\":"<<consumer.bound<<",\"trace_reserved_bytes\":"<<(producer.rows.capacity()+consumer.rows.capacity())*sizeof(Row)<<",\"publication_descriptor_bytes\":"<<events.capacity()*sizeof(Descriptor)<<",\"input_buffer_bytes\":"<<block.capacity()<<",\"dropped_event_count\":"<<producer.dropped+consumer.dropped<<",\"performance_eligible\":false,\"cross_thread_tolerance_ns\":"<<tolerance<<",\"clock\":{\"is_steady\":"<<(Clock::is_steady?"true":"false")<<",\"period_num\":"<<Clock::period::num<<",\"period_den\":"<<Clock::period::den<<",\"qpc_frequency_hz\":";if(qpf)out<<qpf;else out<<"null";
        out<<",\"provenance\":\"steady_clock nominal period; declared cross-role tolerance max(1000ns,QPC tick when available), not empirical calibration or proof of steady_clock QPC mapping\"},\"failures\":[";
        bool comma=false;for(const auto& f:failures)if(f.present){if(comma)out<<',';comma=true;out<<"{\"role\":";quoted(out,f.role);out<<",\"message\":";quoted(out,f.message);out<<",\"field\":";if(f.field.empty())out<<"null";else quoted(out,f.field);const auto number=[&](const char* name,std::optional<I> value){out<<",\""<<name<<"\":";if(value)out<<*value;else out<<"null";};number("request_id",f.request);number("expected",f.expected);number("actual",f.actual);number("offset",f.offset);out<<'}';}out<<"]}\n";
        return complete?0:2;
    }catch(const std::exception& e){std::cerr<<"Comparison setup failure: "<<e.what()<<'\n';return 1;}
}
