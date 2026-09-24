#include <dsd-neo/platform/analog_recording.h>
#include <QUuid>
// SPDX-License-Identifier: GPL-3.0-or-later
#include <dsd-neo/platform/channel_bank.h>
#include <dsd-neo/platform/analog_signaling.h>
#include <dsd-neo/platform/receiver_lab.h>
#include <dsd-neo/platform/reception_sample.h>
#include "call_library.h"
#include <QCoreApplication>
#include <QStandardPaths>
#include <QTemporaryDir>
#include <QSettings>
#include <QFile>
#include <QDir>
#include <QJsonDocument>
#include <QJsonObject>
#include <QDateTime>
#include <cmath>
#include <cstdio>
#include <vector>
#include <random>
#include <stdexcept>
#include <cstring>
constexpr double pi=3.14159265358979323846;
void require(bool pass,const char* message) { if(!pass) throw std::runtime_error(message); }
std::vector<float> tone(double first,double second,int count=4800) {
    std::vector<float> samples(size_t(count),0); for(int i=0;i<count;++i) samples[size_t(i)]=float(0.22*std::sin(2*pi*first*i/48000)+(second?0.22*std::sin(2*pi*second*i/48000):0)); return samples;
}
void feed(const std::vector<float>& samples) {
    for(size_t p=0;p<samples.size();) { auto n=std::min<size_t>(137,samples.size()-p); dsd_signaling_feed(samples.data()+p,n,48000,155000000); p+=n; }
}
void signals() {
    dsd_signal_event event{};
    unsigned char packet[]={1,128,0x12,0x34,0x2e,0x3e,0,0,0,0,0,0,0,0};
    // Independently calculated CRC using Python binascii.crc_hqx with bit reflection.
    require(dsd_signaling_mdc(packet,sizeof(packet),&event)==1 && event.source==0x1234,"MDC known CRC/payload");
    packet[2]^=1; require(!dsd_signaling_mdc(packet,sizeof(packet),&event),"MDC corrupted packet rejected"); packet[2]^=1;
    // Independent polynomial-division fixture: fleet 100, source 1234, target 2345.
    unsigned char fleet[64]; for(int i=0;i<64;++i) fleet[i]=static_cast<unsigned char>((0x0080010eb5423363ULL>>(63-i))&1);
    require(dsd_signaling_fleet(fleet,64,&event) && event.fleet==100 && event.source==1234 && event.target==2345,"FleetSync independent CRC/field vector");
    fleet[12]^=1; require(!dsd_signaling_fleet(fleet,64,&event),"FleetSync damaged block rejected"); fleet[12]^=1;
    dsd_signaling_reset(); std::vector<float> fleetAudio(4807,0); double fleetPhase=0;
    std::vector<int> fleetBits; for(int i=20;i>=0;--i) fleetBits.push_back((0x0a23eb>>i)&1); for(auto bit:fleet) fleetBits.push_back(bit);
    for(int bit:fleetBits) for(int j=0;j<40;++j) { fleetPhase+=2*pi*(bit?1200:1800)/48000; fleetAudio.push_back(float(0.4*std::sin(fleetPhase))); }
    fleetAudio.resize(fleetAudio.size()+960,0); feed(fleetAudio);
    require(dsd_signaling_latest(&event) && std::string(event.protocol)=="FleetSync" && event.source==1234,"FleetSync decoded from audio and frame synchronization");
    std::vector<int> onAir;
    for(int i=39;i>=0;--i) onAir.push_back(int((0x07092a446fULL>>i)&1));
    std::vector<int> interleaved(112);
    for(int c=0;c<16;++c) for(int r=0;r<7;++r) { int k=c*7+r; interleaved[size_t(r*16+c)]=(packet[k/8]>>(k%8))&1; }
    onAir.insert(onAir.end(),interleaved.begin(),interleaved.end());
    dsd_signaling_reset(); std::vector<float> samples(4803,0); double phase=0; int raw=0;
    for(int bit:onAir) { if(!bit) raw^=1; for(int j=0;j<40;++j) { phase+=2*pi*(raw?1200:1800)/48000; samples.push_back(float(0.4*std::sin(phase))); } }
    samples.resize(samples.size()+960,0); feed(samples);
    require(dsd_signaling_latest(&event) && std::string(event.protocol)=="MDC-1200" && event.source==0x1234,"MDC decoded through audio, symbol timing, NRZI and deinterleave");
    const double lows[]={697,770,852,941}, highs[]={1209,1336,1477,1633};
    for(int i=0;i<16;++i) {
        dsd_signaling_reset(); feed(tone(lows[i/4],highs[i%4]));
        require(dsd_signaling_latest(&event) && std::string(event.protocol)=="DTMF" && event.detail[0]=="123A456B789C*0#D"[i],"DTMF digit through audio");
    }
    dsd_signaling_reset(); feed(tone(697,0)); require(!dsd_signaling_latest(&event),"Single tone is not DTMF");
    dsd_signaling_reset(); require(dsd_signaling_two_tone(600,1000,200,300),"Two tone configuration");
    feed(tone(600,0,12000)); feed(tone(1000,0,16800));
    require(dsd_signaling_latest(&event) && std::string(event.protocol)=="Two-tone","Ordered two tone audio sequence");
    dsd_signaling_reset(); feed(tone(1000,0,16800)); feed(tone(600,0,12000)); require(!dsd_signaling_latest(&event),"Reversed tones rejected");
    dsd_signaling_reset(); std::mt19937 rng(123); std::normal_distribution<float> noise(0,0.1F); std::vector<float> noiseAudio(48000*3);
    for(auto& x:noiseAudio) x=noise(rng); feed(noiseAudio); require(!dsd_signaling_latest(&event),"Noise does not publish IDs or digits");
}
void translation() {
    const uint32_t school[]={451100000,451850000,451950000,452125000};
    for(auto hz:school) require(dsd_channel_fits(451612500,1536000,hz),"All school carriers fit with worker Fs/4 offset");
    require(!dsd_channel_fits(451612500,1536000,452300000),"Out-of-window carrier rejected");
    require(!dsd_channel_fits(451612500,1000000,451850000),"Unsupported decimation rejected");
    dsd_channel_reset_source(); dsd_channel_info info{}; dsd_channel_get(-1,&info);
    require(!info.source_bytes && info.source_age_ms==UINT64_MAX,"No stale source before capture");
    const unsigned char valid[]={127,128,129,126};
    dsd_channel_feed_cu8(valid,sizeof(valid),451612500,1536000); dsd_channel_get(3,&info);
    require(info.source_bytes==4 && info.source_age_ms<1000 && info.source_hz==451612500,"Fresh source statistics on fourth lane");
    dsd_channel_feed_cu8(valid,3,1,1); dsd_channel_get(-1,&info);
    require(info.source_bytes==4 && info.source_hz==451612500,"Malformed I/Q does not mark capture fresh");
    dsd_channel_reset_source(); dsd_channel_get(0,&info); require(info.source_bytes==0,"Stop clears capture evidence");
    // Independent target/alias tones exercise the actual anti-alias cascade at USB rate.
    const uint32_t inputRate=1536000, outputRate=192000;
    const size_t count=inputRate/10;
    auto filtered=[&](double frequency,bool partitioned) {
        std::vector<unsigned char> input(2*count),output(2*count); size_t written=0;
        for(size_t i=0;i<count;++i) { input[2*i]=static_cast<unsigned char>(127.5+50*std::cos(2*pi*frequency*i/inputRate)); input[2*i+1]=static_cast<unsigned char>(127.5+50*std::sin(2*pi*frequency*i/inputRate)); }
        void* filter=dsd_channel_filter_create(inputRate,outputRate,-248000);
        require(filter,"Supported shared-channel decimation");
        for(size_t at=0;at<input.size();) { const size_t bytes=std::min<size_t>(partitioned?274:input.size(),input.size()-at);
            written+=dsd_channel_filter_process(filter,input.data()+at,bytes,output.data()+written); at+=bytes; }
        dsd_channel_filter_destroy(filter); output.resize(written); return output;
    };
    auto desired=filtered(200000,false),chunked=filtered(200000,true),alias=filtered(392000,false);
    require(desired.size()==count*2/8 && desired==chunked,"Eightfold traffic reduction with block-invariant streaming");
    auto amplitude=[](const std::vector<unsigned char>& samples) { double power=0; size_t n=0;
        for(size_t j=2000;j+1<samples.size();j+=2) { power+=std::pow(double(samples[j])-127.5,2)+std::pow(double(samples[j+1])-127.5,2); ++n; }
        return std::sqrt(power/n); };
    require(amplitude(desired)>47,"Desired channel retained at worker Fs/4 offset");
    require(amplitude(alias)<1.5,"Aliasing adjacent signal suppressed before downsampling");
    require(!dsd_channel_filter_create(inputRate,123456,0),"Unsupported ratio refused");
    dsd_channel_worker_rate_set(192000); require(dsd_channel_worker_rate()==192000,"Worker rate override");
    dsd_channel_worker_rate_set(123); require(dsd_channel_worker_rate()==0,"Invalid override disabled");
    std::vector<unsigned char> input(48000*2),output(input.size()),partitioned(input.size());
    for(size_t i=0;i<input.size()/2;++i) { input[2*i]=static_cast<unsigned char>(127.5+50*std::cos(2*pi*3000*i/48000)); input[2*i+1]=static_cast<unsigned char>(127.5+50*std::sin(2*pi*3000*i/48000)); }
    double phase=0; dsd_channel_translate(input.data(),output.data(),input.size(),-3000,48000,&phase);
    double error=0; for(size_t i=500;i<output.size()/2;++i) error+=std::abs(double(output[2*i])-177.5)+std::abs(double(output[2*i+1])-127.5);
    require(error/(output.size()/2-500)<2,"Frequency translator moves a tone exactly to DC");
    phase=0; for(size_t at=0;at<input.size();) { size_t count=std::min<size_t>(202,input.size()-at); dsd_channel_translate(input.data()+at,partitioned.data()+at,count,-3000,48000,&phase); at+=count; }
    double difference=0; for(size_t i=0;i<output.size();++i) difference+=std::abs(int(output[i])-int(partitioned[i]));
    require(difference/input.size()<0.1,"Translation carries oscillator phase across blocks");
    std::vector<float> iq(96000); for(size_t i=0;i<iq.size()/2;++i) { iq[2*i]=float(std::cos(2*pi*3000*i/48000)); iq[2*i+1]=float(std::sin(2*pi*3000*i/48000)); }
    auto original=iq; dsd_equalizer_enable(0); dsd_equalizer_process(iq.data(),iq.size(),10); require(iq==original,"Equalizer bypass is exact");
    dsd_equalizer_enable(1); dsd_equalizer_process(iq.data(),iq.size(),10); for(auto x:iq) require(std::isfinite(x),"Equalizer remains finite");
    dsd_equalizer_enable(0); dsd_trial_configure(0,4000); iq=original; dsd_trial_process(iq.data(),iq.size(),48000);
    double power=0; for(size_t i=1000;i<iq.size();++i) power+=iq[i]*iq[i];
    require(power/(iq.size()-1000)<0.04,"Trial bandwidth filter rejects tone outside passband");
    dsd_trial_configure(250,0); iq=original; dsd_trial_process(iq.data(),iq.size(),48000);
    double dot=0; for(size_t i=1000;i<iq.size()/2;++i) dot+=iq[2*i]*std::cos(2*pi*2750*i/48000)+iq[2*i+1]*std::sin(2*pi*2750*i/48000);
    require(dot/(iq.size()/2-1000)>0.99,"Trial frequency offset applied to actual complex samples"); dsd_trial_configure(0,0);
    dsd_dual_grant grant{}; dsd_dual_enable(0); require(!dsd_dual_offer(851000000,1,2,3,4,5,1,0,9),"Disabled dual mode does not consume grants");
    dsd_dual_enable(1); require(dsd_dual_offer(851000000,0xbee00,0x123,0x456,12,34,1,1,9),"Dual route accepts grant");
    require(dsd_dual_get(&grant)&&grant.wacn==0xbee00&&grant.frequency==851000000&&grant.slot==1,"P25 voice context travels intact"); dsd_dual_enable(0);
    dsd_voice_tune request{grant,1}; require(dsd_voice_tune_valid(&request),"Complete P25 voice request accepted");
    request.grant.nac=0; require(!dsd_voice_tune_valid(&request),"Incomplete TDMA context rejected");
    request.grant.tdma=0; require(dsd_voice_tune_valid(&request),"FDMA can acquire NAC from channel");
    request.grant.slot=2; require(!dsd_voice_tune_valid(&request),"Invalid slot rejected");
    dsd_voice_tune_result(12,1); uint64_t sequence=0;
    require(dsd_voice_tune_status(&sequence)==1 && sequence==12,"Applied tune acknowledged by sequence");
    dsd_dmr_evidence_reset(); dsd_dmr_evidence_note(0,0,0,1); dsd_dmr_evidence_note(1,1,0,0); dsd_dmr_evidence_note(1,1,1,0);
    dsd_dmr_evidence evidence{}; dsd_dmr_evidence_get(&evidence);
    require(evidence.checked[0]==1 && evidence.suspected_ras[1]==1 && evidence.rejected[1]==1,"RAS suspicion is separate from valid and damaged bursts");
}
void library() {
    QSettings().clear(); const auto dir=dsd_qt::CallLibrary::directory(); QDir().mkpath(dir+"/main");
    auto create=[&](const QString& name,qint64 time,bool sidecar) { QFile wave(dir+"/main/"+name+".wav"); require(wave.open(QIODevice::WriteOnly),"create wav fixture"); wave.write("RIFF test fixture"); wave.close();
        if(sidecar) { QFile meta(dir+"/main/"+name+".json"); meta.open(QIODevice::WriteOnly); meta.write(QJsonDocument(QJsonObject{{"start_time",time},{"stop_time",time+2},{"talkgroup",100},{"talkgroup_tag","Test dispatch"},{"freq",155000000}}).toJson()); } };
    const auto now=QDateTime::currentSecsSinceEpoch(); create("old",now-60*86400,true); create("favorite",now-60*86400,true); create("new",now,true); create("active",now-60*86400,false);
    QSettings().setValue("calls/favorites/main/favorite.wav",true);
    dsd_qt::CallLibrary calls; calls.refresh();
    require(!QFile::exists(dir+"/main/old.wav"),"Retention removes completed expired call");
    require(QFile::exists(dir+"/main/favorite.wav") && QFile::exists(dir+"/main/active.wav"),"Retention protects favorite and unfinished WAV");
    require(calls.calls().size()==2,"Only finalized calls indexed"); calls.setQuery("*"); require(calls.calls().size()==1,"Favorite search");
    calls.setQuery("155.000"); require(calls.calls().size()==2,"Frequency search");
    require(!calls.remove("../escape.wav")&&!calls.remove("main/favorite.wav"),"Deletion cannot escape root or remove favorite");
    QTemporaryDir exported; require(calls.exportCall("main/new.wav",exported.path()).isEmpty(),"WAV and metadata export"); require(QFile::exists(exported.path()+"/new.json"),"Export keeps metadata");
    require(QFileInfo(dir).canonicalFilePath().startsWith(QFileInfo(QStandardPaths::writableLocation(QStandardPaths::AppDataLocation)).canonicalFilePath()+"/"),"test cleanup stays inside unique test directory"); QDir(dir).removeRecursively(); // dir is the unique test-mode application directory under Qt's test root.
}
int main(int argc,char**argv) {
    QCoreApplication app(argc,argv); QCoreApplication::setOrganizationName("XeraXTests"); QCoreApplication::setApplicationName("advanced-receiver-"+QUuid::createUuid().toString(QUuid::Id128)); QStandardPaths::setTestModeEnabled(true);
    try {
        xerax::ReceptionSample measurement;
        xerax::ReceptionReading reading{100,10,2,155000000,12,true,true};
        measurement.begin(reading);
        reading.ms=10100; reading.good=25; reading.bad=3;
        require(!measurement.add(reading),"Reception observation remains open before duration");
        reading.ms=30100; reading.good=40; reading.snr=16;
        require(measurement.add(reading) && measurement.valid && !measurement.active,"Reception finishes at thirty seconds");
        require(measurement.accepted()==30 && measurement.rejected()==1 && measurement.snrSum/measurement.samples==14,"Reception deltas and valid SNR average");
        measurement.begin(reading); reading.ms+=1000; reading.frequency+=12500;
        require(measurement.add(reading) && !measurement.valid,"A retune invalidates paired reception measurement");
        measurement.begin(reading); reading.ms+=1000; reading.good=0;
        require(measurement.add(reading) && !measurement.valid,"Counter reset cannot underflow reception score");
        QTemporaryDir captures; std::vector<float> pcm(4800,1200);
        dsd_analog_record(captures.path().toUtf8().constData(),pcm.data(),pcm.size(),48000,155000000,1);
        require(QDir(captures.path()).entryList({"*.json"},QDir::Files).isEmpty(),"Active analog recording has no completion sidecar");
        for(int i=0;i<10;i++) dsd_analog_record(captures.path().toUtf8().constData(),pcm.data(),pcm.size(),48000,155000000,0);
        auto metas=QDir(captures.path()).entryList({"*.json"},QDir::Files); require(metas.size()==1,"Analog squelch hang closes recording");
        QFile wave(captures.path()+"/"+metas[0].replace(".json",".wav")); require(wave.open(QIODevice::ReadOnly),"Analog WAV exists"); auto wav=wave.readAll();
        require(wav.size()==44+11*4800*2 && wav.left(4)=="RIFF" && wav.mid(8,4)=="WAVE","Analog recording has correct WAV length and header");
        require(static_cast<unsigned char>(wav[44])==0xb0 && static_cast<unsigned char>(wav[45])==4,"Analog PCM keeps amplitude");
        signals(); translation(); library(); std::puts("AFSK/CRC, DTMF, paging, channel DSP, trial processing, grant context, recording retention passed"); }
    catch(const std::exception& e) { std::fprintf(stderr,"FAIL: %s\n",e.what()); return 1; }
    return 0;
}
