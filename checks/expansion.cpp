// SPDX-License-Identifier: GPL-3.0-or-later
#include <QCoreApplication>
#include <QFile>
#include <QDir>
#include <dsd-neo/engine/trunk_scan.h>
#include <QJsonDocument>
#include <QJsonObject>
#include <QStandardPaths>
#include <QUuid>
#include "receiver_tools.h"
#include "app_prefs.h"
#include "saved_systems_model.h"
#include "scan_lists_model.h"
#include "json_store.h"
#include <dsd-neo/platform/audio_replay.h>
#include <dsd-neo/platform/analog_tones.h>
#include <dsd-neo/runtime/scan_priority.h>
#include <dsd-neo/app_control/frontend.h>
#include <cmath>
#include <cstdio>
#include <vector>
#include <random>
extern "C" int dsd_app_frontend_get_metrics(dsd_frontend_metrics*) { return -1; }
int main(int argc,char**argv) {
    QCoreApplication app(argc,argv);QStandardPaths::setTestModeEnabled(true);
    QCoreApplication::setOrganizationName("XeraXChecks");QCoreApplication::setApplicationName("expansion-"+QUuid::createUuid().toString(QUuid::WithoutBraces));
    int failed=0;auto check=[&](bool okay,const char*label){if(!okay){++failed;std::fprintf(stderr,"FAIL %s\n",label);}};
    uint8_t priorities[]={1,3,1,1,3};size_t active=0,normal=0,priority=4;
    const size_t sequence[]={1,2,4,3,1,0,4,2};
    for(auto expect:sequence){if(priorities[active]&2)priority=active;else normal=active;
        active=dsd_scan_priority_choose(priorities,5,active,normal,priority);check(active==expect,"priority preserves ordinary rotation");}
    uint8_t avoided[]={1,2,0};check(dsd_scan_priority_choose(avoided,3,0,0,0)==0,"avoided/cooling targets skipped");
    dsd_audio_replay_clear();std::vector<int16_t> stereo(16000);
    for(int i=0;i<8000;i++){stereo[i*2]=2000;stereo[i*2+1]=1000;}
    dsd_audio_replay_capture(stereo.data(),8000,8000,2);
    check(std::abs(dsd_audio_replay_seconds()-1.0)<0.01,"8k stereo resampled to 48k mono");
    std::vector<int16_t> audio(48000*60);auto count=dsd_audio_replay_snapshot(audio.data(),audio.size(),60);
    check(count>47000 && std::abs(audio[1000]-1500)<3,"replay mixes both digital slots");
    std::vector<int16_t> second(48000);
    for(int sec=1;sec<=65;sec++){std::fill(second.begin(),second.end(),sec);dsd_audio_replay_capture(second.data(),second.size(),48000,1);}
    count=dsd_audio_replay_snapshot(audio.data(),audio.size(),60);
    check(count==48000*60 && audio.front()==6 && audio.back()==65,"bounded replay evicts oldest audio");
    // This multiplication overflowed size_t on ARMv7 before division.
    dsd_audio_replay_clear();
    std::vector<int16_t> longBlock(480000, 1234);
    const auto receivedBefore = dsd_audio_received_frames();
    dsd_audio_replay_capture(longBlock.data(), longBlock.size(), 8000, 1);
    count=dsd_audio_replay_snapshot(audio.data(),audio.size(),60);
    check(count==2880000 && dsd_audio_received_frames()-receivedBefore==2880000
        && audio.front()==1234 && audio.back()==1234, "maximum block has correct resampled size on 32/64-bit");
    dsd_qt::AppPrefs prefs;dsd_qt::SavedSystemsModel systems;dsd_qt::ScanListsModel lists;
    dsd_qt::ReceiverTools tools(&prefs,&systems,&lists,nullptr);
    const auto wav=dsd_qt::json_store_path("clip.wav");QDir().mkpath(QFileInfo(wav).absolutePath());check(tools.saveReplay(wav,30).isEmpty(),"WAV export");
    QFile w(wav);check(w.open(QIODevice::ReadOnly),"open WAV");auto bytes=w.readAll();check(bytes.startsWith("RIFF")&&bytes.mid(8,8)=="WAVEfmt "&&bytes.size()==44+30*48000*2,"WAV framing and duration");
    check(!tools.saveProfile("",20,0,24,false),"invalid profile rejected");check(!tools.saveProfile("Invalid width",22,2,384,false),"unsupported receiver profile bandwidth refused");check(tools.saveProfile("RTL V3 roof",22,2,24,false),"profile saved");
    prefs.setRrUsername("private-account");prefs.setRrAppKey("PRIVATE-PASSWORD");
    const auto csv=dsd_qt::json_store_path("labels.csv");QFile labels(csv);labels.open(QIODevice::WriteOnly);labels.write("123,A,Test dispatch\n");labels.close();
    check(systems.add({{"name","Analog test"},{"freqMhz","155.25"},{"sourceType","usb"},{"decodeFlag","-fA"},{"groupCsvPath",csv},{"extraArgs","PRIVATE-ARGUMENT"}}),"saved channel");
    auto old=systems.get(0).value("uid").toString();auto draft=lists.newDraft();draft["name"]="Mix";draft["entries"]=QVariantList{QVariantMap{{"kind","system"},{"systemUid",old},{"priority",true}}};check(lists.add(draft),"saved list");
    const auto backup=dsd_qt::json_store_path("backup.json");check(tools.backup(backup).isEmpty(),"portable backup");
    QFile b(backup);b.open(QIODevice::ReadOnly);auto document=b.readAll();b.close();
    check(!document.contains("private-account")&&!document.contains("PRIVATE-PASSWORD")&&!document.contains("PRIVATE-ARGUMENT"),"backup excludes credentials and arbitrary arguments");
    check(tools.restore(backup).isEmpty(),"restore portable backup");check(systems.count()==2&&lists.count()==2,"restore appends without overwriting");
    auto newId=systems.get(1).value("uid").toString();auto restored=lists.get(1).value("entries").toList().first().toMap();
    check(old!=newId&&restored.value("systemUid")==newId&&restored.value("priority").toBool(),"restore remaps references and preserves priority");
    auto newPath=systems.get(1).value("groupCsvPath").toString();QFile relocated(newPath);check(newPath!=csv&&relocated.open(QIODevice::ReadOnly)&&relocated.readAll()=="123,A,Test dispatch\n","restore copies and relocates CSV");
    auto bad=QJsonDocument::fromJson(document).object();bad["files"]=QJsonObject{};b.open(QIODevice::WriteOnly|QIODevice::Truncate);b.write(QJsonDocument(bad).toJson());b.close();
    check(!tools.restore(backup).isEmpty()&&systems.count()==2&&lists.count()==2,"invalid backup changes no lists");
    // Synthetic unfiltered NFM discriminator waveforms: no RF/hardware claim.
    constexpr double pi=3.141592653589793;std::vector<float> tone(48000*3);
    for(int i=0;i<(int)tone.size();i++)tone[i]=1000*std::sin(2*pi*100*i/48000)+400*std::sin(2*pi*1000*i/48000);
    dsd_analog_tones_feed(tone.data(),tone.size(),48000,1,1);dsd_analog_tones result{};dsd_analog_tones_get(&result);check(result.ctcss_hz==100,"CTCSS 100Hz with voice");
    dsd_analog_tones_feed(tone.data(),960,48000,2,1);dsd_analog_tones_get(&result);check(result.ctcss_hz==0,"retune clears tone evidence");
    std::mt19937 random(42);std::normal_distribution<float> noise(0,500);
    for(auto&v:tone)v=noise(random);dsd_analog_tones_reset();dsd_analog_tones_feed(tone.data(),tone.size(),48000,1,1);dsd_analog_tones_get(&result);check(result.ctcss_hz==0&&result.dcs_code<0,"noise does not become tone or DCS");
    // Known parity-first Golay word for DCS 023, independently fixed as a test vector.
    const unsigned word=0x763813;
    for(int inverted=0;inverted<2;inverted++){
        for(int i=0;i<(int)tone.size();i++){int bit=int(double(i)*134.4/48000)%23;tone[i]=(((word>>bit)&1)^inverted)?1000:-1000;}
        dsd_analog_tones_reset();dsd_analog_tones_feed(tone.data(),tone.size(),48000,1,1);dsd_analog_tones_get(&result);
        check(result.dcs_code==(inverted?0047:0023)&&result.dcs_inverse_code==(inverted?0023:0047),"DCS 023 normal/inverted repeated words");
    }
    dsd_analog_tones_feed(tone.data(),960,48000,1,0);dsd_analog_tones_get(&result);check(result.dcs_code<0&&result.ctcss_hz==0,"closed squelch clears identifiers");
    const auto targetPath=dsd_qt::json_store_path("targets.csv");QFile target(targetPath);
    check(target.open(QIODevice::WriteOnly),"create target CSV");
    target.write("id,type,frequency_hz,chan_csv,dwell_ms,activity_hold_ms,notes,priority\nanalog,nfm-conventional,155250000,,500,1200,,1\ndigital,p25-conventional,851012500,,600,1400,,0\n");target.close();
    dsd_trunk_scan_target_list parsed{};char parseError[256]{};
    check(dsd_trunk_scan_load_targets_csv(targetPath.toUtf8().constData(),nullptr,&parsed,parseError,sizeof parseError)==0,"real native mixed CSV parser");
    check(parsed.count==2&&parsed.targets[0].priority==1&&parsed.targets[0].type==DSD_TRUNK_SCAN_TARGET_NFM_CONVENTIONAL&&parsed.targets[1].priority==0,"priority survives native parsing");
    dsd_trunk_scan_target_list_reset(&parsed);
    auto imported=lists.newDraft();imported["name"]="Imported";imported["targetSource"]="csv";imported["targetsCsvPath"]=targetPath;
    check(lists.add(imported),"add CSV scan list");const auto converted=dsd_qt::json_store_path("csv-backup.json");
    const auto backupError=tools.backup(converted);if(!backupError.isEmpty())std::fprintf(stderr,"%s\n",backupError.toUtf8().constData());check(backupError.isEmpty(),"convert CSV targets into portable scan list");
    check(tools.restore(converted).isEmpty(),"restore converted CSV list");
    check(lists.get(lists.count()-1).value("targetSource")=="manual"&&lists.get(lists.count()-1).value("entries").toList().size()==2,"CSV list converted completely");
    dsd_audio_replay_clear();check(dsd_audio_replay_seconds()==0,"clear replay erases samples");
    return failed?1:0;
}
#include <dsd-neo/app_control/notification_status.h>
extern "C" int dsd_app_notification_get(dsd_app_notification_status*) {return 0;}
