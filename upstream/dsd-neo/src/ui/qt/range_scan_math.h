// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>

namespace xerax::range_scan {
// Integer Hz throughout: repeated decimal addition must never drift off the grid.
struct Plan {
    uint32_t first=440000000, last=450000000, step=12500;
    int count() const { return step && last>=first ? int((uint64_t(last)-first)/step+1) : 0; }
    uint32_t frequency(int index) const { return uint32_t(uint64_t(first)+uint64_t(index)*step); }
    bool valid() const {
        return first>=24000000 && last<=1766000000 && last>=first && step>=2500 && step<=100000
            && uint64_t(last)-first<=50000000 && count()<=10001;
    }
};
struct Tile { int begin=0, end=0; uint32_t center=0; };
inline Tile tile(const Plan& p,int begin,uint32_t span) {
    // Leave filter roll-off at both edges out of the survey. Tile boundaries are
    // grid indices, so small ranges and non-divisible endpoints have no gaps.
    const int channels=std::max(1,int(double(span)*0.60/p.step));
    const int end=std::min(p.count(),begin+channels);
    return {begin,end,uint32_t((uint64_t(p.frequency(begin))+p.frequency(end-1))/2)};
}
struct Strength { bool valid=false; double excess=0; };
inline Strength strength(const float* bins,int count,uint32_t center,uint32_t span,uint32_t frequency,uint32_t step) {
    if(!bins || count<64 || !span || step<2500) return {};
    const double binHz=double(span)/count;
    // At least two FFT bins per channel are needed to distinguish neighbors.
    if(binHz>step/2.0 || std::abs(double(frequency)-center)>span*0.37) return {};
    const double position=(double(frequency)-center)/binHz+count/2.0;
    const int lo=std::max(2,int(std::ceil(position-std::min(step*0.42,6000.0)/binHz)));
    const int hi=std::min(count-3,int(std::floor(position+std::min(step*0.42,6000.0)/binHz)));
    if(hi-lo<1) return {};
    std::vector<float> noise;
    const int radius=std::max(12,int(90000/binHz));
    for(int i=std::max(2,int(position)-radius);i<=std::min(count-3,int(position)+radius);++i) {
        if(i>=lo-3 && i<=hi+3) continue;
        if(std::isfinite(bins[i])) noise.push_back(bins[i]);
    }
    if(noise.size()<12) return {};
    auto mid=noise.begin()+noise.size()/2;
    std::nth_element(noise.begin(),mid,noise.end());
    double top=-std::numeric_limits<double>::infinity(),second=top;
    int topIndex=-1;
    for(int i=lo;i<=hi;++i) if(std::isfinite(bins[i]) && bins[i]>top) {top=bins[i];topIndex=i;}
    if(topIndex<0) return {};
    // Require an adjacent bin as well as the peak; a lone numerical/DC spike
    // must not turn an entire scan into an endless decoder acquisition.
    for(int i:{topIndex-1,topIndex+1}) if(i>=lo && i<=hi && std::isfinite(bins[i])) second=std::max(second,double(bins[i]));
    if(!std::isfinite(second)) return {};
    return {true,std::min(top,double(second)+5.0)-*mid};
}
}
