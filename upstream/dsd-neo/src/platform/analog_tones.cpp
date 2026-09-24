// SPDX-License-Identifier: GPL-3.0-or-later
// DCS parity matrix and standard code set derived from SDRangel:
// Copyright (C) 2021 Edouard Griffiths, F4EXB <f4exb06@gmail.com>
// https://github.com/f4exb/sdrangel/tree/master/sdrbase/{util,dsp}
// Streaming detector, tone confidence and publication by XeraX SDR contributors.
#include <dsd-neo/platform/analog_tones.h>
#include <array>
#include <algorithm>
#include <bitset>
#include <cmath>
#include <chrono>
#include <mutex>
namespace {
constexpr double pi=3.14159265358979323846;
constexpr double tones[]={67,69.3,71.9,74.4,77,79.7,82.5,85.4,88.5,91.5,94.8,97.4,100,103.5,107.2,110.9,
114.8,118.8,123,127.3,131.8,136.5,141.3,146.2,151.4,156.7,159.8,162.2,165.5,167.9,171.3,173.8,177.3,179.9,
183.5,186.2,189.9,192.8,196.6,199.5,203.5,206.5,210.7,218.1,225.7,229.1,233.6,241.8,250.3,254.1};
constexpr unsigned codes[]={19,21,22,25,26,30,35,39,41,43,44,53,57,58,59,60,74,76,77,78,82,85,89,90,92,99,101,106,109,110,114,117,122,124,133,138,147,149,150,163,164,165,166,169,170,173,177,179,181,182,185,188,198,201,205,213,217,218,227,230,233,238,244,245,249,265,266,267,275,281,282,293,294,298,300,301,306,308,309,310,323,326,334,339,342,346,358,373,390,394,404,407,409,410,428,434,436,451,458,467,473,474,476,483,492};
constexpr unsigned parity[]={0xa4f,0xf68,0x7b4,0x3da,0x1ed,0xab9,0xf13,0xdc6,0x6e3,0x93e,0x49f};
unsigned word(unsigned c) {
    unsigned data=c|0x800, v=data;
    for (unsigned i=0;i<11;i++) v |= unsigned(std::bitset<12>(data & parity[i]).count()&1)<<(22-i);
    return v;
}
struct Clock { double phase=0; unsigned bits=0; unsigned since[2]={0,0}; int candidate[2]={-1,-1},hits[2]={0,0}; };
struct Detector {
    unsigned rate=0; uint64_t channel=0; double decimate=0,lp1=0,lp2=0,dc=0;
    std::array<double,800> window{}; size_t used=0; int previousTone=-1,toneHits=0;
    std::array<Clock,8> clocks{}; dsd_analog_tones result{0,-1,0,-1};
    std::chrono::steady_clock::time_point last{},dcsAt{};
    Detector() { for(size_t i=0;i<clocks.size();++i) clocks[i].phase=double(i)/clocks.size(); }
    void sample(double x) {
        window[used++]=x;
        for (auto& clock:clocks) {
            clock.phase+=134.4/800.0;
            if(clock.phase<1) continue;
            clock.phase-=1; clock.bits=(clock.bits>>1)|((x>0 ? 1u:0u)<<22); ++clock.since[0]; ++clock.since[1];
            // Exact repeated codewords: never turn a corrected random word into a tone ID.
            for (int polarity=0;polarity<2;polarity++) {
                unsigned w=clock.bits^(polarity ? 0x7fffff:0);
                if((w&0xe00)!=0x800) continue;
                unsigned c=w&511;
                if(!std::binary_search(std::begin(codes),std::end(codes),c)||word(c)!=w) continue;
                int id=int(c)+polarity*512;
                if(clock.candidate[polarity]==id && clock.since[polarity]==23) ++clock.hits[polarity];
                else {clock.candidate[polarity]=id;clock.hits[polarity]=1;}
                clock.since[polarity]=0;
                if(clock.hits[polarity]>=4) {if(polarity) result.dcs_inverse_code=int(c); else result.dcs_code=int(c); dcsAt=std::chrono::steady_clock::now();}
            }
        }
        if(used!=window.size()) return;
        used=0; double mean=0,energy=0; for(auto v:window)mean+=v;mean/=window.size();
        for(auto v:window) energy+=(v-mean)*(v-mean);
        double best=0,second=0;int index=-1;
        for(size_t k=0;k<(sizeof(tones)/sizeof(tones[0]));k++) {
            double a=2*std::cos(2*pi*tones[k]/800),u=0,v=0;
            for(auto x:window) {double q=x-mean+a*u-v;v=u;u=q;}
            double p=u*u+v*v-a*u*v;
            if(p>best){second=best;best=p;index=int(k);}else second=std::max(second,p);
        }
        bool confident=energy>1e-8 && best*2/(window.size()*energy)>0.55 && best>second*2.3;
        if(!confident){previousTone=-1;toneHits=0;result.ctcss_hz=0;}
        else {toneHits=index==previousTone ? toneHits+1:1;previousTone=index;result.ctcss_hz=toneHits>=2 ? tones[index]:0;}
    }
};
std::mutex mutex; Detector detector;
}
extern "C" void dsd_analog_tones_reset(){std::lock_guard<std::mutex> lock(mutex);detector=Detector();}
extern "C" void dsd_analog_tones_feed(const float* samples,size_t count,unsigned rate,uint64_t channel,int enabled){
    std::lock_guard<std::mutex> lock(mutex);
    if(!enabled||!samples||rate<8000||rate>192000){detector=Detector();return;}
    auto& d=detector;
    if(d.rate!=rate||d.channel!=channel){d=Detector();d.rate=rate;d.channel=channel;}
    const double a=1-std::exp(-2*pi*300/rate),h=1-std::exp(-2*pi*20/rate);
    d.last=std::chrono::steady_clock::now();
    for(size_t i=0;i<count;i++){
        double x=std::isfinite(samples[i])?samples[i]:0;
        d.dc+=h*(x-d.dc);d.lp1+=a*(x-d.dc-d.lp1);d.lp2+=a*(d.lp1-d.lp2);
        d.decimate+=800;if(d.decimate>=rate){d.decimate-=rate;d.sample(d.lp2);}
    }
}
extern "C" void dsd_analog_tones_get(dsd_analog_tones* out){
    if(!out)return;std::lock_guard<std::mutex> lock(mutex);
    *out=detector.result;auto now=std::chrono::steady_clock::now();
    if(now-detector.last>std::chrono::milliseconds(500))*out={0,-1,0,-1};
    else if(now-detector.dcsAt>std::chrono::milliseconds(800)){out->dcs_code=-1;out->dcs_inverse_code=-1;}
}
