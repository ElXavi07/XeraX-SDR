// SPDX-License-Identifier: GPL-3.0-or-later
#include <dsd-neo/platform/receiver_lab.h>
#include <array>
#include <atomic>
#include <algorithm>
#include <cmath>
#include <complex>
#include <mutex>
namespace {
std::atomic<int> equalizer{0},generation{1};
std::atomic<double> modulusError{0};
// One DSP producer per process. Only the reset generation crosses threads.
struct Equalizer {
    std::array<std::complex<float>,7> weights{};
    std::array<std::complex<float>,256> history{};
    int cursor=0,gen=0,sps=0;
    double error=0;
    void reset(int g,int samples) { weights.fill({0,0}); weights[3]={1,0}; history.fill({0,0}); cursor=0; gen=g; sps=samples; error=0; }
} eq;
std::mutex grantMutex;
dsd_dual_grant grant{};
bool dual=false;
uint64_t voiceSequence=0;
int voiceStatus=0;
std::atomic<uint64_t> checked[2]{},suspected[2]{},rejected[2]{};
std::atomic<int> rasEnabled{0};
std::atomic<double> trialOffset{0};
std::atomic<int> trialBandwidth{0},trialGeneration{1};
struct Trial {
    std::array<std::complex<float>,65> history{};
    std::array<float,65> taps{};
    int gen=0,rate=0,cursor=0;
    double phase=0;
} trial;
}
void dsd_trial_configure(double offset,int bandwidth) {
    trialOffset=std::isfinite(offset)?std::min(1000.0,std::max(-1000.0,offset)):0;
    trialBandwidth=bandwidth==0?0:std::min(18000,std::max(4000,bandwidth)); ++trialGeneration;
}
void dsd_dmr_ras_enable(int enabled) { rasEnabled=enabled?1:0; }
int dsd_dmr_ras_enabled() { return rasEnabled.load(); }
void dsd_trial_process(float* iq,size_t elements,int rate) {
    const double offset=trialOffset.load(); const int bandwidth=trialBandwidth.load();
    if((offset==0 && bandwidth==0) || !iq || rate<16000) return;
    constexpr double pi=3.14159265358979323846;
    if(trial.gen!=trialGeneration || trial.rate!=rate) {
        trial=Trial(); trial.gen=trialGeneration; trial.rate=rate;
        const double cutoff=std::min(0.45,bandwidth*0.5/rate); double sum=0;
        for(int k=0;k<65;++k) { int x=k-32; const double sinc=x==0?2*cutoff:std::sin(2*pi*cutoff*x)/(pi*x);
            trial.taps[size_t(k)]=float(sinc*(0.54-0.46*std::cos(2*pi*k/64))); sum+=trial.taps[size_t(k)]; }
        if(sum>0) for(auto& tap:trial.taps) tap/=float(sum);
    }
    const auto step=std::polar(1.0F,float(-2*pi*offset/rate)); auto oscillator=std::polar(1.0F,float(trial.phase));
    for(size_t i=0;i+1<elements;i+=2) {
        auto sample=std::complex<float>(iq[i],iq[i+1])*oscillator; oscillator*=step;
        if((i&4095U)==4094U) oscillator/=std::abs(oscillator);
        if(bandwidth) {
            trial.history[size_t(trial.cursor)]=sample; sample={0,0};
            for(int k=0;k<65;++k) sample+=trial.taps[size_t(k)]*trial.history[size_t((trial.cursor-k+65)%65)];
            trial.cursor=(trial.cursor+1)%65;
        }
        iq[i]=sample.real(); iq[i+1]=sample.imag();
    }
    trial.phase=std::remainder(trial.phase-2*pi*offset*double(elements/2)/rate,2*pi);
}
void dsd_equalizer_enable(int enabled) { equalizer=enabled?1:0; ++generation; }
int dsd_equalizer_enabled() { return equalizer.load(); }
void dsd_equalizer_reset() { ++generation; }
double dsd_equalizer_error() { return modulusError.load(); }
void dsd_equalizer_process(float* iq,size_t elements,int sps) {
    if(!equalizer || !iq || sps<2 || sps>40) return;
    const int g=generation.load(); if(eq.gen!=g || eq.sps!=sps) eq.reset(g,sps);
    const int spacing=std::max(1,sps/2);
    for(size_t i=0;i+1<elements;i+=2) {
        eq.history[size_t(eq.cursor)]={iq[i],iq[i+1]};
        std::array<std::complex<float>,7> x; std::complex<float> y{0,0}; float power=0;
        for(int k=0;k<7;++k) { x[size_t(k)]=eq.history[size_t((eq.cursor-k*spacing+256)%256)]; y+=eq.weights[size_t(k)]*x[size_t(k)]; power+=std::norm(x[size_t(k)]); }
        // Normalized constant-modulus adaptation. Limit each update and total tap power;
        // loss of numerical stability resets to a delayed identity filter.
        const float error=std::min(2.0F,std::max(-2.0F,1.0F-std::norm(y)));
        const float mu=0.0003F/(0.05F+power);
        float norm=0;
        for(int k=0;k<7;++k) { eq.weights[size_t(k)]+=mu*error*y*std::conj(x[size_t(k)]); norm+=std::norm(eq.weights[size_t(k)]); }
        if(!std::isfinite(norm) || norm>8 || !std::isfinite(std::norm(y))) { eq.reset(g,sps); continue; }
        iq[i]=y.real(); iq[i+1]=y.imag(); eq.error=0.999*eq.error+0.001*error*error;
        eq.cursor=(eq.cursor+1)%256;
    }
    modulusError=eq.error;
}
void dsd_dual_enable(int enabled) { std::lock_guard<std::mutex> guard(grantMutex); dual=enabled!=0; grant={}; }
int dsd_dual_offer(uint32_t frequency,uint32_t wacn,uint32_t sysid,uint32_t nac,uint32_t tg,uint32_t source,int tdma,int slot,int priority) {
    std::lock_guard<std::mutex> guard(grantMutex); if(!dual) return 0;
    ++grant.sequence; grant.frequency=frequency; grant.wacn=wacn; grant.sysid=sysid; grant.nac=nac;
    grant.talkgroup=tg; grant.source=source; grant.tdma=tdma; grant.slot=slot; grant.priority=priority;
    return 1;
}
int dsd_dual_get(dsd_dual_grant* out) { if(!out) return 0; std::lock_guard<std::mutex> guard(grantMutex); *out=grant; return dual && grant.sequence>0; }
int dsd_voice_tune_valid(const dsd_voice_tune* t) {
    if(!t) return 0;
    const auto& g=t->grant;
    return g.sequence>0 && g.frequency>=24000000 && g.frequency<=1766000000
        && g.wacn<=0xfffff && g.sysid<=0xfff && g.nac<=0xfff
        && (g.tdma==0 || g.tdma==1) && (g.slot==0 || g.slot==1)
        && (t->modulation==0 || t->modulation==1)
        && (!g.tdma || (g.wacn && g.sysid && g.nac));
}
void dsd_voice_tune_result(uint64_t sequence,int status) { std::lock_guard<std::mutex> lock(grantMutex); voiceSequence=sequence; voiceStatus=status; }
int dsd_voice_tune_status(uint64_t* sequence) { std::lock_guard<std::mutex> lock(grantMutex); if(sequence) *sequence=voiceSequence; return voiceStatus; }
void dsd_dmr_evidence_reset() { for(int s=0;s<2;++s) { checked[s]=0; suspected[s]=0; rejected[s]=0; } }
void dsd_dmr_evidence_note(int s,int ras,int fec,int crc) {
    if(s<0 || s>1) return;
    if(fec) ++rejected[s]; else if(ras) ++suspected[s]; else if(crc) ++checked[s]; else ++rejected[s];
}
void dsd_dmr_evidence_get(dsd_dmr_evidence* out) {
    if(!out) return;
    for(int s=0;s<2;++s) { out->checked[s]=checked[s]; out->suspected_ras[s]=suspected[s]; out->rejected[s]=rejected[s]; }
}
