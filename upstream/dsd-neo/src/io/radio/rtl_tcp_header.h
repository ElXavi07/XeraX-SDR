// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstddef>
#include <cstdint>

// Standard rtl_tcp sends exactly 12 bytes: magic, tuner type, gain count.
// The gain values themselves are NOT transmitted. The next byte is I/Q.
template <typename Receive>
bool rtl_tcp_read_header(Receive receive) {
    uint8_t header[12];
    size_t used = 0;
    while (used < sizeof(header)) {
        const int count = receive(header + used, sizeof(header) - used);
        if (count <= 0 || static_cast<size_t>(count) > sizeof(header) - used) return false;
        used += static_cast<size_t>(count);
    }
    return header[0] == 'R' && header[1] == 'T' && header[2] == 'L' && header[3] == '0';
}
