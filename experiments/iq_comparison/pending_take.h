// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "iq_coordinator.h"

namespace xerax::experiment::comparison {
// A rejected clock/ticket or a not-yet-ready slot has NOT consumed the pending
// completion. Keep its identity available to exception/shutdown cleanup.
inline coordinator::Reply take_pending(coordinator::Mailbox& mailbox,
                                       coordinator::Ticket& pending,
                                       coordinator::Tick tick) {
    auto reply = mailbox.take(pending, tick);
    switch (reply.status()) {
    case coordinator::Status::Ok:
    case coordinator::Status::SourceError:
    case coordinator::Status::Closed:
    case coordinator::Status::Cancelled:
    case coordinator::Status::DeadlineExpired:
        pending = {};
        break;
    default:
        break;
    }
    return reply;
}
} // namespace xerax::experiment::comparison
