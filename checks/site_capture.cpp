// SPDX-License-Identifier: GPL-3.0-or-later
// Mix four independent 48 kS/s fixtures into one 1.536 MS/s capture at the
// school's RF spacing, then run the actual four production channel filters.
#include <dsd-neo/platform/channel_bank.h>
#include <fstream>
#include <iterator>
#include <vector>
#include <complex>
#include <cmath>
#include <algorithm>
int main(int argc,char** argv) {
    if(argc!=6) return 2;
    constexpr double pi=3.14159265358979323846;
    const double offsets[]={-512500,237500,337500,512500};
    std::vector<unsigned char> data[4]; std::ofstream outputs[4]; void* filters[4]{};
    std::complex<double> phase[4]={{1,0},{0,1},{-1,0},{0,-1}},step[4];
    size_t samples=0;
    for(int lane=0;lane<4;++lane) {
        std::ifstream f(argv[lane+1],std::ios::binary); data[lane]={(std::istreambuf_iterator<char>(f)),{}};
        if(data[lane].empty() || data[lane].size()%2) return 2;
        samples=std::max(samples,data[lane].size()/2);
        outputs[lane].open(std::string(argv[5])+std::to_string(lane)+".iq",std::ios::binary);
        filters[lane]=dsd_channel_filter_create(1536000,192000,-offsets[lane]-48000);
        if(!outputs[lane] || !filters[lane]) return 2;
        step[lane]=std::polar(1.0,2*pi*offsets[lane]/1536000);
    }
    unsigned char in[64],out[64];
    for(size_t p=0;p<samples;++p) {
        for(unsigned j=0;j<32;++j) {
            std::complex<double> mixed{};
            for(int lane=0;lane<4;++lane) {
                const auto at=(p%(data[lane].size()/2))*2;
                const auto next=(at+2)%data[lane].size();
                const auto& d=data[lane];
                const std::complex<double> a{d[at]-127.5,d[at+1]-127.5},b{d[next]-127.5,d[next+1]-127.5};
                mixed+=(a+(b-a)*(j/32.0))*phase[lane]/4.0;
                phase[lane]*=step[lane];
            }
            in[2*j]=static_cast<unsigned char>(std::clamp(std::lround(mixed.real()+127.5),0L,255L));
            in[2*j+1]=static_cast<unsigned char>(std::clamp(std::lround(mixed.imag()+127.5),0L,255L));
        }
        for(int lane=0;lane<4;++lane) {
            if((p&4095U)==0) phase[lane]/=std::abs(phase[lane]);
            const auto count=dsd_channel_filter_process(filters[lane],in,sizeof(in),out);
            outputs[lane].write(reinterpret_cast<const char*>(out),count);
        }
    }
    for(int lane=0;lane<4;++lane) { dsd_channel_filter_destroy(filters[lane]); if(!outputs[lane]) return 1; }
    return 0;
}
