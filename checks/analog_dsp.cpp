// SPDX-License-Identifier: GPL-3.0-or-later
#include <dsd-neo/dsp/demod_pipeline.h>
#include <dsd-neo/dsp/demod_state.h>
#include <cmath>
#include <cstdio>
#include <vector>
#include <memory>
int main(){
    constexpr double pi=3.141592653589793;int failed=0;
    for(int mode=0;mode<3;mode++){
        int rate=mode==2?240000:48000,n=rate/5;double phase=0;std::vector<float> iq(n*2),out(n);
        for(int i=0;i<n;i++){
            double voice=std::sin(2*pi*1000*i/rate),amplitude=mode==0?1+0.5*voice:1;
            if(mode)phase+=2*pi*(mode==2?75000:2500)*voice/rate;
            iq[i*2]=amplitude*std::cos(phase);iq[i*2+1]=amplitude*std::sin(phase);
        }
        auto allocation=std::make_unique<demod_state>();auto& state=*allocation;state.rate_out=rate;state.lowpassed=iq.data();state.lp_len=n*2;
        if(mode==0)dsd_am_demod(&state);else dsd_fm_demod(&state);
        double xy=0,xx=0,yy=0;
        for(int i=rate/20;i<n;i++){double expected=std::sin(2*pi*1000*i/rate);xy+=state.result[i]*expected;xx+=state.result[i]*state.result[i];yy+=expected*expected;}
        double correlation=xy/std::sqrt(xx*yy);
        if(state.result_len!=n||correlation<0.99){std::fprintf(stderr,"mode %d correlation %.6f\n",mode,correlation);failed++;}
    }
    return failed?1:0;
}
