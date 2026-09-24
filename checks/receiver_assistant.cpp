// SPDX-License-Identifier: GPL-3.0-or-later
#include "receiver_assistant.h"
#include "saved_systems_model.h"
#include "app_language.h"
#include <dsd-neo/platform/receiver_filter.h>
#include <dsd-neo/platform/analog_tones.h>
#include <dsd-neo/platform/audio_replay.h>
#include <QCoreApplication>
#include <QQmlPropertyMap>
#include <QQmlEngine>
#include <QSettings>
#include <QStandardPaths>
#include <QUuid>
#include <QTemporaryDir>
#include <QFile>
#include <QDir>
#include <QJsonDocument>
#include <cstdio>
#include <cmath>
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"FAILED line %d: %s\n",__LINE__,#x); return 1; } } while (0)
class Commands : public QObject {
    Q_OBJECT
public:
    QQmlPropertyMap* metrics;
    QList<int> requested;
    Q_INVOKABLE bool setTunerGain(int gain) { requested << gain; metrics->insert("tunerGainDb", gain); return true; }
};
class Assistant : public dsd_qt::ReceiverAssistant {
public: qint64 clock = 1000;
protected: qint64 nowMs() const override { return clock; }
};
int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    QCoreApplication::setOrganizationName("XeraXChecks");
    QCoreApplication::setApplicationName("assistant-" + QUuid::createUuid().toString(QUuid::WithoutBraces));
    QStandardPaths::setTestModeEnabled(true);
    QTemporaryDir temp; CHECK(temp.isValid());
    QQmlPropertyMap metrics, host, tools;
    Commands commands; commands.metrics = &metrics;
    host.insert("running", true); host.insert("sessionActive", true);
    tools.insert("health", QVariantMap{{"inputValid", true}, {"clipPct", 0.0}, {"rmsDbfs", -20}});
    const QVariantMap defaults{{"centerFreqHz", 155250000}, {"radioInput", true}, {"tunerControlled", false}, {"airspy", QVariantMap{}},
        {"slot1CallState", 0}, {"slot2CallState", 0}, {"ccFecOk", 0}, {"ccFecErr", 0}, {"tunerGainDb", 20}, {"syncedHere", true},
        {"syncLabel", "DMR"}, {"snrValid", true}, {"snrDb", 15}, {"decodeMode", 4}};
    for (auto i = defaults.begin(); i != defaults.end(); ++i) metrics.insert(i.key(), i.value());
    dsd_qt::SavedSystemsModel systems;
    Assistant assistant; assistant.configure(&metrics, &commands, &host, &tools, &systems);
    assistant.poll();
    CHECK(assistant.status()["framePercent"].toDouble() < 0);
    tools.insert("health",QVariantMap{{"iqObserved",true},{"iqFresh",false}});
    assistant.poll(); CHECK(assistant.status()["audioText"].toString().startsWith("Radio samples stopped"));
    tools.insert("health",QVariantMap{{"iqObserved",true},{"iqFresh",true}});
    for(int i=0;i<9;++i) assistant.poll();
    CHECK(assistant.status()["audioText"].toString().startsWith("Digital sync is present"));
    metrics.insert("syncedHere",false); assistant.poll();
    CHECK(assistant.status()["audioText"].toString().startsWith("Radio samples are arriving"));
    metrics.insert("slot1CallState",2); assistant.poll();
    CHECK(assistant.status()["audioText"].toString().startsWith("A call is active"));
    metrics.insert("slot1CallState",0); metrics.insert("syncedHere",true);
    tools.insert("health",QVariantMap{{"inputValid",true},{"clipPct",0.0},{"rmsDbfs",-20}});
    metrics.insert("centerFreqHz",155251000); assistant.poll();
    auto tick = [&](int good, int bad) { metrics.insert("ccFecOk", metrics.value("ccFecOk").toInt()+good); metrics.insert("ccFecErr", metrics.value("ccFecErr").toInt()+bad); assistant.clock += 1000; assistant.poll(); };
    tick(9, 1); CHECK(std::abs(assistant.status()["framePercent"].toDouble()-90) < 0.01);
    metrics.insert("syncedHere", false); tick(0,0); CHECK(assistant.status()["syncLosses"].toInt()==1);
    metrics.insert("centerFreqHz",155500000); tick(0,0); CHECK(assistant.status()["syncLosses"].toInt()==0);
    CHECK(assistant.status()["validFrames"].toInt()==0);
    metrics.insert("ccFecOk", 0); metrics.insert("ccFecErr", 0); assistant.poll(); CHECK(assistant.status()["validFrames"].toInt()==0);
    CHECK(dsd_qt::ReceiverAssistant::score(0,0,30,true,0,true,false) == -1);
    CHECK(dsd_qt::ReceiverAssistant::score(9,1,0,false,1,true,false) == 70);
    CHECK(dsd_qt::ReceiverAssistant::score(0,0,20,true,0,true,true) == 60);
    assistant.setAutoGain(true);
    for(int i=0;i<12;++i) tick(9,1);
    CHECK(commands.requested.size()==1 && commands.requested.last()==24);
    metrics.insert("slot1CallState",2);
    for(int i=0;i<20;++i) tick(0,10);
    CHECK(commands.requested.size()==1); // No tuning during active calls.
    metrics.insert("slot1CallState",0);
    for(int i=0;i<12;++i) tick(1,9);
    CHECK(commands.requested.last()==20); // Worse trial is rolled back.
    assistant.setAutoGain(false); assistant.setAutoGain(true);
    for(int i=0;i<12;++i) tick(5,5);
    CHECK(commands.requested.last()==24);
    for(int i=0;i<12;++i) tick(10,0);
    CHECK(metrics.value("tunerGainDb").toInt()==24);
    CHECK(assistant.status()["gainText"].toString().startsWith("Kept"));
    assistant.setAutoGain(false);
    for (int i = 0; i < 3; ++i) CHECK(systems.add({{"name", QString("Site %1").arg(i)}, {"sourceType", "usb"},
        {"freqMhz", QString::number(155.5 + i * 0.025, 'f', 6)}, {"decodeFlag", "-ft"}, {"trunking", true},
        {"rrSid", 55}, {"rrSiteId", i+1}, {"avoidSite", i==1}}));
    const auto origin = systems.get(0)["uid"].toString(), candidate = systems.get(2)["uid"].toString();
    QStringList switches;
    auto connection = QObject::connect(&assistant, &Assistant::switchSite, [&](const QString& uid) {
        switches << uid; assistant.setSession(uid, false);
        metrics.insert("centerFreqHz", std::round(systems.getByUid(uid)["freqMhz"].toDouble()*1e6));
    });
    assistant.setSession(origin, false); assistant.setRoaming(true); assistant.clock += 31000;
    metrics.insert("syncedHere",false); metrics.insert("slot1CallState",2);
    for(int i=0;i<40;++i)tick(0,10);
    CHECK(switches.isEmpty());
    metrics.insert("slot1CallState",0); metrics.insert("heldTg",123);
    for(int i=0;i<40;++i)tick(0,10);
    CHECK(switches.isEmpty()); metrics.insert("heldTg",0);
    for(int i=0;i<20;++i)tick(0,10);
    CHECK(switches.size()==1 && switches.last()==candidate); // Avoided site was skipped.
    for(int i=0;i<36;++i)tick(0,10);
    CHECK(switches.size()==2 && switches.last()==origin); // Worse site rolls back.
    for(int i=0;i<40;++i)tick(0,10);
    CHECK(switches.size()==2); // Five-minute cooldown survives the rollback restart.
    assistant.clock += 301000;
    for(int i=0;i<20;++i)tick(0,10);
    CHECK(switches.size()==3 && switches.last()==candidate);
    metrics.insert("syncedHere",true);
    for(int i=0;i<36;++i)tick(10,0);
    CHECK(switches.size()==3 && assistant.status()["siteText"].toString().startsWith("Kept"));
    assistant.setRoaming(false); assistant.setSession("",false); QObject::disconnect(connection);
    while(systems.count())systems.remove(0);
    metrics.insert("centerFreqHz",155500000); assistant.poll();
    QVariantMap rule{{"ctcss",0.0},{"dcs",-1},{"inverse",false},{"color",3},{"slot",2},{"talkgroup",123}};
    CHECK(assistant.saveFilter(155500000,rule).isEmpty());
    CHECK(dsd_receiver_digital_allowed(155500000,1,3,2,123));
    CHECK(!dsd_receiver_digital_allowed(155500000,1,-1,2,123));
    CHECK(!dsd_receiver_digital_allowed(155500000,1,4,2,123));
    CHECK(!dsd_receiver_digital_allowed(155500000,1,3,1,123));
    CHECK(!dsd_receiver_digital_allowed(155500000,0,-1,1,124));
    CHECK(dsd_receiver_digital_allowed(155500001,1,4,1,1)); // Exact frequency only.
    rule["color"]=16; CHECK(!assistant.saveFilter(155500000,rule).isEmpty());
    rule["color"]=3; rule["ctcss"]=100.0; CHECK(assistant.saveFilter(155500000,rule).isEmpty());
    dsd_analog_tones_reset(); CHECK(!dsd_receiver_analog_allowed(155500000));
    std::vector<float> tone(48000*3); for(size_t i=0;i<tone.size();++i) tone[i]=float(0.3*std::sin(2*3.141592653589793*100*i/48000));
    for(size_t i=0;i<tone.size();i+=4800) dsd_analog_tones_feed(tone.data()+i,4800,48000,1,1);
    CHECK(dsd_receiver_analog_allowed(155500000));
    rule["ctcss"]=123.0; CHECK(assistant.saveFilter(155500000,rule).isEmpty()); CHECK(!dsd_receiver_analog_allowed(155500000));
    assistant.clearFilter(155500000); CHECK(dsd_receiver_analog_allowed(155500000));
    assistant.setNotebook(true); metrics.insert("syncedHere",true);
    for(int i=0;i<4;++i) tick(10,0);
    CHECK(!assistant.discoveries().isEmpty());
    CHECK(assistant.discoveries()[0].toMap()["confirmed"].toBool());
    CHECK(assistant.saveDiscovery(0)); CHECK(systems.count()==1);
    CHECK(assistant.exportDiscoveries(temp.filePath("notebook.json")).isEmpty());
    QFile notes(temp.filePath("notebook.json")); CHECK(notes.open(QIODevice::ReadOnly)); CHECK(!QJsonDocument::fromJson(notes.readAll()).isNull());
    metrics.insert("syncedHere",false); for(int i=0;i<4;++i)tick(0,0);
    CHECK(!assistant.discoveries()[0].toMap()["confirmed"].toBool());
    CHECK(assistant.prepareCapture({{"sourceType","file"}},155500000).isEmpty());
    auto capture = assistant.prepareCapture({{"sourceType","usb"},{"freqMhz","155.5"},{"trunking",true}},155500000);
    CHECK(!capture.value("iqCapturePath").toString().isEmpty()); CHECK(!capture["trunking"].toBool());
    QFile iq(capture["iqCapturePath"].toString()); CHECK(iq.open(QIODevice::WriteOnly)); iq.write(QByteArray(2049,'a')); iq.close();
    QFile meta(iq.fileName()+".json"); CHECK(meta.open(QIODevice::WriteOnly)); meta.write("{\"test\":true}"); meta.close();
    CHECK(!assistant.exportCapture(0,temp.filePath("signal.tar")).isEmpty());
    host.insert("sessionActive",false); CHECK(assistant.exportCapture(0,temp.filePath("signal.tar")).isEmpty());
    QFile tar(temp.filePath("signal.tar"));CHECK(tar.open(QIODevice::ReadOnly)); const auto bytes=tar.readAll();
    CHECK(bytes.mid(257,5)=="ustar"); CHECK(bytes.mid(512,2049)==QByteArray(2049,'a'));
    CHECK(bytes.mid(3072+257,5)=="ustar"); // First entry header + five padded data blocks.
    std::vector<int16_t> pcm(48000,123); dsd_audio_replay_clear(); dsd_audio_live_suppress(1);
    auto frames=dsd_audio_received_frames(); dsd_audio_replay_capture(pcm.data(),pcm.size(),48000,1);
    CHECK(dsd_audio_received_frames()==frames+48000);CHECK(dsd_audio_replay_seconds()==1);
    auto gaps=dsd_audio_gap_count(); dsd_audio_note_gap(); CHECK(gaps==dsd_audio_gap_count());
    dsd_audio_live_suppress(0); dsd_audio_note_gap();CHECK(gaps+1==dsd_audio_gap_count());
    QQmlEngine engine; dsd_qt::AppLanguage language(&engine,QStringLiteral(XERAX_QML_DIR "/../i18n/es.json"));
    language.setLanguage("es"); CHECK(QCoreApplication::translate("test","Receiver tools")==QString::fromUtf8("Herramientas de radio"));
    language.setLanguage("en"); CHECK(QCoreApplication::translate("test","Receiver tools")=="Receiver tools");
    language.setLanguage("invalid");CHECK(language.language()=="en");
    puts("Receiver policy, filters, discovery, capture, replay and language checks passed");
    return 0;
}
#include "receiver_assistant.moc"
