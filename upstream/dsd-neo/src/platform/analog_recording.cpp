// SPDX-License-Identifier: GPL-3.0-or-later
#include <dsd-neo/platform/analog_recording.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <ctime>
#include <string>
#include <vector>
namespace {
FILE* output=nullptr;
std::string filename;
uint32_t sampleRate=0, tuned=0, samples=0, quiet=0, serial=0;
std::time_t started=0;
bool failed=false;
void le16(unsigned char* p,uint16_t v) { p[0]=v&255; p[1]=(v>>8)&255; }
void le32(unsigned char* p,uint32_t v) { for(int i=0;i<4;i++) p[i]=(v>>(i*8))&255; }
bool header() {
    unsigned char h[44]={'R','I','F','F',0,0,0,0,'W','A','V','E','f','m','t',' ',16,0,0,0,1,0,1,0};
    le32(h+4,36+samples*2); le32(h+24,sampleRate); le32(h+28,sampleRate*2);
    le16(h+32,2); le16(h+34,16); h[36]='d';h[37]='a';h[38]='t';h[39]='a'; le32(h+40,samples*2);
    return std::fseek(output,0,SEEK_SET)==0 && std::fwrite(h,1,44,output)==44;
}
}
extern "C" void dsd_analog_record_close() {
    if(!output) return;
    const bool good=header() && !failed;
    const bool closed=std::fclose(output)==0; output=nullptr;
    if(!good || !closed || !samples) return;
    const auto sidecar=filename.substr(0,filename.size()-4)+".json", pending=sidecar+".tmp";
    FILE* meta=std::fopen(pending.c_str(),"wb"); if(!meta) return;
    const auto ended=started+(samples+sampleRate-1)/sampleRate;
    const bool wrote=std::fprintf(meta,"{\"start_time\":%lld,\"stop_time\":%lld,\"talkgroup\":0,\"talkgroup_tag\":\"Analog\",\"short_name\":\"Analog\",\"freq\":%u,\"sample_rate\":%u,\"samples\":%u,\"encrypted\":false,\"segmentation\":\"squelch\"}\n",static_cast<long long>(started),static_cast<long long>(ended),tuned,sampleRate,samples)>0;
    const bool saved=std::fclose(meta)==0;
    if(wrote && saved) std::rename(pending.c_str(),sidecar.c_str());
}
extern "C" void dsd_analog_record(const char* directory,const float* pcm,size_t count,unsigned rate,uint32_t frequency,int open) {
    if(!directory || !*directory || !pcm || rate<8000 || rate>192000) { dsd_analog_record_close(); return; }
    if(output && (rate!=sampleRate || frequency!=tuned || samples>=sampleRate*300U)) dsd_analog_record_close();
    if(!output && !open) return;
    if(!output) {
        sampleRate=rate; tuned=frequency; samples=0; quiet=0; failed=false; started=std::time(nullptr);
        filename=std::string(directory)+"/analog-"+std::to_string(static_cast<long long>(started))+"-"+std::to_string(++serial)+".wav";
        output=std::fopen(filename.c_str(),"wb"); if(!output) return;
        if(!header()) { failed=true; dsd_analog_record_close(); return; }
    }
    std::vector<unsigned char> bytes(count*2);
    for(size_t i=0;i<count;i++) {
        const float value=open && std::isfinite(pcm[i])?std::max(-32768.0f,std::min(32767.0f,pcm[i])):0.0f;
        le16(bytes.data()+i*2,static_cast<uint16_t>(static_cast<int16_t>(value)));
    }
    if(std::fwrite(bytes.data(),1,bytes.size(),output)!=bytes.size()) failed=true;
    samples+=static_cast<uint32_t>(count); quiet=open?0:quiet+static_cast<uint32_t>(count);
    if(quiet>=sampleRate || failed) dsd_analog_record_close();
}
