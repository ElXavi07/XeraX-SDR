// SPDX-License-Identifier: GPL-3.0-or-later
#include "../upstream/dsd-neo/src/io/radio/rtl_tcp_header.h"
#include <algorithm>
#include <cassert>
#include <cstring>
#include <vector>
int main() {
    for (size_t fragment : {1U, 2U, 5U, 12U, 100U}) {
        for (uint32_t gains : {0U, 29U, 4095U, 0xffffffffU}) {
            std::vector<uint8_t> wire{'R','T','L','0',0,0,0,5,
                uint8_t(gains>>24),uint8_t(gains>>16),uint8_t(gains>>8),uint8_t(gains),42,199,55,180};
            size_t offset=0;
            assert(rtl_tcp_read_header([&](uint8_t* dst,size_t n) {
                n=std::min({n,fragment,wire.size()-offset});
                std::memcpy(dst,wire.data()+offset,n); offset+=n; return int(n);
            }));
            assert(offset==12 && wire[offset]==42 && wire[offset+1]==199);
        }
    }
    for (size_t length=0;length<12;++length) {
        size_t offset=0; uint8_t wire[12]={'R','T','L','0'};
        assert(!rtl_tcp_read_header([&](uint8_t* dst,size_t n) {
            n=std::min(n,length-offset); std::memcpy(dst,wire+offset,n); offset+=n; return int(n);
        }));
    }
    assert(!rtl_tcp_read_header([](uint8_t* dst,size_t n) { std::memset(dst,0,n); return int(n); }));
    assert(!rtl_tcp_read_header([](uint8_t*,size_t) { return -1; }));
}
