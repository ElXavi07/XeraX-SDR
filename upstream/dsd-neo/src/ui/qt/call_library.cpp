// SPDX-License-Identifier: GPL-3.0-or-later
#include "call_library.h"
#ifdef DSD_QT_DESKTOP_MEDIA
#include "desktop_media.h"
#endif
#include "json_store.h"
#include <QDateTime>
#include <QDir>
#include <QDirIterator>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSettings>
#include <QStandardPaths>
#include <QUrl>
#include <algorithm>
#ifdef Q_OS_ANDROID
#include <QJniObject>
#include <QCoreApplication>
#endif
namespace dsd_qt {
QString CallLibrary::directory() { return QStandardPaths::writableLocation(QStandardPaths::AppDataLocation)+"/calls"; }
QStringList CallLibrary::recordingArgs(const QString& lane) {
    if(!QSettings().value("calls/record",false).toBool()) return {};
    if(lane.contains('/') || lane.contains("..")) return {};
    const auto dir=directory()+"/"+lane; if(!QDir().mkpath(dir)) return {};
    return {"-7",dir,"-P","--rdio-mode","dirwatch"};
}
CallLibrary::CallLibrary(QObject* parent):QObject(parent) {
    m_timer.setInterval(5000); connect(&m_timer,&QTimer::timeout,this,&CallLibrary::refresh); m_timer.start(); refresh();
}
bool CallLibrary::recording() const { return QSettings().value("calls/record",false).toBool(); }
void CallLibrary::setRecording(bool value) { QSettings().setValue("calls/record",value); Q_EMIT changed(); }
void CallLibrary::setQuery(const QString& value) { m_query=value.left(200); Q_EMIT changed(); }
int CallLibrary::retentionDays() const { return QSettings().value("calls/retention",30).toInt(); }
void CallLibrary::setRetentionDays(int value) { if(value<1 || value>3650) return; QSettings().setValue("calls/retention",value); refresh(); }
QString CallLibrary::safePath(const QString& id) const {
    if(id.isEmpty() || QDir::isAbsolutePath(id)) return {};
    const auto path=QFileInfo(directory()+"/"+id).canonicalFilePath(), root=QFileInfo(directory()).canonicalFilePath();
    if(root.isEmpty() || !path.startsWith(root+"/") || !path.endsWith(".wav") || QFileInfo(path).isSymLink()) return {};
    return path;
}
void CallLibrary::refresh() {
    QVariantList rows; m_bytes=0;
    QSettings prefs;
    const auto cutoff=QDateTime::currentSecsSinceEpoch()-qint64(retentionDays())*86400;
    QDirIterator it(directory(),{"*.json"},QDir::Files,QDirIterator::Subdirectories);
    while(it.hasNext()) {
        const auto meta=it.next(); const auto wave=meta.left(meta.size()-5)+".wav";
        const auto id=QDir(directory()).relativeFilePath(wave), path=safePath(id);
        if(path.isEmpty()) continue;
        QFile file(meta); if(!file.open(QIODevice::ReadOnly) || file.size()>65536) continue;
        const auto doc=QJsonDocument::fromJson(file.readAll()); if(!doc.isObject()) continue;
        auto row=doc.object().toVariantMap();
        const bool starred=prefs.value("calls/favorites/"+id,false).toBool();
        const qint64 start=row.value("start_time").toLongLong();
        // Sidecar appears atomically after native WAV close. Never touch a writer's open WAV.
        if(start>0 && start<cutoff && !starred) { file.close(); if(QFile::remove(path)) QFile::remove(meta); continue; }
        row["id"]=id; row["favorite"]=starred; row["bytes"]=QFileInfo(path).size();
        row["duration"]=std::max<qint64>(0,row.value("stop_time").toLongLong()-start);
        row["when"]=QDateTime::fromSecsSinceEpoch(start).toLocalTime().toString("MMM d hh:mm:ss");
        row["source"]=row.value("srcList").toList().value(0).toMap().value("src");
        m_bytes+=QFileInfo(path).size(); rows.append(row);
    }
    std::sort(rows.begin(),rows.end(),[](const QVariant&a,const QVariant&b){return a.toMap().value("start_time").toLongLong()>b.toMap().value("start_time").toLongLong();});
    m_calls=rows; Q_EMIT changed();
}
QVariantList CallLibrary::calls() const {
    if(m_query.trimmed().isEmpty()) return m_calls;
    QVariantList result;
    for(const auto& value:m_calls) {
        const auto row=value.toMap();
        QString text=QString("%1 %2 %3 %4 %5 %6").arg(row.value("talkgroup_tag").toString(),row.value("talkgroup").toString(),
            row.value("source").toString(),row.value("short_name").toString(),QString::number(row.value("freq").toDouble()/1e6,'f',6),row.value("when").toString());
        if(text.contains(m_query,Qt::CaseInsensitive) || (m_query=="*" && row.value("favorite").toBool())) result.append(row);
    }
    return result;
}
bool CallLibrary::favorite(const QString& id,bool value) { if(safePath(id).isEmpty()) return false; QSettings().setValue("calls/favorites/"+id,value); refresh(); return true; }
bool CallLibrary::remove(const QString& id) {
    const auto path=safePath(id);
    if(path.isEmpty() || QSettings().value("calls/favorites/"+id,false).toBool() || !QFile::exists(path.left(path.size()-4)+".json")) return false;
    if(!QFile::remove(path)) return false;
    QFile::remove(path.left(path.size()-4)+".json"); refresh(); return true;
}
QString CallLibrary::play(const QString& id) {
    const auto path=safePath(id); if(path.isEmpty()) return tr("Recording is unavailable.");
#ifdef Q_OS_ANDROID
    if(!QJniObject::callStaticMethod<jboolean>("io/github/arancormonk/dsdneo/ReceiverExtras","play","(Landroid/content/Context;Ljava/lang/String;)Z",
        QNativeInterface::QAndroidApplication::context().object(),QJniObject::fromString(path).object())) return tr("Playback could not start.");
    return {};
#elif defined(DSD_QT_DESKTOP_MEDIA)
    return desktop_play(path);
#else
    return tr("Recording: %1").arg(path);
#endif
}
QString CallLibrary::exportCall(const QString& id,const QString& directoryUrl) {
    const auto path=safePath(id); if(path.isEmpty()) return tr("Recording is unavailable.");
#ifdef Q_OS_ANDROID
    if(directoryUrl.startsWith("content:")) return QJniObject::callStaticObjectMethod("io/github/arancormonk/dsdneo/CallExport","export",
        "(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;",QNativeInterface::QAndroidApplication::context().object(),
        QJniObject::fromString(path).object(),QJniObject::fromString(directoryUrl).object()).toString();
#endif
    QUrl url(directoryUrl); const auto dir=url.isLocalFile()?url.toLocalFile():directoryUrl;
    const auto to=QDir(dir).filePath(QFileInfo(path).fileName());
    if(!QFile::copy(path,to)) return tr("Could not export the recording. Choose a folder without a file of the same name.");
    const auto meta=path.left(path.size()-4)+".json";
    if(!QFile::copy(meta,to.left(to.size()-4)+".json")) { QFile::remove(to); return tr("Could not export call metadata."); }
    return {};
}
}
