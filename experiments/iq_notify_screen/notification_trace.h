// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "ready_notification.h"
#include <cstdint>
#include <fstream>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

namespace xerax::experiment::notification_trace {
using I = std::int64_t;
struct Mapping { notification::Token token{}; I request = 0; I event = 0; };
struct Row {
    const char* kind = "";
    const char* phase = "";
    const char* role = "";
    const char* status = "running";
    std::size_t id = 0;
    std::optional<I> request, event, owner, service, base, before, after, deadline;
    std::optional<std::uint64_t> domain, generation, stage_loads, yield_calls;
};
struct Trace {
    std::vector<Row> rows;
    std::size_t bound, dropped = 0;
    const char* role;
    Trace(std::size_t capacity, const char* name):bound(capacity),role(name){rows.reserve(capacity);}
    Row& add(const char* kind,const char* phase) {
        if(rows.size()==bound){++dropped;throw std::runtime_error("Notification sidecar capacity exhausted");}
        rows.push_back({});auto& r=rows.back();r.kind=kind;r.phase=phase;r.role=role;r.id=rows.size();return r;
    }
};
inline void identity(Row& row,const Mapping& mapping) {
    row.request=mapping.request;row.event=mapping.event;
    row.domain=mapping.token.domain;row.generation=mapping.token.generation;
}
inline const char* status_name(notification::Status value) {
    using notification::Status;
    switch(value) {
    case Status::Ok:return "ok";case Status::Ready:return "ready";
    case Status::AlreadyReady:return "already_ready";case Status::Busy:return "busy";
    case Status::NotCurrent:return "not_current";case Status::TimedOut:return "timed_out";
    case Status::Closed:return "closed";case Status::CounterExhausted:return "counter_exhausted";
    }return "unknown";
}
inline void write(const std::string& path,const Trace& producer,const Trace& consumer,I origin) {
    std::ofstream out(path);if(!out)throw std::runtime_error("Cannot open notification sidecar");
    out<<"kind,phase,role,id,request_id,event_id,token_domain,token_generation,parent_owner_id,parent_service_id,base_row_id,before_ns,after_ns,status,deadline_ns,stage_loads,yield_calls\n";
    for(const auto* trace:{&producer,&consumer})for(const auto& r:trace->rows) {
        const auto n=[&](std::optional<I> value,bool time=false){if(value)out<<(*value-(time?origin:0));};
        out<<r.kind<<','<<r.phase<<','<<r.role<<','<<r.id<<',';n(r.request);out<<',';n(r.event);out<<',';
        if(r.domain){out<<*r.domain;}out<<',';if(r.generation){out<<*r.generation;}out<<',';
        n(r.owner);out<<',';n(r.service);out<<',';n(r.base);out<<',';n(r.before,true);out<<',';n(r.after,true);out<<','<<r.status<<',';n(r.deadline,true);out<<',';
        if(r.stage_loads){out<<*r.stage_loads;}out<<',';if(r.yield_calls){out<<*r.yield_calls;}out<<'\n';
    }
    out.flush();if(!out)throw std::runtime_error("Notification sidecar write failed");
    out.close();if(!out)throw std::runtime_error("Notification sidecar close failed");
}
} // namespace xerax::experiment::notification_trace
