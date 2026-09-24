// SPDX-License-Identifier: GPL-3.0-or-later
#include <dsd-neo/platform/nxdn_search.h>
#include <array>
#include <chrono>
#include <cstring>
#include <mutex>

namespace {
std::mutex mutex;
bool enabled=false;
unsigned generation=1;
dsd_nxdn_search_status status{};
using Clock=std::chrono::steady_clock;
Clock::time_point last{};

/* The first four AMBE parameter bits are the high bits of b0 (pitch).
 * Each row expresses a keystream bit as a linear function of the 15-bit seed.
 * Four additional variables describe an UNKNOWN common pitch prefix. No
 * specific spoken word, silence value, language or saved key is assumed. */
using Rows=std::array<std::array<uint32_t,4>,16>;
const Rows rows=[] {
    Rows out{}; std::array<uint32_t,15> state{};
    for(unsigned i=0;i<15;++i) state[i]=1U<<i;
    for(unsigned n=0;n<16*49;++n) {
        if(n%49<4) out[n/49][n%49]=state[0]|(1U<<(15+n%49));
        const auto next=state[0]^state[1];
        for(unsigned i=0;i<14;++i) state[i]=state[i+1];
        state[14]=next;
    }
    return out;
}();
unsigned parity(uint32_t v) { v^=v>>16; v^=v>>8; v^=v>>4; return (0x6996U>>(v&15U))&1U; }

/* 32 equations, 19 unknowns. Reject inconsistent or underdetermined systems.
 * Repeated positions provide no new seed evidence and are explicitly rejected. */
bool solve(const dsd_nxdn_search_context& c,uint16_t& seed) {
    uint32_t basis[19]{}; unsigned rhs[19]{}; unsigned rank=0,seen=0;
    for(unsigned n=0;n<8;++n) {
        const unsigned p=c.positions[n];
        if(p>=16 || (seen&(1U<<p))) return false;
        seen|=1U<<p;
        for(unsigned j=0;j<4;++j) {
            uint32_t mask=rows[p][j]; unsigned bit=(c.prefixes[n]>>(3-j))&1U;
            for(int k=18;k>=0;--k) if(mask&(1U<<k)) {
                if(basis[k]) { mask^=basis[k]; bit^=rhs[k]; }
                else { basis[k]=mask; rhs[k]=bit; ++rank; break; }
            }
            if(mask==0 && bit) return false;
        }
    }
    if(rank!=19) return false;
    uint32_t answer=0;
    for(unsigned k=0;k<19;++k) if(parity(basis[k]&answer)^rhs[k]) answer|=1U<<k;
    seed=static_cast<uint16_t>(answer&0x7FFFU);
    return true;
}
void publish(const dsd_nxdn_search_context& c,int s) {
    status.status=s; status.key=s==DSD_NXDN_SEARCH_USING?c.key:-1;
    status.frames=static_cast<int>(c.sequence); last=Clock::now();
}
void descramble(uint16_t key,int position,char bits[49]) {
    uint16_t lfsr=key;
    for(int n=0;n<(position+1)*49;++n) {
        if(n>=position*49) bits[n-position*49]^=static_cast<char>(lfsr&1U);
        lfsr=static_cast<uint16_t>((lfsr>>1)|(((lfsr^(lfsr>>1))&1U)<<14));
    }
}
}
void dsd_nxdn_search_enable(int value) {
    std::lock_guard<std::mutex> lock(mutex);
    enabled=value!=0; ++generation; status={}; status.key=-1; last={};
}
int dsd_nxdn_search_enabled() { std::lock_guard<std::mutex> lock(mutex); return enabled?1:0; }
void dsd_nxdn_search_get(dsd_nxdn_search_status* result) {
    if(!result) return;
    std::lock_guard<std::mutex> lock(mutex); *result=status; result->enabled=enabled?1:0;
    result->age_ms=last==Clock::time_point{}?UINT64_MAX:static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now()-last).count());
    if(!enabled || result->age_ms>1500) { result->status=DSD_NXDN_SEARCH_WAITING; result->key=-1; }
}
int dsd_nxdn_search_audio_allowed(const dsd_nxdn_search_context* c) {
    std::lock_guard<std::mutex> lock(mutex);
    return c && enabled && c->generation==generation && c->applied;
}
int dsd_nxdn_search_step(dsd_nxdn_search_context* c,const dsd_nxdn_search_input* in,char bits[49]) {
    if(!c || !in || !bits) return 0;
    std::lock_guard<std::mutex> lock(mutex); c->applied=0;
    if(!enabled) { *c={}; return 0; }
    if(c->generation!=generation || c->epoch!=in->epoch || c->frequency!=in->frequency ||
       c->source!=in->source || c->target!=in->target || c->ran!=in->ran || c->kid!=in->kid || c->variant!=in->variant) {
        *c={}; c->generation=generation; c->epoch=in->epoch; c->frequency=in->frequency;
        c->source=in->source; c->target=in->target; c->ran=in->ran; c->kid=in->kid; c->variant=in->variant;
    }
    if(in->manual_key || in->cipher!=1 || !in->established || !in->epoch ||
       (in->variant!=48 && in->variant!=96)) {
        c->ready=c->pending=c->count=c->cursor=0;
        publish(*c,in->manual_key?DSD_NXDN_SEARCH_SUPPLIED:DSD_NXDN_SEARCH_UNSUPPORTED); return 0;
    }
    if(!in->position_valid || in->position<0 || in->position>15 || in->errors<0 || in->errors>3) {
        c->count=c->cursor=0; c->pending=0;
        publish(*c,DSD_NXDN_SEARCH_SEARCHING); return 0;
    }
    for(unsigned i=0;i<49;++i) if(bits[i]!=0 && bits[i]!=1) { c->count=c->pending=0; return 0; }
    ++c->sequence;
    if(!c->ready) {
        c->positions[c->cursor]=static_cast<uint8_t>(in->position);
        c->prefixes[c->cursor]=static_cast<uint8_t>((bits[0]<<3)|(bits[1]<<2)|(bits[2]<<1)|bits[3]);
        c->cursor=(c->cursor+1)%8; if(c->count<8) ++c->count;
        uint16_t found=0;
        if(c->pending && c->sequence-c->candidate_at>200) c->pending=0;
        if(c->count==8 && solve(*c,found)) {
            if(c->pending && c->candidate==found && c->sequence-c->candidate_at>=8) {
                c->key=found; c->ready=1;
            } else if(!c->pending || c->candidate!=found) {
                c->candidate=found; c->candidate_at=c->sequence; c->pending=1;
            }
        }
    }
    if(c->ready) { descramble(c->key,in->position,bits); c->applied=1; }
    publish(*c,c->ready?DSD_NXDN_SEARCH_USING:c->pending?DSD_NXDN_SEARCH_CANDIDATE:DSD_NXDN_SEARCH_SEARCHING);
    return c->applied;
}
