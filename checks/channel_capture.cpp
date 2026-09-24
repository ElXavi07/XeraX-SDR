// SPDX-License-Identifier: GPL-3.0-or-later
// Lift a 48 kS/s fixture into a 1.536 MS/s capture, then use the production
// channel filter to deliver 192 kS/s with the worker's -Fs/4 carrier offset.
#include <dsd-neo/platform/channel_bank.h>
#include <fstream>
#include <iterator>
#include <vector>
#include <complex>
#include <cmath>
#include <algorithm>
int main(int argc,char** argv) {
    if(argc!=3) return 2;
    std::ifstream input(argv[1],std::ios::binary);
    std::vector<unsigned char> data((std::istreambuf_iterator<char>(input)),{});
    if(data.empty() || data.size()%2) return 2;
    std::ofstream output(argv[2],std::ios::binary);
    void* filter=dsd_channel_filter_create(1536000,192000,-248000);
    if(!filter || !output) return 2;
    const auto step=std::polar(1.0,2*3.14159265358979323846*200000/1536000);
    std::complex<double> phase{1,0};
    unsigned char in[64],out[64];
    for(size_t p=0;p<data.size();p+=2) {
        const size_t next=std::min(p+2,data.size()-2);
        const std::complex<double> a{data[p]-127.5,data[p+1]-127.5},b{data[next]-127.5,data[next+1]-127.5};
        for(unsigned j=0;j<32;++j) {
            const auto value=(a+(b-a)*(j/32.0))*phase;
            in[2*j]=static_cast<unsigned char>(std::min(255L,std::max(0L,std::lround(value.real()+127.5))));
            in[2*j+1]=static_cast<unsigned char>(std::min(255L,std::max(0L,std::lround(value.imag()+127.5))));
            phase*=step;
        }
        if((p&4095U)==0) phase/=std::abs(phase);
        const auto count=dsd_channel_filter_process(filter,in,sizeof(in),out);
        output.write(reinterpret_cast<const char*>(out),count);
    }
    dsd_channel_filter_destroy(filter);
    return output?0:1;
}
