// SPDX-License-Identifier: GPL-3.0-or-later
#include "desktop_media.h"
#include <QCoreApplication>
#include <QFile>
#include <QThread>
#include <QTimer>
#include <QtEndian>
#include <windows.h>
#include <mmsystem.h>
#include <dsd-neo/platform/audio_replay.h>
#include <dsd-neo/platform/audio.h>
namespace dsd_qt {
namespace {
QTimer* playbackTimer=nullptr;
QString ownedClip, testStatus;
QThread* testThread=nullptr;
bool playing=false, testing=false;
}
bool desktop_audio_testing() { return testing; }
void desktop_stop_playback() {
    PlaySoundW(nullptr,nullptr,0);
    if(playbackTimer) playbackTimer->stop();
    playing=false;
    if(!ownedClip.isEmpty()) { QFile::remove(ownedClip); ownedClip.clear(); }
    dsd_audio_live_suppress(0);
}
QString desktop_play(const QString& path,bool temporary) {
    if(testing) return QObject::tr("Wait for the audio test to finish.");
    QFile file(path);
    if(!file.open(QIODevice::ReadOnly)) return file.errorString();
    const auto header=file.read(12);
    if(header.size()!=12 || header.left(4)!="RIFF" || header.mid(8,4)!="WAVE")
        return QObject::tr("This recording is not a WAV file.");
    quint32 rate=0, data=0;
    for(int count=0;count<100 && !file.atEnd();++count) {
        const auto chunk=file.read(8); if(chunk.size()!=8) break;
        quint32 size=qFromLittleEndian<quint32>(chunk.constData()+4);
        if(size>quint64(file.size()-file.pos())) break;
        const auto next=file.pos()+size+(size&1);
        if(chunk.left(4)=="fmt " && size>=16) {
            const auto fmt=file.read(16);
            if(qFromLittleEndian<quint16>(fmt.constData())!=1) return QObject::tr("Only PCM WAV playback is supported.");
            rate=qFromLittleEndian<quint32>(fmt.constData()+8);
        } else if(chunk.left(4)=="data") data=size;
        if(rate && data) break;
        if(!file.seek(next)) break;
    }
    if(!rate || !data || quint64(data)*1000/rate>3600000) return QObject::tr("Invalid or oversized WAV recording.");
    file.close();
    desktop_stop_playback();
    dsd_audio_live_suppress(1);
    if(!PlaySoundW(reinterpret_cast<LPCWSTR>(path.utf16()),nullptr,SND_FILENAME|SND_ASYNC|SND_NODEFAULT)) {
        dsd_audio_live_suppress(0);
        return QObject::tr("Windows could not play this recording.");
    }
    playing=true;
    if(temporary) ownedClip=path;
    if(!playbackTimer) {
        playbackTimer=new QTimer(QCoreApplication::instance());
        playbackTimer->setSingleShot(true);
        QObject::connect(playbackTimer,&QTimer::timeout,[] { desktop_stop_playback(); });
        QObject::connect(QCoreApplication::instance(),&QCoreApplication::aboutToQuit,[] {
            desktop_stop_playback(); dsd_audio_cancel_output_test();
            if(testThread) testThread->wait();
        });
    }
    playbackTimer->start(int(quint64(data)*1000/rate)+250);
    return {};
}
void desktop_test_audio() {
    if(testing) return;
    desktop_stop_playback(); testing=true;
    testStatus=QObject::tr("Playing test tones");
    const int token=dsd_audio_output_test_token();
    testThread=QThread::create([token] {
        QThread::currentThread()->setProperty("result",dsd_audio_test_output(token));
    });
    QObject::connect(testThread,&QThread::finished,QCoreApplication::instance(),[] {
        testing=false;
        testStatus=testThread->property("result").toInt()==0
            ? QObject::tr("Windows accepted both test tones. Confirm that you heard them.")
            : QObject::tr("Audio test failed. Check the Windows default output.");
        auto* done=testThread; testThread=nullptr; done->deleteLater();
    });
    QObject::connect(QCoreApplication::instance(),&QCoreApplication::aboutToQuit,testThread,[] {
        dsd_audio_cancel_output_test(); if(testThread) testThread->wait();
    });
    testThread->start();
}
QVariantMap desktop_media_health() {
    return {{"desktop",true},{"replaying",playing},{"testingAudio",testing},{"audioTestStatus",testStatus}};
}
}
