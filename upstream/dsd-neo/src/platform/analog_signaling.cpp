// SPDX-License-Identifier: GPL-3.0-or-later
// FleetSync field layout, CRC parameters and MDC deinterleaver adapted from
// SDRTrunk, Copyright (C) 2014-2018 Dennis Sheirer, GPL-3.0-or-later.
// See docs/ANALOG-SIGNALING.md for provenance and limitations.
#include <dsd-neo/platform/analog_signaling.h>
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <vector>
#include <deque>
namespace {
constexpr double pi=3.14159265358979323846;
std::mutex mutex;
dsd_signal_event latest{};
std::deque<dsd_signal_event> pending;
uint64_t serial=0, sampleCount=0, lastPublish=0;
uint32_t lastFrequency=0;
int sampleRate=0;
std::vector<float> audio;
double toneA=600,toneB=1000;
int durationA=1000,durationB=1000,aFrames=0,bFrames=0,gapFrames=0;
char lastDtmf=0; int dtmfFrames=0,dtmfGap=0;
double energy(const float* samples,size_t n,double hz,int rate) {
    const double c=2*std::cos(2*pi*hz/rate); double s1=0,s2=0;
    for(size_t i=0;i<n;++i) { const double next=samples[i]+c*s1-s2; s2=s1; s1=next; }
    return std::max(0.0,s1*s1+s2*s2-c*s1*s2);
}
void publish(dsd_signal_event event) {
    // Eight symbol phases can validate the same burst; only suppress identical near-duplicates.
    if(sampleCount-lastPublish<uint64_t(std::max(sampleRate,1))/4 && event.source==latest.source && event.target==latest.target
        && event.opcode==latest.opcode && std::strcmp(event.protocol,latest.protocol)==0 && std::strcmp(event.detail,latest.detail)==0) return;
    lastPublish=sampleCount; event.serial=++serial; event.frequency=lastFrequency; latest=event;
    if(pending.size()>=100) pending.pop_front(); pending.push_back(event);
}
unsigned bits(const unsigned char* b,int start,int count) { unsigned value=0; for(int i=0;i<count;++i) value=(value<<1)|(b[start+i]&1); return value; }
bool fleetCrc(const unsigned char* b) {
    unsigned parity=0, crc=1, weight=0x6815;
    for(int i=0;i<64;++i) parity^=b[i]&1;
    if(parity) return false;
    for(int i=47;i>=0;--i) { if(b[i]) crc^=weight; weight=((weight<<1)&0x7fff)^((weight&0x4000)?0x6815:0); }
    return crc==bits(b,48,15);
}
struct Framer {
    uint64_t shift=0;
    std::array<unsigned char,128> payload{};
    int protocol=0,have=0,needed=0,polarity=0;
    void accept(int bit) {
        if(protocol) {
            payload[size_t(have++)]=static_cast<unsigned char>(bit^polarity);
            if(have==64 && protocol==2 && payload[15]) needed=128;
            if(have<needed) return;
            dsd_signal_event event{}; int valid=0;
            if(protocol==1) {
                unsigned char info[14]{};
                for(int column=0;column<16;++column) for(int row=0;row<7;++row) {
                    const int index=column*7+row; info[index/8]|=static_cast<unsigned char>(payload[size_t(row*16+column)]<<(index%8));
                }
                valid=dsd_signaling_mdc(info,14,&event);
            } else valid=dsd_signaling_fleet(payload.data(),size_t(needed),&event);
            if(valid) publish(event);
            protocol=0; have=0; shift=0; return;
        }
        shift=(shift<<1)|unsigned(bit);
        const uint64_t m=shift&0xffffffffffULL;
        if(m==0x07092a446fULL || m==(0x07092a446fULL^0xffffffffffULL)) { protocol=1; needed=112; have=0; polarity=m==0x07092a446fULL?0:1; }
        const unsigned f=unsigned(shift&0x1fffff);
        if(f==0x0a23eb || f==(0x0a23eb^0x1fffff) || f==0x0a7650 || f==(0x0a7650^0x1fffff)) {
            protocol=2; needed=64; have=0; polarity=(f==0x0a23eb || f==0x0a7650)?0:1;
        }
    }
};
struct Phase { std::vector<float> samples; Framer direct,nrzi; int previous=0; };
std::array<Phase,8> phases;
void resetState() {
    audio.clear(); for(auto& phase:phases) phase=Phase(); sampleCount=0; lastPublish=0;
    aFrames=bFrames=gapFrames=0; lastDtmf=0; dtmfFrames=dtmfGap=0;
}
void tones() {
    const size_t n=audio.size(); double total=0; for(float sample:audio) total+=sample*sample;
    if(total<1e-10) total=1e-10;
    constexpr double freqs[]={697,770,852,941,1209,1336,1477,1633};
    double powers[8]; for(int i=0;i<8;++i) powers[i]=energy(audio.data(),n,freqs[i],sampleRate);
    int low=0,high=4; for(int i=1;i<4;++i) if(powers[i]>powers[low]) low=i; for(int i=5;i<8;++i) if(powers[i]>powers[high]) high=i;
    bool valid=powers[low]+powers[high]>0.30*total*n && powers[low]>0.15*powers[high] && powers[high]>0.15*powers[low];
    for(int i=0;i<8;++i) if(i!=low&&i!=high&&powers[i]*4>std::min(powers[low],powers[high])) valid=false;
    const char digit=valid?"123A456B789C*0#D"[low*4+high-4]:0;
    if(digit) {
        if(digit!=lastDtmf) { lastDtmf=digit; dtmfFrames=0; }
        dtmfGap=0;
        if(++dtmfFrames==2) { dsd_signal_event e{}; std::snprintf(e.protocol,sizeof(e.protocol),"DTMF"); std::snprintf(e.detail,sizeof(e.detail),"%c",digit); e.opcode=unsigned(digit); publish(e); }
    } else if(++dtmfGap>=2) { lastDtmf=0; dtmfFrames=0; }
    const auto matched=[&](double hz) { return energy(audio.data(),n,hz,sampleRate)>0.30*total*n; };
    if(matched(toneA)) { ++aFrames; bFrames=0; gapFrames=0; }
    else if(aFrames*20>=durationA && matched(toneB)) {
        gapFrames=0;
        if(++bFrames*20>=durationB) { dsd_signal_event e{}; std::snprintf(e.protocol,sizeof(e.protocol),"Two-tone");
            std::snprintf(e.detail,sizeof(e.detail),"%.1f / %.1f Hz",toneA,toneB); publish(e); aFrames=bFrames=0; }
    } else if(++gapFrames>10) aFrames=bFrames=0;
}
}
int dsd_signaling_mdc(const unsigned char* info,size_t count,dsd_signal_event* out) {
    if(!info || count<6 || !out) return 0;
    unsigned crc=0;
    for(int i=0;i<4;++i) { crc^=info[i]; for(int j=0;j<8;++j) crc=(crc>>1)^((crc&1)?0x8408:0); }
    crc^=0xffff;
    if(crc!=(unsigned(info[4])|(unsigned(info[5])<<8))) return 0;
    *out={}; std::snprintf(out->protocol,sizeof(out->protocol),"MDC-1200");
    out->source=(unsigned(info[2])<<8)|info[3]; out->opcode=info[0];
    std::snprintf(out->detail,sizeof(out->detail),"ID %04X · opcode %02X · argument %02X",out->source,info[0],info[1]); return 1;
}
int dsd_signaling_fleet(const unsigned char* data,size_t count,dsd_signal_event* out) {
    if(!data||!out||count<64||!fleetCrc(data)) return 0;
    const bool extended=data[15]!=0;
    if(extended && (count<128 || !fleetCrc(data+64))) return 0;
    *out={}; std::snprintf(out->protocol,sizeof(out->protocol),"FleetSync");
    out->fleet=bits(data,16,8)+99; out->source=bits(data,24,12)+999; out->target=bits(data,36,12)+999; out->opcode=bits(data,8,5);
    const unsigned targetFleet=extended?bits(data,64,8)+99:out->fleet;
    std::snprintf(out->detail,sizeof(out->detail),"%u-%u → %u-%u",out->fleet,out->source,targetFleet,out->target); return 1;
}
void dsd_signaling_reset() { std::lock_guard<std::mutex> g(mutex); resetState(); latest={}; pending.clear(); }
int dsd_signaling_pop(dsd_signal_event* out) { if(!out) return 0; std::lock_guard<std::mutex> g(mutex); if(pending.empty()) return 0; *out=pending.front(); pending.pop_front(); return 1; }
int dsd_signaling_latest(dsd_signal_event* out) { if(!out) return 0; std::lock_guard<std::mutex> g(mutex); *out=latest; return latest.serial?1:0; }
int dsd_signaling_two_tone(double a,double b,int a_ms,int b_ms) {
    if(!std::isfinite(a)||!std::isfinite(b)||a<300||a>3000||b<300||b>3000||std::abs(a-b)<40||a_ms<100||a_ms>5000||b_ms<100||b_ms>5000) return 0;
    std::lock_guard<std::mutex> g(mutex); toneA=a; toneB=b; durationA=a_ms; durationB=b_ms; aFrames=bFrames=0; return 1;
}
void dsd_signaling_feed(const float* samples,size_t count,int rate,uint32_t frequency) {
    if(!samples||rate<8000||rate>96000) return;
    std::lock_guard<std::mutex> g(mutex);
    if(rate!=sampleRate || frequency!=lastFrequency) { resetState(); sampleRate=rate; lastFrequency=frequency; }
    const int symbol=rate/1200;
    for(size_t i=0;i<count;++i) {
        const float sample=std::isfinite(samples[i])?samples[i]:0;
        ++sampleCount; audio.push_back(sample);
        if(audio.size()>=size_t(rate/50)) { tones(); audio.clear(); }
        for(size_t p=0;p<phases.size();++p) {
            if(sampleCount<=p*size_t(symbol)/8) continue;
            auto& phase=phases[p]; phase.samples.push_back(sample);
            if(phase.samples.size()<size_t(symbol)) continue;
            const double lo=energy(phase.samples.data(),phase.samples.size(),1200,rate), hi=energy(phase.samples.data(),phase.samples.size(),1800,rate);
            const int raw=lo>hi?1:0;
            phase.direct.accept(raw); phase.nrzi.accept(raw==phase.previous?1:0); phase.previous=raw; phase.samples.clear();
        }
    }
}
