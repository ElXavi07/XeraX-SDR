// SPDX-License-Identifier: GPL-3.0-or-later
#include "range_scanner.h"
#include "saved_systems_model.h"
#include <QSettings>
#include <QDateTime>
#include <QRegularExpression>
#include <dsd-neo/app_control/frontend.h>
#include <dsd-neo/core/wideband_spectrum.h>
#include <dsd-neo/runtime/decode_mode.h>
#include <dsd-neo/platform/audio_replay.h>
#include <cmath>

namespace dsd_qt {
namespace {
QVariantMap defaults() { return {{"firstMhz","440.000000"},{"lastMhz","450.000000"},{"stepKhz",12.5},
    {"decodeFlag","-fa"},{"speed",1},{"thresholdDb",10},{"tailMs",1200},{"maxVisitMs",15000}}; }
const QStringList modes={"-fa","-fA","-fU","-fs","-f1","-f2","-fi","-fn"};
bool number(const QVariantMap& map,const char* name,double low,double high,bool integer=false) {
    const QVariant v=map.value(name); bool ok=false; const double n=v.toDouble(&ok);
    return v.metaType().id()!=QMetaType::Bool && ok && std::isfinite(n) && n>=low && n<=high && (!integer || std::floor(n)==n);
}
xerax::range_scan::Plan plan(const QVariantMap& s) {
    return {uint32_t(std::llround(s.value("firstMhz").toDouble()*1e6)),uint32_t(std::llround(s.value("lastMhz").toDouble()*1e6)),
            uint32_t(std::llround(s.value("stepKhz").toDouble()*1000))};
}
bool busyWorkers(QObject* expansion) {
    if(!expansion) return false;
    const auto s=expansion->property("status").toMap();
    if(s.value("surveying").toBool() || s.value("geoScanning").toBool() || s.value("labRunning").toBool()
        || s.value("receptionRunning").toBool() || s.value("siteCapture").toBool() || s.value("dual").toBool()) return true;
    for(const auto& v:expansion->property("lanes").toList())
        if(QStringList{"running","starting","stopping"}.contains(v.toMap().value("state").toString())) return true;
    return false;
}
}
RangeScanner::RangeScanner(QObject* parent):QObject(parent) {
    m_clock.start(); m_settings=defaults();
    const auto saved=QSettings().value("rangeScanner/settings").toMap();
    if(!saved.isEmpty() && validate(saved).isEmpty()) m_settings=saved;
    m_message=tr("Choose a range, then start scanning."); publish();
    m_timer.setInterval(33); m_timer.setTimerType(Qt::PreciseTimer);
    connect(&m_timer,&QTimer::timeout,this,&RangeScanner::poll);
}
RangeScanner::~RangeScanner() { own(false); gateAudio(false); }
void RangeScanner::configure(QObject* metrics,QObject* commands,QObject* host,QObject* spectrum,QObject* tools,
    QObject* assistant,QObject* expansion,SavedSystemsModel* systems) {
    m_metrics=metrics;m_commands=commands;m_host=host;m_spectrum=spectrum;m_tools=tools;
    m_assistant=assistant;m_expansion=expansion;m_systems=systems;
}
QString RangeScanner::validate(const QVariantMap& s) const {
    if(!number(s,"firstMhz",24,1766) || !number(s,"lastMhz",24,1766) || !number(s,"stepKhz",5,100)
        || std::abs(s.value("stepKhz").toDouble()*1000-std::round(s.value("stepKhz").toDouble()*1000))>0.001)
        return tr("Use 24–1766 MHz and a channel step of 5–100 kHz.");
    const auto p=plan(s);
    if(!p.valid()) return tr("End must follow start; use at most 50 MHz and 10,001 channel positions.");
    if(!modes.contains(s.value("decodeFlag").toString())) return tr("Choose a supported scanning mode.");
    if(!number(s,"speed",0,2,true) || !number(s,"thresholdDb",6,30,true)
        || !number(s,"tailMs",300,5000,true) || !number(s,"maxVisitMs",0,120000,true)
        || (s.value("maxVisitMs").toInt()!=0 && s.value("maxVisitMs").toInt()<5000))
        return tr("Check scan speed, signal threshold, resume delay and maximum listening time.");
    return {};
}
QString RangeScanner::saveSettings(const QVariantMap& s) {
    const auto error=validate(s); if(!error.isEmpty()) return error;
    m_settings.clear(); for(const auto& key:defaults().keys()) m_settings[key]=s.value(key);
    QSettings().setValue("rangeScanner/settings",m_settings); Q_EMIT changed(); return {};
}
QVariant RangeScanner::value(const char* key) const { return m_metrics?m_metrics->property(key):QVariant(); }
QString RangeScanner::readiness() const {
    if(!m_host || !m_host->property("running").toBool() || !value("optionsKnown").toBool() || !value("radioInput").toBool())
        return tr("Start a USB radio or RTL-TCP receiver first.");
    if(value("tunerControlled").toBool() || value("scannerMode").toBool() || value("heldTg").toUInt() || value("scanHold").toBool())
        return tr("Stop the channel list or trunk following and release holds first.");
    if(busyWorkers(m_expansion) || (m_assistant && (m_assistant->property("autoGain").toBool()
        || m_assistant->property("roaming").toBool() || m_assistant->property("status").toMap().value("capturing").toBool())))
        return tr("Stop receiver experiments, recording I/Q, extra receivers and automatic site selection first.");
    if(m_tools) {
        const auto health=m_tools->property("health").toMap();
        if(health.value("thermal").toInt()>=3) return tr("Let the phone cool before starting a range scan.");
        if(health.value("replaying").toBool() || health.value("workerAudio").toBool() || health.value("testingAudio").toBool())
            return tr("Stop replay, extra receiver audio and test tones first.");
    }
    return {};
}
bool RangeScanner::command(const char* method,unsigned int hz) {
    bool accepted=false;
    return m_commands && QMetaObject::invokeMethod(m_commands,method,Qt::DirectConnection,Q_RETURN_ARG(bool,accepted),Q_ARG(unsigned int,hz)) && accepted;
}
bool RangeScanner::modeCommand(int mode) {
    bool accepted=false;
    return m_commands && QMetaObject::invokeMethod(m_commands,"rangeDecodeMode",Qt::DirectConnection,Q_RETURN_ARG(bool,accepted),Q_ARG(int,mode)) && accepted;
}
void RangeScanner::own(bool on) {
    if(m_commands) QMetaObject::invokeMethod(m_commands,"setRangeScanOwned",Qt::DirectConnection,Q_ARG(bool,on));
    if(m_metrics) m_metrics->setProperty("rangeScanActive",on);
    if(m_spectrum) QMetaObject::invokeMethod(m_spectrum,"setScanActive",Qt::DirectConnection,Q_ARG(bool,on));
}
QString RangeScanner::start(const QVariantMap& s) {
    if(m_active) return tr("Stop the current range scan before changing its settings.");
    auto error=validate(s); if(error.isEmpty()) error=readiness(); if(!error.isEmpty()) return error;
    if(!m_session.value("iqCapturePath").toString().isEmpty()) return tr("Stop I/Q recording before scanning.");
    dsdneoUserDecodeMode desired{};
    dsd_decode_mode_from_cli_preset(s.value("decodeFlag").toString().back().toLatin1(),&desired);
    const int current=value("decodeMode").toInt();
    const auto analogMode=[](int mode){return mode==DSDCFG_MODE_ANALOG || mode==DSDCFG_MODE_AM || mode==DSDCFG_MODE_WFM;};
    if(current!=desired && (analogMode(current) || analogMode(desired))) {
        if(m_session.value("sourceType").toString().isEmpty()) return tr("Start this listening mode from Explore before scanning.");
        // Analog changes require reopening the frontend and audio stream. Use
        // Main's existing USB-permission/Idle restart path, not a live flag flip.
        auto session=m_session;session["decodeFlag"]=s.value("decodeFlag");session["rangeScanOptions"]=s;
        session["freqMhz"]=s.value("firstMhz");session["bandwidthKhz"]=48;session["trunking"]=false;
        m_message=tr("Restarting the receiver for the selected listening mode…");publish();
        Q_EMIT restartRequested(session);return {};
    }
    saveSettings(s); m_pending.clear(); m_plan=plan(s); m_avoids.clear(); m_hits.clear();m_candidates.clear();
    Q_EMIT hitsChanged();
    m_threshold=s.value("thresholdDb").toDouble(); m_tail=s.value("tailMs").toInt();m_maxVisit=s.value("maxVisitMs").toInt();
    const int speed=s.value("speed").toInt();
    m_settle=speed==0?120:speed==1?180:300; m_probeFrames=speed==2?3:2;
    // rtl_tcp commands have no RF timestamp/ack; allow extra queued-network
    // settling in addition to the frontend's purge and matching-frame checks.
    if(m_session.value("sourceType").toString()=="rtltcp")m_settle+=180;
    m_acquire=speed==0?1200:speed==1?3000:6000;
    const auto flag=s.value("decodeFlag").toString();
    dsdneoUserDecodeMode decoded{};
    if(dsd_decode_mode_from_cli_preset(flag.back().toLatin1(),&decoded)!=0) return tr("Choose a supported scanning mode.");
    m_mode=static_cast<int>(decoded);m_analog=flag=="-fA" || flag=="-fU";
    if(!m_analog && flag!="-fa") m_acquire=std::max(900,m_acquire*2/3);
    m_active=true;m_held=false;m_candidate=false;m_tuning=false;m_modeReady=false;
    m_nextIndex=0;m_pass=1;m_started=nowMs();m_requested=m_started;m_lastFrame=m_started;
    m_lastSerial=0;m_span=0;m_expected=0;m_phase="starting";m_message.clear();
    own(true);gateAudio(true);
    if(!modeCommand(m_mode)) { finish(tr("The receiver rejected the scan mode. Try again after it is ready."));return m_message; }
    m_timer.start();publish();return {};
}
void RangeScanner::setSession(const QVariantMap& session) {
    if(m_active) finish(tr("Range scanning stopped because the receiver session changed."));
    m_session=session;m_pending=session.value("rangeScanOptions").toMap();m_pendingAt=nowMs();
    if(!m_pending.isEmpty()) { m_phase="starting";m_message=tr("Waiting for the receiver to start…");m_timer.start();publish(); }
}
void RangeScanner::stop() { m_pending.clear();finish(tr("Range scanning stopped. The receiver stays on its current frequency.")); }
void RangeScanner::finish(const QString& text) {
    m_active=false;m_tuning=false;m_held=false;m_phase="stopped";m_message=text;
    own(false);gateAudio(false);m_timer.stop();publish();
}
void RangeScanner::hold(bool on) {
    if(!m_active || !m_candidate || m_tuning) return;
    m_held=on;if(!on) m_lastActive=nowMs();publish();
}
void RangeScanner::skip() { if(m_active && m_candidate && !m_tuning) {m_held=false;nextCandidate();publish();} }
void RangeScanner::avoid() {
    if(!m_active || !m_candidate || m_tuning) return;
    m_avoids.insert(m_expected);skip();
}
void RangeScanner::clearAvoids() {m_avoids.clear();publish();}
void RangeScanner::tune(uint32_t hz,bool candidate) {
    gateAudio(true);m_expected=hz;m_candidate=candidate;m_tuning=true;m_phase="tuning";
    m_requested=nowMs();m_seenFrames=0;m_observations=0;m_everActive=false;m_held=false;m_lastActive=0;
    if(!command("rangeTuneHz",hz)) finish(tr("The receiver rejected a tuning request. Scanning stopped."));
}
void RangeScanner::nextTile(uint32_t span) {
    if(m_nextIndex>=m_plan.count()) {m_nextIndex=0;++m_pass;}
    m_tile=xerax::range_scan::tile(m_plan,m_nextIndex,span);
    m_votes.fill(0,m_tile.end-m_tile.begin);m_candidates.clear();
    tune(m_tile.center,false);
}
void RangeScanner::nextCandidate() {
    while(!m_candidates.isEmpty()) {
        const auto hz=m_candidates.takeFirst();
        if(!m_avoids.contains(hz)) {tune(hz,true);return;}
    }
    nextTile(m_span);
}
void RangeScanner::noteHit(double excess,const QString& protocol,bool voice) {
    int index=-1;
    for(int i=0;i<m_hits.size();++i) if(m_hits[i].toMap().value("frequency").toUInt()==m_expected){index=i;break;}
    auto hit=index<0?QVariantMap{{"frequency",m_expected},{"protocol",QString()},{"voice",false},{"saved",false}}:m_hits[index].toMap();
    const bool firstHere=index<0;
    hit["excessDb"]=std::round(excess*10)/10;hit["lastSeen"]=QDateTime::currentDateTime().toString("HH:mm:ss");
    if(!protocol.isEmpty()) hit["protocol"]=protocol;
    hit["voice"]=voice || hit.value("voice").toBool();
    if(firstHere) {if(m_hits.size()>=500)m_hits.removeLast();m_hits.prepend(hit);} else m_hits[index]=hit;
    m_hitsDirty=true;
}
bool RangeScanner::saveHit(int index) {
    if(!m_systems || index<0 || index>=m_hits.size()) return false;
    auto hit=m_hits[index].toMap();if(hit.value("saved").toBool())return true;
    QVariantMap system;
    for(const auto* field:{"sourceType","host","port","airspy"}) if(m_session.contains(field))system[field]=m_session[field];
    if(system.value("sourceType").toString().isEmpty())return false;
    const auto mhz=QString::number(hit.value("frequency").toDouble()/1e6,'f',6);
    system["name"]=tr("Found %1 MHz").arg(mhz);system["freqMhz"]=mhz;system["trunking"]=false;
    system["decodeFlag"]=m_settings.value("decodeFlag");
    const QMap<QString,QString> detected{{"DMR","-fs"},{"P25p1","-f1"},{"P25p2","-f2"},{"NXDN48","-fi"},{"NXDN96","-fn"}};
    if(detected.contains(hit.value("protocol").toString()))system["decodeFlag"]=detected.value(hit.value("protocol").toString());
    if(!m_systems->add(system))return false;
    hit["saved"]=true;m_hits[index]=hit;Q_EMIT hitsChanged();publish();return true;
}
bool RangeScanner::saveFrequency(unsigned int frequency) {
    // Findings can be prepended between a rendered frame and a tap. Resolve
    // the displayed frequency, never an index from an older UI publication.
    for(int i=0;i<m_hits.size();++i)if(m_hits[i].toMap().value("frequency").toUInt()==frequency)return saveHit(i);
    return false;
}
RangeScanner::Frame RangeScanner::readFrame() const {
    Frame frame;frame.bins.resize(DSD_WIDEBAND_SPECTRUM_BINS);
    const int count=dsd_app_frontend_wideband_spectrum_get(frame.bins.data(),int(frame.bins.size()),&frame.center,&frame.span,&frame.serial);
    frame.bins.resize(std::max(0,count));return frame;
}
qint64 RangeScanner::nowMs() const {return m_clock.elapsed();}
quint64 RangeScanner::pcmFrames() const {return dsd_audio_nonzero_frames();}
void RangeScanner::gateAudio(bool quiet) {dsd_audio_range_suppress(quiet?1:0);}
void RangeScanner::publish() {
    const auto now=nowMs();
    if(m_hitsDirty && (now-m_hitsPublished>=1000 || !m_active)) {m_hitsPublished=now;m_hitsDirty=false;Q_EMIT hitsChanged();}
    if(m_active && now-m_published<200 && m_status.value("phase").toString()==m_phase
        && m_status.value("frequency").toUInt()==m_expected && m_status.value("held").toBool()==m_held)return;
    m_published=now;
    m_status={{"phase",m_phase},{"message",m_message},{"held",m_held},{"candidate",m_candidate && !m_tuning},
        {"frequency",m_expected},{"passes",m_pass},{"checked",m_nextIndex},{"positions",m_plan.count()},
        {"avoided",m_avoids.size()},{"hits",m_hits.size()},{"captureSpanHz",m_span},
        {"elapsedSeconds",m_active?(nowMs()-m_started)/1000:0},{"pending",!m_pending.isEmpty()}};
    Q_EMIT changed();
}
void RangeScanner::poll() {
    const auto now=nowMs();
    if(!m_pending.isEmpty()) {
        if(m_host && m_host->property("running").toBool() && value("optionsKnown").toBool()) {
            const auto request=m_pending;m_pending.clear();const auto error=start(request);if(!error.isEmpty())finish(error);
        } else if(now-m_pendingAt>30000 || (m_host && m_host->property("sessionState").toInt()==4)) {
            m_pending.clear();finish(tr("The receiver did not start. Check the source connection, then retry."));
        }
        return;
    }
    if(!m_active)return;
    const auto error=readiness();if(!error.isEmpty()){finish(error);return;}
    if(value("decodeMode").toInt()!=m_mode) {
        if(m_modeReady || now-m_requested>8000)finish(tr("The listening mode changed or could not be applied. Scanning stopped."));
        return;
    }
    m_modeReady=true;
    const Frame frame=readFrame();
    const bool fresh=frame.bins.size()>=64 && frame.span>0 && frame.serial && frame.serial!=m_lastSerial;
    if(!fresh) {
        if(now-m_lastFrame>5000)finish(tr("No fresh spectrum is reaching the scanner. Check the radio or Wi-Fi connection."));
        return;
    }
    m_lastSerial=frame.serial;m_lastFrame=now;
    if(double(frame.span)/double(frame.bins.size())>m_plan.step/2.0) {
        finish(tr("The capture is too wide for this channel step. Use a larger step or a narrower capture bandwidth."));return;
    }
    if(!m_span) {m_span=frame.span;nextTile(m_span);publish();return;}
    if(frame.span!=m_span) {finish(tr("Capture bandwidth changed. Restart the range scan."));return;}
    if(frame.center!=m_expected) {
        if(!m_tuning || now-m_requested>8000)finish(tr("The receiver did not reach the requested frequency. Scanning stopped."));
        return;
    }
    if(m_tuning) {
        if(now-m_requested<m_settle)return;
        if(++m_seenFrames<2)return;
        m_tuning=false;m_landed=now;m_lastPcm=pcmFrames();m_phase=m_candidate?"acquiring":"sweeping";
        // Digital media can play as soon as the real decoder produces it. Analog
        // stays quiet until the measured carrier passes the threshold below.
        gateAudio(!m_candidate || m_analog);
        publish();return;
    }
    if(!m_candidate) {
        for(int index=m_tile.begin;index<m_tile.end;++index) {
            const auto hz=m_plan.frequency(index);
            if(m_avoids.contains(hz))continue;
            const auto level=xerax::range_scan::strength(frame.bins.constData(),int(frame.bins.size()),frame.center,frame.span,hz,m_plan.step);
            if(level.valid && level.excess>=m_threshold)++m_votes[index-m_tile.begin];
        }
        if(++m_observations>=m_probeFrames) {
            for(int index=m_tile.begin;index<m_tile.end;++index) if(m_votes[index-m_tile.begin]>=2)m_candidates.append(m_plan.frequency(index));
            m_nextIndex=m_tile.end;nextCandidate();publish();
        }
        return;
    }
    const auto level=xerax::range_scan::strength(frame.bins.constData(),int(frame.bins.size()),frame.center,frame.span,m_expected,m_plan.step);
    const bool carrier=level.valid && level.excess>=m_threshold-(m_everActive?3:0);
    const bool matching=std::abs(value("centerFreqHz").toDouble()-m_expected)<1;
    const bool synced=matching && value("syncedHere").toBool() && now-m_landed>=300;
    const quint64 pcm=pcmFrames();
    const bool voice=!m_analog && synced && pcm>m_lastPcm
        && (value("slot1CallState").toInt()==2 || value("slot2CallState").toInt()==2);
    m_lastPcm=pcm;
    const bool activity=m_analog?carrier:voice;
    if(activity) {m_lastActive=now;m_everActive=true;}
    if(carrier || synced) noteHit(level.valid?level.excess:0,m_analog?m_settings.value("decodeFlag").toString()=="-fU"?"AM":"NFM":synced?value("syncLabel").toString():QString(),voice);
    // Activity describes RF/decoder evidence; user mute, squelch and channel
    // filters still control whether any received audio can reach the speaker.
    if(m_analog)gateAudio(!carrier);
    const bool tail=m_everActive && now-m_lastActive<m_tail;
    m_phase=m_held?"held":activity?"listening":tail?"tail":"acquiring";
    if(!m_held && ((m_maxVisit>0 && now-m_landed>=m_maxVisit)
        || (now-m_landed>=m_acquire && !activity && !tail)))nextCandidate();
    publish();
}
}
