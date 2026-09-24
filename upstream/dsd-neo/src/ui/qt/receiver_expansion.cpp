// SPDX-License-Identifier: GPL-3.0-or-later
#include "receiver_expansion.h"
#include <QUuid>
#include "decoder_host.h"
#include "saved_systems_model.h"
#include "session_args.h"
#include "call_library.h"
#include "json_store.h"
#include <dsd-neo/platform/channel_bank.h>
#include <dsd-neo/platform/receiver_lab.h>
#include <dsd-neo/platform/nxdn_search.h>
#include <dsd-neo/platform/analog_signaling.h>
#include <QDateTime>
#include <QGuiApplication>
#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonObject>
#include <QJsonDocument>
#include <QRegularExpression>
#include <QSaveFile>
#include <QSettings>
#include <QStandardPaths>
#include <QUrl>
#include <algorithm>
#include <cmath>
#ifdef Q_OS_ANDROID
#include <QJniObject>
#include <QCoreApplication>
#endif
namespace dsd_qt {
namespace {
constexpr const char* workers="io/github/arancormonk/dsdneo/ReceiverWorkers";
QString local(const QString& path) { const QUrl url(path); return url.isLocalFile()?url.toLocalFile():path; }
QVariantMap readJson(const QString& path) { QFile f(path); return f.open(QIODevice::ReadOnly)?QJsonDocument::fromJson(f.readAll()).object().toVariantMap():QVariantMap(); }
QString writeJson(const QString& path,const QVariant& value) {
    QSaveFile file(local(path)); const auto bytes=QJsonDocument::fromVariant(value).toJson();
    // Android document-provider URIs cannot be atomically renamed onto.
    file.setDirectWriteFallback(path.startsWith("content://"));
    if(!file.open(QIODevice::WriteOnly) || file.write(bytes)!=bytes.size() || !file.commit()) return file.errorString();
    return {};
}
}
ReceiverExpansion::ReceiverExpansion(QObject* parent):QObject(parent) {
    m_reports=json_store_load_array("lab_reports.json").toVariantList();
    m_receptionReports=json_store_load_array("reception_reports.json").toVariantList();
    dsd_dmr_ras_enable(QSettings().value("receiver/rasReception",false).toBool());
    m_status={{"location",tr("Indio · 50 miles")},{"surveying",false},{"labRunning",false},{"geoScanning",false}};
    m_clock.start(); m_timer.setInterval(1000); connect(&m_timer,&QTimer::timeout,this,&ReceiverExpansion::poll);
}
ReceiverExpansion::~ReceiverExpansion() { if(m_host && m_locationRequest) m_host->cancelLocationRequest(m_locationRequest); }
void ReceiverExpansion::configure(QObject* metrics,QObject* commands,DecoderHost* host,SavedSystemsModel* systems,SessionArgsBuilder* args) {
    m_metrics=metrics; m_commands=commands; m_host=host; m_systems=systems; m_args=args;
    connect(host,&DecoderHost::locationResult,this,[this](qint64 id,bool ok,double lat,double lon,double accuracy,qint64 when,bool,const QString&,const QString&,const QString& error) {
        if(id!=m_locationRequest) return;
        m_locationRequest=0;
        if(!ok || accuracy<0 || !std::isfinite(lat) || !std::isfinite(lon)) { m_status["location"]=error.isEmpty()?tr("Location unavailable; keeping the last center."):error; Q_EMIT changed(); return; }
        m_lat=lat; m_lon=lon; m_accuracy=accuracy; m_fix=when;
        m_status["location"]=tr("Current location · accuracy %1 m").arg(qRound(accuracy)); rankSites(); Q_EMIT changed();
    });
    connect(systems,&SavedSystemsModel::countChanged,this,[this]{rankSites(); Q_EMIT changed();});
    connect(systems,&SavedSystemsModel::sitesChanged,this,[this]{rankSites(); Q_EMIT changed();});
    rankSites(); m_timer.start();
}
QVariant ReceiverExpansion::value(const char* key) const { return m_metrics?m_metrics->property(key):QVariant(); }
void ReceiverExpansion::setSession(const QVariantMap& session) {
    m_session=session; m_siteStarted=false;
    m_status["siteCapture"]=session.value("siteCapture").toBool();
    if(session.isEmpty()) return;
    QVariantMap safe;
    for(const auto& key:{"uid","name","sourceType","freqMhz","decodeFlag","trunking","host","port","filePath","airspy","siteCapture","siteChannels"}) if(session.contains(key)) safe[key]=session[key];
    QSettings().setValue("receiver/activeSession",safe);
}
QVariantMap ReceiverExpansion::restoredSession() const {
    auto session=QSettings().value("receiver/activeSession").toMap();
    if(m_systems && !session.value("uid").toString().isEmpty()) {
        const auto saved=m_systems->getByUid(session.value("uid").toString());
        if(!saved.isEmpty()) {
            if(session.value("siteCapture").toBool()) {
                auto merged=saved;
                for(const auto& field:{"siteCapture","siteChannels","freqMhz","decodeFlag","trunking"}) merged[field]=session[field];
                session=merged;
            } else session=saved;
        }
    }
    return session;
}
void ReceiverExpansion::setRecovery(bool enabled) {
#ifdef Q_OS_ANDROID
    QJniObject::callStaticMethod<void>("io/github/arancormonk/dsdneo/ReceiverSession","configureRecovery","(Landroid/content/Context;Z)V",QNativeInterface::QAndroidApplication::context().object(),enabled);
#else
    Q_UNUSED(enabled);
#endif
}
QVariantList ReceiverExpansion::devices() const {
#ifdef Q_OS_ANDROID
    const auto json=QJniObject::callStaticObjectMethod(workers,"devices","(Landroid/content/Context;)Ljava/lang/String;",QNativeInterface::QAndroidApplication::context().object()).toString();
    return QJsonDocument::fromJson(json.toUtf8()).array().toVariantList();
#else
    return {};
#endif
}
bool ReceiverExpansion::startWorker(int lane,const QStringList& args,const QString& device) {
#ifdef Q_OS_ANDROID
    const auto json=QJsonDocument(QJsonArray::fromStringList(args)).toJson(QJsonDocument::Compact);
    return QJniObject::callStaticMethod<jboolean>(workers,"start","(Landroid/content/Context;ILjava/lang/String;Ljava/lang/String;)Z",
        QNativeInterface::QAndroidApplication::context().object(),lane,QJniObject::fromString(QString::fromUtf8(json)).object(),QJniObject::fromString(device).object());
#else
    Q_UNUSED(lane); Q_UNUSED(args); Q_UNUSED(device); return false;
#endif
}
QString ReceiverExpansion::startSiteCapture(const QString& frequencies) {
    if(!m_host || !m_host->isRunning() || !QStringList{"usb","rtltcp"}.contains(m_session.value("sourceType").toString()))
        return tr("Start your RTL-SDR or RTL-TCP source first.");
    if(m_session.value("siteCapture").toBool()) return tr("Four-channel reception is already selected.");
    if(m_surveying || m_geo || !m_trial.isEmpty() || value("scannerMode").toBool() || value("rangeScanActive").toBool()) return tr("Stop scanning, surveys and tests first.");
    for(const auto& lane:m_lanes) if(QStringList{"running","starting","stopping"}.contains(lane.toMap().value("state").toString()))
        return tr("Stop additional receivers first.");
    const auto parts=frequencies.split(QRegularExpression("[,;\\s]+"),Qt::SkipEmptyParts);
    if(parts.size()!=4) return tr("Enter four different frequencies in MHz, separated by commas.");
    QVariantList channels; QList<uint32_t> hz;
    for(const auto& part:parts) {
        bool ok=false; const double f=part.toDouble(&ok);
        if(!ok || !std::isfinite(f) || f<24 || f>1766) return tr("Use frequencies between 24 and 1766 MHz.");
        const uint32_t h=uint32_t(std::llround(f*1e6));
        if(hz.contains(h)) return tr("Enter four different frequencies in MHz, separated by commas.");
        hz.append(h); channels.append(h);
    }
    const auto mm=std::minmax_element(hz.cbegin(),hz.cend());
    const uint32_t center=(*mm.first+*mm.second)/2;
    for(const auto h:hz) if(!dsd_channel_fits(center,1536000,h)) return tr("These channels do not fit in one capture. Choose a narrower group.");
    m_siteOriginal=m_session;
    auto session=m_session;
    session["siteCapture"]=true; session["siteChannels"]=channels;
    session["freqMhz"]=QString::number(center/1e6,'f',6); session["bandwidthKhz"]=48;
    session["decodeFlag"]="-fs"; session["trunking"]=false; session["extraArgs"]=QString();
    session.remove("iqCapturePath");
    m_status["siteError"]=QString();
    Q_EMIT restartRequested(session);
    return {};
}
void ReceiverExpansion::stopSiteCapture() {
    for(int i=0;i<DSD_CHANNEL_LANES;++i) stopChannel(i);
    if(m_siteOriginal.isEmpty() && m_systems) m_siteOriginal=m_systems->getByUid(m_session.value("uid").toString());
    if(!m_siteOriginal.isEmpty()) Q_EMIT restartRequested(m_siteOriginal);
    else if(m_host) m_host->stop();
}
void ReceiverExpansion::autoSiteAudio() {
#ifdef Q_OS_ANDROID
    QJniObject::callStaticMethod<void>(workers,"autoSiteAudio","()V");
#endif
}
QString ReceiverExpansion::startChannel(int lane,double mhz,const QString& flag,const QString& device) {
    if(value("rangeScanActive").toBool()) return tr("Stop the range scan before starting another receiver or replay test.");
    if(lane<0 || lane>=DSD_CHANNEL_LANES || !std::isfinite(mhz) || mhz<24 || mhz>1766) return tr("Choose a receiver and a valid frequency.");
    if(!QStringList{"-fa","-f1","-f2","-fs","-fi","-fn","-fA","-fd","-fy","-fz","-fm"}.contains(flag)) return tr("Choose a supported mode.");
    if(!m_args || !m_trial.isEmpty() || !m_trials.isEmpty()) return tr("Stop the lab before starting another receiver.");
    QVariantMap system=m_session;
    system["freqMhz"]=QString::number(mhz,'f',6); system["decodeFlag"]=flag; system["trunking"]=false;
    system.remove("iqCapturePath"); system["extraArgs"]=QString(); system["bandwidthKhz"]=48; system["biasTee"]=0;
    system["workerSession"]=true;
    system.remove("siteCapture"); system.remove("siteChannels");
    if(device.isEmpty()) {
        if(!tuningAllowed() || m_surveying) return tr("Start a fixed RTL-SDR channel at 48 kHz bandwidth first. Stop scanning and trunk following.");
        dsd_channel_info info{}; dsd_channel_get(lane,&info);
        if(info.source_age_ms>2000 || !dsd_channel_fits(info.source_hz,info.sample_rate,uint32_t(std::llround(mhz*1e6))))
            return tr("This channel is outside the shared capture window. Tune the main receiver closer.");
        const int port=dsd_channel_open(lane); if(port<0) return tr("The shared I/Q receiver could not start.");
        system["sourceType"]="rtltcp"; system["host"]="127.0.0.1"; system["port"]=port; system["ppm"]="0";
    } else {
        // A receiver already held by the main process cannot be opened a second time.
        system["sourceType"]="usb";
    }
    SessionArgsError error{};
    auto args=m_args->workerArgs(system,&error)+CallLibrary::recordingArgs(QString("worker%1").arg(lane));
    if(device.isEmpty()) args<<"--xerax-shared-rate=192000";
    if(dsd_dmr_ras_enabled()) args<<"--xerax-ras";
    if(error!=SessionArgsError::None || !startWorker(lane,args,device)) { dsd_channel_close(lane); return tr("Could not start the additional receiver. Check its configuration."); }
    return {};
}
void ReceiverExpansion::stopChannel(int lane) {
#ifdef Q_OS_ANDROID
    QJniObject::callStaticMethod<void>(workers,"stop","(I)V",lane);
#endif
    dsd_channel_close(lane);
}
void ReceiverExpansion::listen(int lane) {
#ifdef Q_OS_ANDROID
    QJniObject::callStaticMethod<void>(workers,"listen","(I)V",lane);
#else
    Q_UNUSED(lane);
#endif
}
bool ReceiverExpansion::requestDevice(const QString& id) {
#ifdef Q_OS_ANDROID
    return QJniObject::callStaticMethod<jboolean>(workers,"requestDevice","(Landroid/content/Context;Ljava/lang/String;)Z",
        QNativeInterface::QAndroidApplication::context().object(),QJniObject::fromString(id).object());
#else
    Q_UNUSED(id); return false;
#endif
}
QString ReceiverExpansion::startDual(const QString& device) {
    if(!m_host || !m_host->isRunning() || !m_session.value("trunking").toBool() || !value("siteProtocol").toString().contains("P25",Qt::CaseInsensitive))
        return tr("Start a saved P25 trunked system on the main receiver first.");
    if(device.isEmpty() || !m_args) return tr("Choose the second USB RTL-SDR receiver.");
    auto system=m_session; system["sourceType"]="usb"; system["trunking"]=false; system["decodeFlag"]="-f1";
    system["workerSession"]=true;
    system.remove("siteCapture"); system.remove("siteChannels"); system["bandwidthKhz"]=48; system["extraArgs"]=QString(); system.remove("iqCapturePath");
    SessionArgsError error{}; const auto args=m_args->workerArgs(system,&error)+CallLibrary::recordingArgs("voice");
    if(error!=SessionArgsError::None) return session_args_error_text(error);
#ifdef Q_OS_ANDROID
    const auto json=QJsonDocument(QJsonArray::fromStringList(args)).toJson(QJsonDocument::Compact);
    if(QJniObject::callStaticMethod<jboolean>(workers,"armDual","(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;)Z",
        QNativeInterface::QAndroidApplication::context().object(),QJniObject::fromString(QString::fromUtf8(json)).object(),QJniObject::fromString(device).object())) { listen(0); return {}; }
#endif
    return tr("Could not arm the voice receiver. Grant access to a different RTL-SDR and stop other workers.");
}
void ReceiverExpansion::stopDual() {
#ifdef Q_OS_ANDROID
    QJniObject::callStaticMethod<void>(workers,"disarmDual","()V");
#endif
    dsd_dual_enable(0);
}
void ReceiverExpansion::setEqualizer(bool enabled) { dsd_equalizer_enable(enabled); m_status["equalizer"]=enabled; Q_EMIT changed(); }
void ReceiverExpansion::setRasReception(bool enabled) { dsd_dmr_ras_enable(enabled); QSettings().setValue("receiver/rasReception",enabled); m_status["rasReception"]=enabled; Q_EMIT changed(); }
void ReceiverExpansion::setNxdnSearch(bool enabled) {
    dsd_nxdn_search_enable(enabled); m_status["nxdnSearch"]=enabled;
    m_status["nxdnSearchStatus"]=0; m_status["nxdnSearchKey"]=-1; Q_EMIT changed();
}
bool ReceiverExpansion::setTwoTone(double a,double b,int aMs,int bMs) { return dsd_signaling_two_tone(a,b,aMs,bMs)!=0; }
QString ReceiverExpansion::runLab() {
    if(value("rangeScanActive").toBool()) return tr("Stop the range scan before starting another receiver or replay test.");
    if(!m_trial.isEmpty() || !m_trials.isEmpty()) return tr("A replay test is already running.");
    for(const auto& lane:m_lanes) if(lane.toMap().value("state").toString()=="running") return tr("Stop additional receivers before running the lab.");
    m_status["labRunId"]=QUuid::createUuid().toString(QUuid::WithoutBraces);
    const QString dir=QStandardPaths::writableLocation(QStandardPaths::AppDataLocation)+"/iq-lab";
    QDir().mkpath(dir);
    const auto manifest=readJson("assets:/iq-lab/manifest.json");
    if(manifest.isEmpty()) return tr("The I/Q test fixtures are unavailable.");
    for(const auto& v:manifest.value("tests").toList()) {
        auto test=v.toMap(); const QString stem=test.value("fixture").toString();
        for(const auto& suffix:{QString(".iq"),QString(".iq.json")}) {
            const auto target=dir+"/"+stem+suffix;
            QFile fixture(target);
            const auto hash=manifest.value("sha256").toMap().value(stem+suffix).toString().toLatin1();
            auto valid=[&]() { if(!fixture.open(QIODevice::ReadOnly)) return false; const auto actual=QCryptographicHash::hash(fixture.readAll(),QCryptographicHash::Sha256).toHex(); fixture.close(); return actual==hash; };
            if(!valid()) {
                QFile::remove(target);
                if(!QFile::copy("assets:/iq-lab/"+stem+suffix,target) || !valid()) { m_trials.clear(); return tr("Could not verify a test fixture."); }
            }
        }
        test["metadata"]=dir+"/"+stem+".iq.json"; m_trials.append(test);
    }
    m_status["labRunning"]=true; nextTrial(); return {};
}
QString ReceiverExpansion::reprocess(const QString& metadata,const QString& flag) {
    if(value("rangeScanActive").toBool()) return tr("Stop the range scan before starting another receiver or replay test.");
    if(!m_trial.isEmpty() || !m_trials.isEmpty()) return tr("A replay test is already running.");
    auto meta=readJson(metadata);
    if(meta.value("format").toString()!="dsd-neo-iq" || meta.value("contains_retunes").toBool()) return tr("Choose a fixed-frequency native I/Q capture.");
    if(!QStringList{"-f1","-f2","-fs","-fi","-fn","-fa","-fA"}.contains(flag)) return tr("Choose a supported mode.");
    m_status["labRunId"]=QUuid::createUuid().toString(QUuid::WithoutBraces);
    // Each run changes the actual demodulator. The same samples remain available for comparison.
    QStringList mods=flag=="-f1"||flag=="-f2"?QStringList{"-mc","-mq"}:QStringList{QString()};
    for(const auto& mod:mods) {
        for(const auto offset:{0,-250,250}) m_trials.append(QVariantMap{{"name",tr("Saved I/Q %1 %2 · offset %3 Hz").arg(flag,mod).arg(offset)},
            {"metadata",metadata},{"flag",flag},{"mod",mod},{"offset",offset},{"exploratory",true}});
        for(const auto bandwidth:{6000,12000}) m_trials.append(QVariantMap{{"name",tr("Saved I/Q %1 %2 · filter %3 Hz").arg(flag,mod).arg(bandwidth)},
            {"metadata",metadata},{"flag",flag},{"mod",mod},{"bandwidth",bandwidth},{"exploratory",true}});
        if(mod=="-mq") m_trials.append(QVariantMap{{"name",tr("Saved I/Q · CQPSK equalizer")},{"metadata",metadata},{"flag",flag},{"mod",mod},{"equalizer",true},{"exploratory",true}});
    }
    m_status["labRunning"]=true; nextTrial(); return {};
}
void ReceiverExpansion::nextTrial() {
    if(m_trials.isEmpty()) { m_trial.clear(); m_status["labRunning"]=false; Q_EMIT changed(); return; }
    m_trial=m_trials.takeFirst().toMap(); m_terminalAt=0;
    m_trial["runId"]=m_status.value("labRunId");
    QStringList args{"--frontend","none","--iq-replay",m_trial.value("metadata").toString(),"--iq-replay-rate","fast","-o","null",m_trial.value("flag").toString()};
    if(!m_trial.value("mod").toString().isEmpty()) args<<m_trial.value("mod").toString();
    if(m_trial.value("equalizer").toBool()) args<<"--xerax-equalizer";
    if(m_trial.value("relaxedCrc").toBool()) args<<"-F";
    if(m_trial.value("ras").toBool()) args<<"--xerax-ras";
    if(m_trial.contains("offset")) args<<QString("--xerax-offset=%1").arg(m_trial.value("offset").toInt());
    if(m_trial.contains("bandwidth")) args<<QString("--xerax-bandwidth=%1").arg(m_trial.value("bandwidth").toInt());
    m_status["trial"]=m_trial.value("name");
    if(!startWorker(0,args)) { m_status["trial"]=tr("Could not start the replay worker."); m_trials.clear(); m_trial.clear(); m_status["labRunning"]=false; }
    Q_EMIT changed();
}
void ReceiverExpansion::stopTrials() { m_trials.clear(); m_trial.clear(); m_status["labRunning"]=false; stopChannel(0); Q_EMIT changed(); }
QString ReceiverExpansion::exportReports(const QString& url) { return writeJson(url,QVariantMap{{"schema",2},{"tests",m_reports},{"receptionSamples",m_receptionReports},{"hardwareAcceptance",false}}); }
xerax::ReceptionReading ReceiverExpansion::receptionReading() const {
    return {m_clock.elapsed(),value("ccFecOk").toULongLong(),value("ccFecErr").toULongLong(),
        value("centerFreqHz").toDouble(),value("snrDb").toDouble(),m_host && m_host->isRunning(),value("snrValid").toBool()};
}
QString ReceiverExpansion::startReceptionSample(const QString& label) {
    if(m_reception.active) return tr("A reception sample is already running.");
    if(!tuningAllowed() || m_surveying || m_geo || value("scannerMode").toBool()) return tr("Start a fixed channel and stop scanning before measuring reception.");
    if(label.trimmed().isEmpty() || label.size()>80) return tr("Name this setup using 1–80 characters.");
    m_receptionLabel=label.trimmed(); m_reception.begin(receptionReading());
    m_status["sampleRunId"]=QUuid::createUuid().toString(QUuid::WithoutBraces);
    m_status["receptionRunning"]=true; m_status["receptionSeconds"]=0; Q_EMIT changed(); return {};
}
void ReceiverExpansion::cancelReceptionSample() { m_reception.active=false; m_status["receptionRunning"]=false; Q_EMIT changed(); }
void ReceiverExpansion::locate(bool live) {
    m_gps=live;
    if(!live) { m_lat=33.7206; m_lon=-116.2156; m_accuracy=0; m_fix=0; m_status["location"]=tr("Indio · %1 miles").arg(m_radius); rankSites(); Q_EMIT changed(); return; }
    if(m_host && !m_locationRequest) { m_locationRequest=QDateTime::currentMSecsSinceEpoch(); m_host->requestCurrentLocation(m_locationRequest); m_lastLocate=m_clock.elapsed(); }
}
void ReceiverExpansion::setRadius(double miles) { if(!std::isfinite(miles) || miles<1 || miles>500) return; m_radius=miles; rankSites(); Q_EMIT changed(); }
void ReceiverExpansion::setGeoScan(bool enabled) { m_geo=enabled; m_status["geoScanning"]=enabled; m_lastSwitch=0; Q_EMIT changed(); }
void ReceiverExpansion::rankSites() {
    m_nearby.clear(); if(!m_systems) return;
    for(int i=0;i<m_systems->count();++i) {
        const double miles=m_systems->distanceKm(i,m_lat,m_lon)/1.609344;
        if(miles<0 || miles>m_radius+m_accuracy/1609.344) continue;
        auto row=m_systems->get(i); row["distanceMi"]=miles;
        row["eligible"]=miles+m_accuracy/1609.344<=m_radius;
        row["uncertain"]=!row.value("eligible").toBool(); m_nearby.append(row);
    }
    std::sort(m_nearby.begin(),m_nearby.end(),[](const QVariant&a,const QVariant&b){return a.toMap().value("distanceMi").toDouble()<b.toMap().value("distanceMi").toDouble();});
}
bool ReceiverExpansion::tuningAllowed() const {
    return m_host && m_host->isRunning() && value("radioInput").toBool() && !value("tunerControlled").toBool() && !value("rangeScanActive").toBool()
        && !value("heldTg").toUInt() && !value("scanHold").toBool();
}
bool ReceiverExpansion::tune(double hz) {
    bool ok=false; return m_commands && QMetaObject::invokeMethod(m_commands,"manualTuneHz",Qt::DirectConnection,Q_RETURN_ARG(bool,ok),Q_ARG(unsigned int,static_cast<unsigned int>(hz))) && ok;
}
QString ReceiverExpansion::startSurvey(double first,double last,double step,int dwell) {
    if(!tuningAllowed()) return tr("Start a fixed radio channel and release any hold before surveying.");
    if(!std::isfinite(first)||!std::isfinite(last)||!std::isfinite(step)||first<24||last>1766||last<first||step<6.25||step>1000||dwell<2||dwell>30 || (last-first)*1000/step>499)
        return tr("Use 24–1766 MHz, 6.25–1000 kHz steps, 2–30 seconds dwell and at most 500 channels.");
    for(const auto& lane:m_lanes) if(lane.toMap().value("state").toString()=="running") return tr("Stop additional receivers before moving the main tuner.");
    m_status["surveyError"]=QString(); m_surveyWait=0; m_survey.clear();
    for(double hz=first*1e6;hz<=last*1e6+0.5;hz+=step*1000) m_survey.append(QVariantMap{{"frequency",hz},{"samples",0},{"busy",0},{"ok",0},{"protocol",QString()},{"occupancy",0},{"lastActive",QString()}});
    m_originalFrequency=value("centerFreqHz").toDouble(); m_surveyIndex=0; m_surveyTicks=0; m_dwell=dwell; m_surveying=true; m_status["surveying"]=true;
    m_good=value("ccFecOk").toULongLong(); tune(first*1e6); Q_EMIT changed(); return {};
}
void ReceiverExpansion::stopSurvey() { const bool was=m_surveying; m_surveying=false; m_status["surveying"]=false; if(was && tuningAllowed()) tune(m_originalFrequency); Q_EMIT changed(); }
bool ReceiverExpansion::tuneSurvey(int index) { if(index<0||index>=m_survey.size()) return false; stopSurvey(); return tuningAllowed() && tune(m_survey[index].toMap().value("frequency").toDouble()); }
bool ReceiverExpansion::saveSurvey(int index) {
    if(!m_systems||index<0||index>=m_survey.size()) return false;
    const auto row=m_survey[index].toMap(); auto system=m_session;
    system.remove("uid"); system.remove("iqCapturePath"); system.remove("decryptionProfileUid"); system.remove("encKeyValue");
    system["name"]=tr("Survey %1 MHz").arg(row.value("frequency").toDouble()/1e6,0,'f',6);
    system["freqMhz"]=QString::number(row.value("frequency").toDouble()/1e6,'f',6); system["trunking"]=false;
    return m_systems->add(system);
}
void ReceiverExpansion::poll() {
#ifdef Q_OS_ANDROID
    const auto service=QJniObject::callStaticObjectMethod("io/github/arancormonk/dsdneo/ReceiverSession","status","(Landroid/content/Context;)Ljava/lang/String;",QNativeInterface::QAndroidApplication::context().object()).toString();
    const auto serviceState=QJsonDocument::fromJson(service.toUtf8()).object().toVariantMap();
    for(auto it=serviceState.cbegin();it!=serviceState.cend();++it) m_status[it.key()]=it.value();
    const auto restored=serviceState.value("captureRestored").toLongLong();
    if(m_captureRestored>=0 && restored>m_captureRestored) Q_EMIT captureRestored();
    m_captureRestored=restored;
    const auto json=QJniObject::callStaticObjectMethod(workers,"status","(Landroid/content/Context;)Ljava/lang/String;",QNativeInterface::QAndroidApplication::context().object()).toString();
    const auto state=QJsonDocument::fromJson(json.toUtf8()).object(); m_lanes=state.value("lanes").toArray().toVariantList();
    m_status["thermalPaused"]=state.value("thermalPaused").toBool(); m_status["audible"]=state.value("audible").toInt(-1);
    m_status["siteAuto"]=state.value("siteAuto").toBool();
    m_status["dual"]=state.value("dual").toBool(); m_status["voiceFrequency"]=state.value("voiceFrequency").toDouble(); m_status["voiceTarget"]=state.value("voiceTarget").toDouble();
    m_status["voicePending"]=state.value("voicePending").toBool(); m_status["tuneLatencyMs"]=state.value("tuneLatencyMs").toDouble();
#endif
    const bool site=m_session.value("siteCapture").toBool() && m_host && m_host->isRunning();
    m_status["siteCapture"]=site;
    if(site && !m_siteStarted) {
        // Activity recreation must reattach to existing workers, never reopen
        // their loopback sockets. Native channel ownership survives the UI.
        for(int i=0;i<DSD_CHANNEL_LANES;++i) {
            dsd_channel_info lane{}; dsd_channel_get(i,&lane);
            if(lane.port) { m_siteStarted=true; break; }
        }
    }
    if(site && !m_siteStarted) {
        dsd_channel_info input{}; dsd_channel_get(-1,&input);
        if(input.source_age_ms<1500 && input.sample_rate) {
            m_siteStarted=true;
            const auto channels=m_session.value("siteChannels").toList();
            if(channels.size()!=4 || input.sample_rate!=1536000 || std::abs(double(input.source_hz)-m_session.value("freqMhz").toDouble()*1e6)>1000)
                m_status["siteError"]=tr("Capture center or rate differs from the plan. Stop four-channel mode and check the source.");
            else for(int i=0;i<channels.size();++i) {
                const auto error=startChannel(i,channels[i].toDouble()/1e6,"-fs");
                if(!error.isEmpty()) { m_status["siteError"]=error; break; }
            }
            if(!m_status.value("siteError").toString().isEmpty()) for(int i=0;i<DSD_CHANNEL_LANES;++i) stopChannel(i);
        }
    }
    m_status["equalizer"]=dsd_equalizer_enabled()!=0; m_status["equalizerError"]=dsd_equalizer_error();
    m_status["rasReception"]=dsd_dmr_ras_enabled()!=0;
    dsd_nxdn_search_status nxdn{}; dsd_nxdn_search_get(&nxdn);
    m_status["nxdnSearch"]=nxdn.enabled!=0; m_status["nxdnSearchStatus"]=nxdn.status;
    m_status["nxdnSearchKey"]=nxdn.key; m_status["nxdnSearchFrames"]=nxdn.frames;
    dsd_dmr_evidence dmr{}; dsd_dmr_evidence_get(&dmr);
    m_status["dmrChecked"]=QVariant::fromValue<qulonglong>(dmr.checked[0]+dmr.checked[1]);
    m_status["dmrRas"]=QVariant::fromValue<qulonglong>(dmr.suspected_ras[0]+dmr.suspected_ras[1]);
    m_status["dmrRejected"]=QVariant::fromValue<qulonglong>(dmr.rejected[0]+dmr.rejected[1]);
    m_status["decryption"]=value("decryptionSlots");
    if(m_reception.active) {
        const bool complete=m_reception.add(receptionReading());
        m_status["receptionSeconds"]=static_cast<int>((m_reception.last.ms-m_reception.first.ms)/1000);
        if(complete) {
            QVariantMap report{{"name",m_receptionLabel},{"runId",m_status.value("sampleRunId")},{"at",QDateTime::currentDateTimeUtc().toString(Qt::ISODate)},
                {"frequency",m_reception.first.frequency},{"durationMs",QVariant::fromValue<qlonglong>(m_reception.last.ms-m_reception.first.ms)},
                {"valid",m_reception.valid},{"fecAccepted",QVariant::fromValue<qulonglong>(m_reception.accepted())},
                {"fecRejected",QVariant::fromValue<qulonglong>(m_reception.rejected())},{"snrSamples",m_reception.samples}};
            if(m_reception.samples) report["meanSnrDb"]=m_reception.snrSum/m_reception.samples;
            m_receptionReports.prepend(report); while(m_receptionReports.size()>30) m_receptionReports.removeLast();
            json_store_save_array("reception_reports.json",QJsonArray::fromVariantList(m_receptionReports));
            m_status["receptionRunning"]=false;
        }
    }
    dsd_signal_event event{};
    while(dsd_signaling_pop(&event)) {
        m_status["signalSerial"]=QVariant::fromValue<qulonglong>(event.serial);
        m_status["signaling"]=QString::fromUtf8(event.protocol)+" · "+QString::fromUtf8(event.detail);
        auto events=m_status.value("signals").toList(); events.prepend(QVariantMap{{"text",m_status.value("signaling")},{"when",QDateTime::currentDateTime().toString("hh:mm:ss")},{"frequency",event.frequency}});
        while(events.size()>100) events.removeLast(); m_status["signals"]=events;
    }
    for(int i=0;i<m_lanes.size() && i<DSD_CHANNEL_LANES;++i) {
        auto row=m_lanes[i].toMap(); dsd_channel_info info{}; dsd_channel_get(i,&info);
        row["dropped"]=QVariant::fromValue<qulonglong>(info.dropped); row["bytes"]=QVariant::fromValue<qulonglong>(info.bytes); row["captureRate"]=info.sample_rate;
        row["outputRate"]=info.output_rate;
        if(m_session.value("siteCapture").toBool()) row["plannedFrequency"]=m_session.value("siteChannels").toList().value(i);
        if(QStringList{"failed","complete","stopped"}.contains(row.value("state").toString()) && info.port) dsd_channel_close(i);
        if(info.error) row["error"]=info.error==1?tr("Receiver fell behind; restart this channel."):info.error==2?tr("Capture rates differ. Use 48 kHz bandwidth on both receivers."):info.error==3?tr("Channel is outside the shared bandwidth."):tr("Main receiver moved; restart this channel.");
        m_lanes[i]=row;
    }
    if(!m_trial.isEmpty() && !m_lanes.isEmpty()) {
        const auto lane=m_lanes[0].toMap(); const auto phase=lane.value("state").toString();
        if(phase=="running" || phase=="starting") m_terminalAt=0;
        if(phase=="complete" || phase=="failed" || phase=="stopped") {
            if(!m_terminalAt) m_terminalAt=m_clock.elapsed();
            if(m_clock.elapsed()-m_terminalAt>=2000) {
                auto result=m_trial; result.remove("metadata");
                const QString evidence=lane.value("evidence").toString();
                const auto expected=m_trial.value("expect").toString(), reject=m_trial.value("reject").toString();
                const bool passed=phase=="complete" && !expected.isEmpty() && QRegularExpression(expected).match(evidence).hasMatch()
                    && (reject.isEmpty() || !QRegularExpression(reject).match(evidence).hasMatch());
                result["result"]=m_trial.value("exploratory").toBool()?QStringLiteral("Comparison only"):passed?QStringLiteral("Passed"):QStringLiteral("Failed");
                result["passed"]=passed; result["completed"]=phase=="complete"; result["at"]=QDateTime::currentDateTimeUtc().toString(Qt::ISODate);
                const auto metric=QRegularExpression("XeraX P25 FEC: accepted=(\\d+) rejected=(\\d+); voice_accepted=(\\d+) voice_rejected=(\\d+)").match(evidence);
                result["fecAccepted"]=metric.captured(1).toUInt()+metric.captured(3).toUInt();
                result["fecRejected"]=metric.captured(2).toUInt()+metric.captured(4).toUInt();
                result["pcmBytes"]=lane.value("pcmBytes");
                result["evidence"]=evidence; result["elapsedMs"]=lane.value("elapsedMs");
                m_reports.prepend(result); while(m_reports.size()>100) m_reports.removeLast();
                json_store_save_array("lab_reports.json",QJsonArray::fromVariantList(m_reports)); nextTrial();
            }
        }
    }
    const bool interactive=QGuiApplication::applicationState()==Qt::ApplicationActive;
    if(m_surveying && !interactive) { stopSurvey(); return; }
    if(interactive && m_gps && !m_locationRequest && m_clock.elapsed()-m_lastLocate>=60000) locate(true);
    bool extraRunning=false;
    for(const auto& lane:m_lanes) { const auto phase=lane.toMap().value("state").toString(); extraRunning|=phase=="running" || phase=="starting"; }
    if(interactive && m_geo && !extraRunning && !m_surveying && m_host && m_host->isRunning() && value("slot1CallState").toInt()!=2 && value("slot2CallState").toInt()!=2
        && !value("heldTg").toUInt() && !value("scanHold").toBool() && m_clock.elapsed()-m_lastSwitch>30000
        && (!m_gps || m_fix>0 && QDateTime::currentMSecsSinceEpoch()-m_fix<120000)) {
        // Round-robin eligible sites in distance order, with a 30-second dwell.
        // The uncertainty margin and fresh-fix gate exclude ambiguous boundary sites.
        QStringList eligible;
        for(const auto& site:m_nearby) { const auto row=site.toMap(); if(row.value("eligible").toBool()) eligible<<row.value("uid").toString(); }
        if(!eligible.isEmpty()) {
            const int current=eligible.indexOf(m_session.value("uid").toString());
            const auto uid=eligible[(current+1)%eligible.size()];
            m_lastSwitch=m_clock.elapsed();
            if(uid!=m_session.value("uid").toString()) { m_lastSite=uid; Q_EMIT selectSite(uid); }
        }
    }
    if(m_surveying) {
        if(!tuningAllowed() || m_status.value("thermalPaused").toBool()) { stopSurvey(); return; }
        auto row=m_survey[m_surveyIndex].toMap();
        if(++m_surveyWait>m_dwell+10) { stopSurvey(); m_status["surveyError"]=tr("Survey stopped: the tuner did not reach the requested frequency."); Q_EMIT changed(); return; }
        const double target=row.value("frequency").toDouble(); const auto good=value("ccFecOk").toULongLong();
        if(std::abs(value("centerFreqHz").toDouble()-target)<100 && m_surveyTicks++>0) {
            const bool busy=value("snrValid").toBool() && value("snrDb").toDouble()>=6;
            row["samples"]=row.value("samples").toInt()+1; row["busy"]=row.value("busy").toInt()+int(busy);
            row["occupancy"]=100.0*row.value("busy").toInt()/row.value("samples").toInt();
            if(busy) row["lastActive"]=QDateTime::currentDateTime().toString("hh:mm:ss");
            if(good>m_good && value("syncedHere").toBool()) { row["ok"]=row.value("ok").toInt()+int(good-m_good); row["protocol"]=value("siteProtocol"); }
            m_survey[m_surveyIndex]=row;
        }
        m_good=good;
        if(m_surveyTicks>=m_dwell) { m_surveyWait=0; m_surveyTicks=0; m_surveyIndex=(m_surveyIndex+1)%m_survey.size(); tune(m_survey[m_surveyIndex].toMap().value("frequency").toDouble()); }
    }
    Q_EMIT changed();
}
}
