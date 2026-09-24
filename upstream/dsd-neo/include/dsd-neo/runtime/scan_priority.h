// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef XERAX_SCAN_PRIORITY_H
#define XERAX_SCAN_PRIORITY_H
#include <stddef.h>
#include <stdint.h>
/* flags: bit 0 = eligible, bit 1 = priority. Alternates the classes while
 * preserving an independent round-robin cursor for each. No call is preempted
 * here: the coordinator invokes this only after its hold/visit policy allows. */
static inline size_t dsd_scan_priority_choose(const uint8_t* flags, size_t count, size_t active,
                                               size_t normal_cursor, size_t priority_cursor) {
    if (!flags || count < 2 || active >= count) return active;
    int want_priority = (flags[active] & 2) == 0;
    size_t cursor = want_priority ? priority_cursor : normal_cursor;
    for (size_t i = 1; i <= count; ++i) {
        size_t next = (cursor + i) % count;
        if (next != active && (flags[next] & 1) && (((flags[next] & 2) != 0) == want_priority)) return next;
    }
    for (size_t i = 1; i < count; ++i) {
        size_t next = (active + i) % count;
        if (flags[next] & 1) return next;
    }
    return active;
}
#endif
