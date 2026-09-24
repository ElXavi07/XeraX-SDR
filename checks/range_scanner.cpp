// SPDX-License-Identifier: GPL-3.0-or-later
#include <QCoreApplication>
#include <QStandardPaths>
#include <QUuid>
#include <cstdio>
#include "range_scanner.h"
#include "saved_systems_model.h"
#include "decode_mode_flag.h"
#include <dsd-neo/platform/audio_replay.h>

// Only RF input and queued hardware commands are injected. The production
// scanner, settings, detector, hold policy and persistence run unchanged.
extern "C" int dsd_app_frontend_wideband_spectrum_get(float*,int,uint32_t*,uint32_t*,uint32_t*) {return 0;}
class Radio:public QObject {
    Q_OBJECT
public:
    QObject* metrics=nullptr;bool owned=false,accepted=true;uint32_t requested=0;int tunes=0;
    Q_INVOKABLE void setRangeScanOwned(bool on){owned=on;}
    Q_INVOKABLE bool rangeTuneHz(unsigned int hz){requested=hz;++tunes;return owned && accepted;}
    Q_INVOKABLE bool rangeDecodeMode(int mode){metrics->setProperty("decodeMode",mode);return owned && accepted;}
};
class Scanner:public dsd_qt::RangeScanner {
public:
    mutable Frame incoming;
    qint64 time=1000;quint64 pcm=0;bool quiet=false;
    Scanner(){incoming.bins.fill(-80,1024);incoming.span=1536000;incoming.center=440000000;incoming.serial=1;}
    qint64 nowMs()const override{return time;}
    Frame readFrame()const override{return incoming;}
    quint64 pcmFrames()const override{return pcm;}
    void gateAudio(bool on)override{quiet=on;}
    void tick(int ms=100,bool fresh=true){time+=ms;if(fresh)++incoming.serial;poll();}
    void noise(){incoming.bins.fill(-80);}
    void signal(uint32_t hz){
        const int bin=int(std::llround((double(hz)-incoming.center)/incoming.span*incoming.bins.size()+incoming.bins.size()/2));
        for(int d=-1;d<=1;++d)if(bin+d>=0 && bin+d<incoming.bins.size())incoming.bins[bin+d]=d?-48:-40;
    }
};
int main(int argc,char** argv){
    QCoreApplication app(argc,argv);QStandardPaths::setTestModeEnabled(true);
    app.setOrganizationName("XeraXTests");app.setApplicationName("range-"+QUuid::createUuid().toString(QUuid::WithoutBraces));
    int failures=0;auto check=[&](bool ok,const char* name){if(!ok){++failures;std::fprintf(stderr,"FAIL: %s\n",name);}};
    using namespace xerax::range_scan;
    Plan p{440000000,460000000,12500};check(p.valid() && p.count()==1601 && p.frequency(1600)==460000000,"inclusive integer frequency grid");
    p.last=450000001;check(p.count()==801 && p.frequency(p.count()-1)==450000000,"non-divisible end does not overshoot");
    int covered=0,tiles=0;while(covered<p.count()){auto t=tile(p,covered,1536000);check(t.begin==covered && t.end>t.begin,"tile coverage progresses");covered=t.end;++tiles;}
    check(covered==801 && tiles==11,"wideband tiles replace 801 individual tuning requests");
    QVector<float> bins(1024,-80);const uint32_t center=440500000,span=1536000,target=440600000;
    check(strength(bins.data(),1024,center,span,target,12500).excess<6,"noise is not activity");
    const int bin=int(std::round((double(target)-center)/span*1024+512));bins[bin]=-20;
    check(strength(bins.data(),1024,center,span,target,12500).excess<6,"single-bin spike rejected");
    bins[bin+1]=-40;bins[bin-1]=-40;
    check(strength(bins.data(),1024,center,span,target,12500).excess>20,"carrier detected");
    check(strength(bins.data(),1024,center,span,target+12500,12500).excess<6,"adjacent grid frequency not duplicated");
    check(!strength(bins.data(),1024,center,8000000,target,5000).valid,"inadequate FFT resolution rejected");
    for(auto& b:bins)b=NAN;
    check(!strength(bins.data(),1024,center,span,target,12500).valid,"non-finite spectra rejected");

    QObject metrics,host,tools,assistant,expansion;Radio radio;radio.metrics=&metrics;
    metrics.setProperty("optionsKnown",true);metrics.setProperty("radioInput",true);metrics.setProperty("centerFreqHz",440000000.0);
    metrics.setProperty("tunerControlled",false);host.setProperty("running",true);host.setProperty("sessionState",2);
    metrics.setProperty("decodeMode",dsd_qt::decode_mode_for_flag("-fA"));
    dsd_qt::SavedSystemsModel systems;Scanner scan;
    scan.configure(&metrics,&radio,&host,nullptr,&tools,&assistant,&expansion,&systems);
    scan.setSession({{"sourceType","rtltcp"},{"host","192.168.1.245"},{"port",1234},{"encKeyValue","must-not-copy"}});
    auto settings=scan.settings();settings["speed"]=0;settings["decodeFlag"]="-fA";settings["maxVisitMs"]=5000;settings["tailMs"]=500;
    for(const QVariant& bad:QVariantList{NAN,INFINITY,-1,"broken",true}){auto s=settings;s["firstMhz"]=bad;check(!scan.validate(s).isEmpty(),"invalid range rejected");}
    {auto s=settings;s["lastMhz"]="439";check(!scan.validate(s).isEmpty(),"reversed range rejected");}
    check(scan.start(settings).isEmpty() && scan.active() && radio.owned && scan.quiet,"starts with receiver ownership and quiet sweep");
    check(!scan.start(settings).isEmpty(),"active settings cannot be overwritten");
    scan.poll();const auto firstTune=radio.requested;
    scan.incoming.center=firstTune;metrics.setProperty("centerFreqHz",double(firstTune));
    const int initialTunes=radio.tunes;
    for(int i=0;i<5;++i)scan.tick(100,false);
    check(radio.tunes==initialTunes && scan.status().value("phase")=="tuning","duplicate frames cannot complete a tune");
    // Simulate actual hardware acknowledging each requested tile, with fresh FFTs.
    const auto sweepStart=scan.time;
    for(int i=0;i<150 && scan.status().value("passes").toInt()<2;++i){scan.incoming.center=radio.requested;metrics.setProperty("centerFreqHz",double(radio.requested));scan.tick();}
    check(scan.active() && scan.status().value("passes").toInt()==2 && radio.tunes-initialTunes<=12,"empty range loops through blocks");
    check(scan.time-sweepStart<8000,"synthetic blank sweep avoids per-channel decode dwell");
    scan.stop();check(!radio.owned && !scan.quiet && !scan.active(),"stop releases all scanner resources");

    settings["lastMhz"]="440.050000";
    check(scan.start(settings).isEmpty(),"start short analog scan");scan.poll();
    const uint32_t carrier=440012500;
    auto advance=[&](bool present,int ms=100){scan.incoming.center=radio.requested;metrics.setProperty("centerFreqHz",double(radio.requested));scan.noise();if(present)scan.signal(carrier);scan.tick(ms);};
    for(int i=0;i<25 && scan.status().value("phase")!="listening";++i)advance(true);
    check(scan.status().value("phase")=="listening" && radio.requested==carrier && !scan.quiet,"detected NFM carrier becomes audible");
    check(!scan.hits().isEmpty() && scan.hits()[0].toMap().value("protocol")=="NFM","real analog finding recorded");
    const int before=radio.tunes;scan.hold(true);
    for(int i=0;i<65;++i)advance(true);
    check(radio.tunes==before && scan.status().value("held").toBool(),"manual hold overrides visit limit");
    check(scan.saveHit(0) && systems.count()==1,"found channel saved");
    const auto saved=systems.get(0);check(saved.value("encKeyValue").toString().isEmpty() && saved.value("host")=="192.168.1.245","saved discovery keeps source but excludes keys");
    check(scan.saveHit(0) && systems.count()==1,"save button does not duplicate discovery");
    check(scan.saveFrequency(carrier) && !scan.saveFrequency(carrier+100000),"save resolves stable displayed frequency and rejects unknown positions");
    scan.avoid();check(scan.active() && scan.status().value("avoided").toInt()==1,"avoid advances immediately");
    for(int i=0;i<30;++i)advance(true);
    check(!scan.status().value("candidate").toBool(),"avoided frequency is not reacquired on next pass");
    scan.clearAvoids();for(int i=0;i<30 && scan.status().value("phase")!="listening";++i)advance(true);
    check(scan.status().value("phase")=="listening","clearing avoids restores acquisition");
    const auto listeningTune=radio.tunes;
    for(int i=0;i<3;++i)advance(false);
    check(scan.quiet && radio.tunes==listeningTune,"analog squelch closes during tail without immediate hop");
    for(int i=0;i<20 && radio.tunes==listeningTune;++i)advance(false);
    check(radio.tunes>listeningTune,"quiet channel resumes after acquisition and tail");scan.stop();

    settings["decodeFlag"]="-fa";metrics.setProperty("decodeMode",dsd_qt::decode_mode_for_flag("-fa"));check(scan.start(settings).isEmpty(),"start auto digital");scan.poll();
    for(int i=0;i<30 && !scan.status().value("candidate").toBool();++i)advance(true);
    const int candidateTune=radio.tunes;
    metrics.setProperty("syncedHere",true);metrics.setProperty("syncLabel","DMR");
    for(int i=0;i<20 && radio.tunes==candidateTune;++i)advance(true);
    check(radio.tunes>candidateTune,"sync without voice cannot trap the scan indefinitely");
    for(int i=0;i<30 && !scan.status().value("candidate").toBool();++i)advance(true);
    metrics.setProperty("slot1CallState",2);
    for(int i=0;i<9;++i){scan.pcm+=4800;advance(true);}
    check(scan.status().value("phase")=="listening","actual digital PCM and voice state extend listening");
    metrics.setProperty("slot1CallState",0);metrics.setProperty("syncedHere",false);const int voiceTune=radio.tunes;
    for(int i=0;i<20 && radio.tunes==voiceTune;++i)advance(false);
    check(radio.tunes>voiceTune,"digital hang tail returns to sweep");scan.stop();

    check(scan.start(settings).isEmpty(),"start timeout case");scan.poll();
    scan.tick(5100,false);check(!scan.active() && !scan.quiet,"stale network data stops scanner and releases audio");
    radio.accepted=false;check(!scan.start(settings).isEmpty() && !scan.active() && !radio.owned,"queue rejection unwinds ownership");radio.accepted=true;
    metrics.setProperty("tunerControlled",true);check(!scan.start(settings).isEmpty(),"trunk/list conflict refused");metrics.setProperty("tunerControlled",false);
    expansion.setProperty("status",QVariantMap{{"receptionRunning",true}});check(!scan.start(settings).isEmpty(),"measurement conflict refused");expansion.setProperty("status",QVariantMap{});
    check(scan.start(settings).isEmpty(),"start external mode case");scan.poll();metrics.setProperty("decodeMode",99);scan.tick();check(!scan.active(),"external mode change terminates ownership");
    check(scan.start(settings).isEmpty(),"start stalled tune");scan.poll();scan.incoming.center=99;scan.tick(8100);check(!scan.active(),"wrong-frequency fresh frames cannot acknowledge tune");
    host.setProperty("running",false);scan.setSession({{"sourceType","usb"},{"rangeScanOptions",settings}});scan.poll();check(scan.status().value("pending").toBool(),"USB permission/start can remain pending");
    host.setProperty("running",true);scan.poll();check(scan.active(),"range scan starts after source becomes ready");host.setProperty("running",false);scan.poll();check(!scan.active(),"session ending releases scan");
    dsd_audio_live_suppress(1);dsd_audio_range_suppress(1);dsd_audio_range_suppress(0);check(dsd_audio_live_suppressed(),"range gate cannot unmute replay worker");
    dsd_audio_live_suppress(0);dsd_audio_range_suppress(1);check(dsd_audio_live_suppressed(),"range gate independently suppresses");dsd_audio_range_suppress(0);
    host.setProperty("running",true);metrics.setProperty("decodeMode",dsd_qt::decode_mode_for_flag("-fA"));
    scan.setSession({{"sourceType","usb"},{"decodeFlag","-fA"}});QVariantMap restart;
    QObject::connect(&scan,&dsd_qt::RangeScanner::restartRequested,&scan,[&](const QVariantMap& s){restart=s;});
    check(scan.start(settings).isEmpty() && !scan.active() && restart.value("decodeFlag")=="-fa"
        && restart.value("rangeScanOptions").toMap()==settings,"analog-to-digital uses full receiver restart path");
    std::fprintf(stderr,"%d range scan failures. Synthetic spectra/clock and real controller; no hardware speed claim.\n",failures);
    return failures?1:0;
}
#include "range_scanner.moc"
