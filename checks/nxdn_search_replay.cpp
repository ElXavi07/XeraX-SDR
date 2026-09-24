// SPDX-License-Identifier: GPL-3.0-or-later
// Replay actual AMBE speech parameters extracted from the pinned public IQ fixture.
// Only the cipher is synthetic. This is not a scrambled off-air acceptance test.
#include <dsd-neo/platform/nxdn_search.h>
#include <array>
#include <cstdio>
#include <fstream>
#include <vector>
#include <string>
struct Frame { int position,errors; uint64_t word; };
int main(int argc,char** argv) {
    if(argc!=3) return 2;
    std::ifstream file(argv[1]); std::vector<Frame> frames; Frame f{}; std::string word;
    while(file>>f.position>>f.errors>>word) { f.word=std::stoull(word,nullptr,16); frames.push_back(f); }
    if(frames.empty()) return 2;
    const int variant=std::stoi(argv[2]); unsigned found=0,first=0;
    for(unsigned test=0;test<64;++test) {
        const unsigned key=(test*509+12345)&32767U;
        std::array<unsigned char,784> stream{};
        for(int i=0;i<15;++i) stream[i]=(key>>i)&1U;
        for(int i=15;i<784;++i) stream[i]=stream[i-15]^stream[i-14];
        dsd_nxdn_search_context c{}; dsd_nxdn_search_enable(1);
        dsd_nxdn_search_input in{1,155000000,10,20,1,2,variant,1,1,0,0,1,0};
        bool recovered=false;
        for(unsigned n=0;n<frames.size();++n) {
            const auto& frame=frames[n]; if(frame.position<0 || frame.position>=16) return 3;
            in.position=frame.position; in.errors=frame.errors;
            char bits[49],plain[49];
            for(int i=0;i<49;++i) { plain[i]=static_cast<char>((frame.word>>(55-i))&1U); bits[i]=plain[i]^stream[frame.position*49+i]; }
            if(dsd_nxdn_search_step(&c,&in,bits)) {
                if(c.key!=key) return 4;
                for(int i=0;i<49;++i) if(bits[i]!=plain[i]) return 5;
                if(!recovered) { first=n+1; recovered=true; }
            }
        }
        if(recovered) ++found;
    }
    std::printf("{\"variant\":%d,\"keysTested\":64,\"keysRecovered\":%u,\"frames\":%zu,\"firstAcceptedFrame\":%u,\"wrongKeys\":0}\n",variant,found,frames.size(),first);
    return variant==48 && found!=64?6:0;
}
