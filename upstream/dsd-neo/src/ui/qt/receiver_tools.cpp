// SPDX-License-Identifier: GPL-3.0-or-later
#include "receiver_tools.h"
#include "app_prefs.h"
#include "saved_systems_model.h"
#include "scan_lists_model.h"
#include "decoder_host.h"
#include "json_store.h"
#include <dsd-neo/platform/audio_replay.h>
#include <dsd-neo/platform/channel_bank.h>
#include <dsd-neo/platform/analog_tones.h>
#include <dsd-neo/app_control/frontend.h>
#include <QDataStream>
#include <QDateTime>
#include <dsd-neo/app_control/notification_status.h>
#include <cmath>
#include <QDir>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QStandardPaths>
#include <QTemporaryFile>
#include <QUrl>
#include <QVector>
#ifdef Q_OS_ANDROID
#include <QJniObject>
#include <QCoreApplication>
#endif

namespace dsd_qt {
namespace {
QString localPath(const QString& url) {
    QUrl parsed(url);
    return parsed.isLocalFile() ? parsed.toLocalFile() : url;
}
#ifdef Q_OS_ANDROID
constexpr const char* extras = "io/github/arancormonk/dsdneo/ReceiverExtras";
#endif
}
ReceiverTools::ReceiverTools(AppPrefs* prefs, SavedSystemsModel* systems, ScanListsModel* lists,
                             DecoderHost* host, QObject* parent)
    : QObject(parent), m_prefs(prefs), m_systems(systems), m_lists(lists), m_host(host) {
    m_timer.setInterval(1000);
    connect(&m_timer, &QTimer::timeout, this, [this] {
        m_health["inputValid"] = false;
        dsd_channel_info capture{}; dsd_channel_get(-1,&capture);
        const bool running=m_host && m_host->isRunning();
        m_health["iqObserved"]=running && capture.source_bytes>0;
        m_health["iqFresh"]=running && capture.source_bytes>0 && capture.source_age_ms<2000;
        m_health["iqAgeMs"]=capture.source_bytes?QVariant::fromValue<qulonglong>(capture.source_age_ms):QVariant(-1);
        m_health["iqBytes"]=QVariant::fromValue<qulonglong>(capture.source_bytes);
        m_health["captureHz"]=running?capture.source_hz:0;
        m_health["captureRate"]=running?capture.sample_rate:0;
        const auto pcm = dsd_audio_received_frames(), nonzero = dsd_audio_nonzero_frames(), output = dsd_audio_output_frames();
        m_health["audioPcmArriving"] = pcm > m_audioFrames;
        m_health["audioNonzero"] = nonzero > m_nonzeroFrames;
        m_health["audioOutputMoving"] = output > m_outputFrames;
        m_health["audioSuppressed"] = dsd_audio_live_suppressed() != 0;
        m_health["audioPcmFrames"] = QVariant::fromValue<qulonglong>(pcm);
        m_health["audioOutputFrames"] = QVariant::fromValue<qulonglong>(output);
        m_audioFrames = pcm; m_nonzeroFrames = nonzero; m_outputFrames = output;
        dsd_frontend_metrics input{};
        if (dsd_app_frontend_get_metrics(&input) == 0) {
            m_health["inputValid"] = input.input_level.sample_count > 0;
            m_health["clipPct"] = input.input_level.clip_pct;
            m_health["rmsDbfs"] = input.input_level.rms_dbfs;
            m_health["autoPpm"] = input.auto_ppm_enabled != 0;
            m_health["ppmLocked"] = input.auto_ppm_locked != 0;
            m_health["ppmLockedValue"] = input.auto_ppm_locked_ppm;
            m_health["ppmErrorHz"] = input.auto_ppm_df_hz;
        }
#ifdef Q_OS_ANDROID
        const auto context = QNativeInterface::QAndroidApplication::context();
        const auto value = QJniObject::callStaticObjectMethod(extras, "health",
            "(Landroid/content/Context;)Ljava/lang/String;", context.object());
        const auto device = QJsonDocument::fromJson(value.toString().toUtf8()).object().toVariantMap();
        for (auto i = device.cbegin(); i != device.cend(); ++i) m_health[i.key()] = i.value();
#endif
        dsd_app_notification_status activity{};
        if (m_systems && dsd_app_notification_get(&activity) && activity.radio_input
            && (activity.slots[0].state == DSD_APP_CALL_LINE_ACTIVE || activity.slots[1].state == DSD_APP_CALL_LINE_ACTIVE)) {
            const auto frequency = activity.cc_freq_hz > 0 ? activity.cc_freq_hz : activity.center_freq_hz;
            auto heard = json_store_load_array("heard_sites.json"); bool updated = false;
            for (int row=0; row<m_systems->count(); row++) {
                auto site=m_systems->get(row);
                if (std::abs(site.value("freqMhz").toDouble()*1e6-frequency)>100) continue;
                const auto uid=site.value("uid").toString(); const qint64 now=QDateTime::currentSecsSinceEpoch();
                int index=-1;for(int i=0;i<heard.size();i++) if(heard[i].toObject().value("uid").toString()==uid){index=i;break;}
                if(index>=0 && now-heard[index].toObject().value("at").toDouble()<60) continue;
                QJsonObject record{{"uid",uid},{"at",now}};
                if(index>=0) heard[index]=record; else heard.append(record);
                updated=true;
            }
            if(updated) json_store_save_array("heard_sites.json",heard);
        }
        dsd_analog_tones tones{}; dsd_analog_tones_get(&tones);
        m_health["tone"] = tones.ctcss_hz > 0 ? QString("CTCSS %1 Hz").arg(tones.ctcss_hz, 0, 'f', 1)
            : tones.dcs_code >= 0 ? QString("DCS %1N").arg(tones.dcs_code, 3, 8, QLatin1Char('0'))
                + (tones.dcs_inverse_code >= 0 ? QString(" / %1I").arg(tones.dcs_inverse_code, 3, 8, QLatin1Char('0')) : QString())
            : tr("No stable tone identified");
        Q_EMIT changed();
    });
    m_timer.start();
}
double ReceiverTools::replaySeconds() const { return dsd_audio_replay_seconds(); }
void ReceiverTools::clearReplay() { dsd_audio_replay_clear(); Q_EMIT changed(); }
QString ReceiverTools::saveReplay(const QString& url, int seconds) {
    if (seconds < 1 || seconds > 60) return tr("Choose 1–60 seconds.");
    QVector<int16_t> samples(48000 * seconds);
    const size_t count = dsd_audio_replay_snapshot(samples.data(), static_cast<size_t>(samples.size()), seconds);
    if (!count) return tr("No received audio in the replay buffer yet.");
    QFile file(localPath(url));
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate)) return file.errorString();
    QDataStream out(&file);
    out.setByteOrder(QDataStream::LittleEndian);
    out.writeRawData("RIFF", 4); out << quint32(36 + count * 2);
    out.writeRawData("WAVEfmt ", 8); out << quint32(16) << quint16(1) << quint16(1)
        << quint32(48000) << quint32(96000) << quint16(2) << quint16(16);
    out.writeRawData("data", 4); out << quint32(count * 2);
    for (size_t i = 0; i < count; ++i) out << samples[static_cast<qsizetype>(i)];
    return out.status() == QDataStream::Ok && file.flush() ? QString() : tr("Could not finish writing the clip.");
}
QString ReceiverTools::playReplay(int seconds) {
    const QString dir = QStandardPaths::writableLocation(QStandardPaths::CacheLocation);
    QDir().mkpath(dir);
    // Each player owns its file until release; a second tap cannot truncate the
    // clip the Android media service is still reading or preparing.
    QTemporaryFile clip(dir + "/xerax-replay-XXXXXX.wav");
    if (!clip.open()) return clip.errorString();
    const QString path = clip.fileName();
    clip.close();
    const auto error = saveReplay(path, seconds);
    if (!error.isEmpty()) return error;
#ifdef Q_OS_ANDROID
    const auto context = QNativeInterface::QAndroidApplication::context();
    if (QJniObject::callStaticMethod<jboolean>(extras, "play", "(Landroid/content/Context;Ljava/lang/String;)Z",
        context.object(), QJniObject::fromString(path).object())) { clip.setAutoRemove(false); return {}; }
    return tr("Playback could not start.");
#else
    clip.setAutoRemove(false);
    return tr("Clip created: %1").arg(path);
#endif
}
void ReceiverTools::stopPlayback() {
#ifdef Q_OS_ANDROID
    QJniObject::callStaticMethod<void>(extras, "stopPlayback", "()V");
#endif
}
void ReceiverTools::restoreAudio() {
#ifdef Q_OS_ANDROID
    const auto context = QNativeInterface::QAndroidApplication::context();
    QJniObject::callStaticMethod<void>(extras, "restoreAudio", "(Landroid/content/Context;)V", context.object());
#endif
}
void ReceiverTools::testAudio() {
#ifdef Q_OS_ANDROID
    const auto context = QNativeInterface::QAndroidApplication::context();
    QJniObject::callStaticMethod<void>(extras, "testAudio", "(Landroid/content/Context;)V", context.object());
#endif
}
QVariantList ReceiverTools::profiles() const { return json_store_load_array("receiver_profiles.json").toVariantList(); }
bool ReceiverTools::saveProfile(const QString& name, int gain, int ppm, int bandwidth, bool biasTee) {
    if (name.trimmed().isEmpty() || name.size() > 80 || gain < -1 || gain > 49 || ppm < -200 || ppm > 200
        || !QList<int>{4, 6, 8, 12, 16, 24, 48}.contains(bandwidth)) return false;
    auto rows = json_store_load_array("receiver_profiles.json");
    if (rows.size() >= 100) return false;
    rows.append(QJsonObject{{"name", name.trimmed()}, {"gainDb", gain}, {"ppm", ppm},
        {"bandwidthKhz", bandwidth}, {"biasTee", biasTee}});
    bool ok = json_store_save_array("receiver_profiles.json", rows);
    Q_EMIT changed(); return ok;
}
bool ReceiverTools::applyProfile(int index) {
    auto rows = profiles();
    if (!m_prefs || index < 0 || index >= rows.size()) return false;
    const auto row = rows[index].toMap();
    m_prefs->setGainDb(row.value("gainDb").toInt()); m_prefs->setPpm(row.value("ppm").toInt());
    m_prefs->setBandwidthKhz(row.value("bandwidthKhz").toInt()); m_prefs->setBiasTee(row.value("biasTee").toBool());
    return true;
}
bool ReceiverTools::removeProfile(int index) {
    auto rows = json_store_load_array("receiver_profiles.json");
    if (index < 0 || index >= rows.size()) return false;
    rows.removeAt(index); bool ok = json_store_save_array("receiver_profiles.json", rows);
    Q_EMIT changed(); return ok;
}
QVariantList ReceiverTools::sites(double latitude, double longitude) const {
    QVariantList result;
    if (!m_systems) return result;
    const auto heard=json_store_load_array("heard_sites.json");
    for (int i = 0; i < m_systems->count(); ++i) {
        auto row = m_systems->get(i);
        row["heardAt"]=0;
        for(const auto& v:heard) {auto record=v.toObject();if(record.value("uid").toString()==row.value("uid").toString()) row["heardAt"]=record.value("at").toDouble();}
        const double km = m_systems->distanceKm(i, latitude, longitude);
        if (km < 0) continue;
        row["distanceMi"] = km / 1.609344; row["row"] = i;
        result.append(row);
    }
    return result;
}
QString ReceiverTools::alertRules() const {
#ifdef Q_OS_ANDROID
    return QJniObject::callStaticObjectMethod(extras, "alertRules", "(Landroid/content/Context;)Ljava/lang/String;",
        QNativeInterface::QAndroidApplication::context().object()).toString();
#else
    return {};
#endif
}
bool ReceiverTools::setAlertRules(const QString& rules) {
#ifdef Q_OS_ANDROID
    return QJniObject::callStaticMethod<jboolean>(extras, "configureAlerts", "(Landroid/content/Context;Ljava/lang/String;)Z",
        QNativeInterface::QAndroidApplication::context().object(), QJniObject::fromString(rules).object());
#else
    Q_UNUSED(rules); return false;
#endif
}

}
