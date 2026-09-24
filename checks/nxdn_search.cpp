// SPDX-License-Identifier: GPL-3.0-or-later
#include <dsd-neo/platform/nxdn_search.h>
#include <array>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <random>
#include <stdexcept>
static void require(bool ok,const char* why) { if(!ok) throw std::runtime_error(why); }
// Independent Fibonacci recurrence: output[t+15] = output[t] XOR output[t+1].
static void cipher(char bits[49],unsigned key,int pos) {
    std::array<unsigned char,784> stream{};
    for(int i=0;i<15;++i) stream[i]=(key>>i)&1U;
    for(int i=15;i<784;++i) stream[i]=stream[i-15]^stream[i-14];
    for(int i=0;i<49;++i) bits[i]^=static_cast<char>(stream[pos*49+i]);
}
static dsd_nxdn_search_input input() { return {1,155000000,10,20,1,3,48,1,1,0,0,1,0}; }
static void fill(char bits[49],unsigned prefix,std::mt19937& rng) {
    for(int i=0;i<49;++i) bits[i]=static_cast<char>(rng()&1U);
    for(int i=0;i<4;++i) bits[i]=static_cast<char>((prefix>>(3-i))&1U);
}
int main() {
    try {
        const auto start=std::chrono::steady_clock::now();
        std::mt19937 rng(0x58455241); char bits[49],plain[49];
        dsd_nxdn_search_enable(1);
        unsigned cases=0;
        for(int variant:{48,96}) for(unsigned key=0;key<32768;++key) {
            dsd_nxdn_search_context c{}; auto in=input(); in.variant=variant;
            for(int n=0;n<20;++n) {
                in.position=variant==48?n%16:(n%8<4?n%8:n%8+4);
                fill(plain,n<8?10:9,rng); std::memcpy(bits,plain,49); cipher(bits,key,in.position);
                const bool applied=dsd_nxdn_search_step(&c,&in,bits)!=0;
                require(applied==(n>=15),"Must wait for two disjoint eight-frame windows");
                if(applied) require(c.key==key && std::memcmp(bits,plain,49)==0,"Recovered seed and plaintext must match independent encoder");
            }
            ++cases;
        }
        // Random voice/noise and stationary prefixes must never latch a WRONG key.
        auto in=input(); dsd_nxdn_search_context c{};
        for(int n=0;n<500000;++n) {
            in.position=n%16; fill(bits,rng()&15U,rng);
            require(!dsd_nxdn_search_step(&c,&in,bits),"Random payload falsely accepted");
        }
        for(unsigned prefix=0;prefix<16;++prefix) {
            c={};
            for(int n=0;n<32;++n) { in.position=n%16; fill(bits,prefix,rng);
                if(dsd_nxdn_search_step(&c,&in,bits)) require(c.key==0,"Constant clear pitch cannot produce nonzero key"); }
        }
        // Same offset repeated is not independent evidence.
        c={}; in.position=0;
        for(int n=0;n<64;++n) { fill(bits,14,rng); cipher(bits,12345,0); require(!dsd_nxdn_search_step(&c,&in,bits),"Repeated offset accepted"); }
        // Acquire then verify every context boundary and policy rejection.
        auto acquire=[&] {
            c={}; in=input();
            for(int n=0;n<16;++n) { in.position=n; fill(bits,10,rng); cipher(bits,32767,n); dsd_nxdn_search_step(&c,&in,bits); }
            require(c.ready && c.key==32767 && dsd_nxdn_search_audio_allowed(&c),"Acquisition");
        };
        for(int boundary=0;boundary<13;++boundary) {
            acquire();
            switch(boundary) {
                case 0: ++in.epoch; break; case 1: ++in.frequency; break; case 2: ++in.source; break;
                case 3: ++in.target; break; case 4: ++in.ran; break; case 5: ++in.kid; break;
                case 6: in.variant=96; break; case 7: in.cipher=2; break; case 8: in.cipher=3; break;
                case 9: in.manual_key=1; break; case 10: in.established=0; break;
                case 11: in.position_valid=0; break; case 12: in.errors=4; break;
            }
            fill(plain,9,rng); std::memcpy(bits,plain,49);
            require(!dsd_nxdn_search_step(&c,&in,bits) && !dsd_nxdn_search_audio_allowed(&c) && std::memcmp(bits,plain,49)==0,"Boundary must not reuse candidate");
        }
        acquire(); dsd_nxdn_search_enable(0); require(!dsd_nxdn_search_audio_allowed(&c),"Disable must close audio immediately");
        dsd_nxdn_search_enable(1); require(!dsd_nxdn_search_audio_allowed(&c),"Re-enable cannot revive stale context");
        const double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
        std::printf("PASS: %u complete seed/format cases; 500000 random frames; 13 context/quality boundaries; %.3f seconds\n",cases,seconds);
        return 0;
    } catch(const std::exception& e) { std::fprintf(stderr,"FAIL: %s\n",e.what()); return 1; }
}
