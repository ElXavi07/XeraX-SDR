// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cmath>
#include <cstdint>
namespace xerax {
struct ReceptionReading {
    int64_t ms=0;
    uint64_t good=0,bad=0;
    double frequency=0,snr=0;
    bool running=false,snrValid=false;
};
// A fixed-channel, fixed-duration observation. Counters are control-frame FEC,
// not voice intelligibility or a comparison to any other receiver.
class ReceptionSample {
public:
    ReceptionReading first{},last{};
    double snrSum=0;
    unsigned samples=0;
    bool active=false,valid=false;
    void begin(const ReceptionReading& r) { first=last=r; snrSum=0; samples=0; active=valid=r.running; }
    bool add(const ReceptionReading& r) {
        if(!active) return false;
        if(!r.running || !std::isfinite(r.frequency) || std::abs(r.frequency-first.frequency)>100
            || r.good<last.good || r.bad<last.bad || r.ms<=last.ms) { valid=false; active=false; return true; }
        last=r;
        if(r.snrValid && std::isfinite(r.snr)) { snrSum+=r.snr; ++samples; }
        if(r.ms-first.ms>=30000) { active=false; return true; }
        return false;
    }
    uint64_t accepted() const { return last.good-first.good; }
    uint64_t rejected() const { return last.bad-first.bad; }
};
}
