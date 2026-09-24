// SPDX-License-Identifier: GPL-3.0-or-later
#include "receiver_assistant.h"
#include "json_store.h"
#include "saved_systems_model.h"
#include <dsd-neo/platform/receiver_filter.h>
#include <dsd-neo/platform/audio_replay.h>
#include <dsd-neo/runtime/config.h>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSaveFile>
#include <QSettings>
#include <QStandardPaths>
#include <QStorageInfo>
#include <QUrl>
#include <cmath>
#include <algorithm>
namespace dsd_qt {
namespace {
QString path(const QString& url) { QUrl u(url); return u.isLocalFile() ? u.toLocalFile() : url; }
QString captureDir() { return QStandardPaths::writableLocation(QStandardPaths::AppDataLocation) + "/iq-captures"; }
QString writeJson(const QString& file, const QJsonDocument& doc) {
    QSaveFile out(path(file));
    out.setDirectWriteFallback(file.startsWith("content://"));
    if (!out.open(QIODevice::WriteOnly) || out.write(doc.toJson()) < 0 || !out.commit()) return out.errorString();
    return {};
}
}
ReceiverAssistant::ReceiverAssistant(QObject* parent) : QObject(parent) {
    m_notes = json_store_load_array("discoveries.json").toVariantList();
    while (m_notes.size() > 500) m_notes.removeFirst();
    m_filters = json_store_load_array("receiver_filters.json").toVariantList();
    m_notebook = QSettings().value("receiver/notebook", false).toBool();
    publishFilters(); m_clock.start();
    m_timer.setInterval(1000); connect(&m_timer, &QTimer::timeout, this, &ReceiverAssistant::poll);
    m_status["gainText"] = tr("Automatic gain is off");
    m_status["siteText"] = tr("Automatic site selection is off");
}
ReceiverAssistant::~ReceiverAssistant() { cancelGain(true); persistNotes(); }
void ReceiverAssistant::configure(QObject* metrics, QObject* commands, QObject* host, QObject* tools, SavedSystemsModel* systems) {
    m_metrics = metrics; m_commands = commands; m_host = host; m_tools = tools; m_systems = systems; m_timer.start();
}
QVariant ReceiverAssistant::value(const char* key) const { return m_metrics ? m_metrics->property(key) : QVariant(); }
void ReceiverAssistant::setSession(const QString& uid, bool scanning) {
    if (uid != m_uid && uid != m_trialUid) { m_trialUid.clear(); m_originUid.clear(); m_siteCooldown = std::max(m_siteCooldown, nowMs() + 30000); }
    m_uid = uid; m_scanning = scanning;
}
bool ReceiverAssistant::commandGain(int gain) {
    bool accepted = false;
    return m_commands && QMetaObject::invokeMethod(m_commands, "setTunerGain", Qt::DirectConnection,
        Q_RETURN_ARG(bool, accepted), Q_ARG(int, gain)) && accepted;
}
void ReceiverAssistant::cancelGain(bool restore) {
    if (restore && m_gainPhase == 2 && value("centerFreqHz").toDouble() == m_gainFrequency && value("tunerGainDb").toInt() == m_trialGain && !m_scanning
        && !value("tunerControlled").toBool() && value("radioInput").toBool()
        && m_host && m_host->property("running").toBool()) commandGain(m_originalGain);
    m_gainPhase = 0; m_gainTicks = 0;
}
void ReceiverAssistant::setAutoGain(bool enabled) {
    if(enabled && value("rangeScanActive").toBool()) return;
    if (m_autoGain == enabled) return;
    if (!enabled) cancelGain(true);
    m_autoGain = enabled; m_gainCooldown = 0;
    m_status["gainGeneration"] = m_status.value("gainGeneration").toInt() + 1;
    m_status["gainText"] = enabled ? tr("Waiting for a steady, idle RTL-SDR channel") : tr("Automatic gain is off");
    Q_EMIT changed();
}
void ReceiverAssistant::setRoaming(bool enabled) {
    if(enabled && value("rangeScanActive").toBool()) return;
    m_roaming = enabled;
    // Disabling is a manual choice: keep the site currently being heard.
    m_trialUid.clear(); m_originUid.clear(); m_weakTicks = 0;
    m_status["siteText"] = enabled ? tr("Watching saved sites in this system") : tr("Automatic site selection is off");
    Q_EMIT changed();
}
void ReceiverAssistant::setNotebook(bool enabled) {
    m_notebook = enabled; QSettings().setValue("receiver/notebook", enabled); Q_EMIT changed();
}
double ReceiverAssistant::score(int ok, int bad, double snr, bool snrValid, double clip, bool clipValid, bool analog) {
    if (!analog && ok + bad < 8) return -1;
    if (analog && !snrValid) return -1;
    const double base = analog ? std::clamp(snr * 3.0, 0.0, 100.0) : 100.0 * ok / (ok + bad);
    return std::max(0.0, base - (clipValid ? std::min(40.0, clip * 20.0) : 0.0));
}
void ReceiverAssistant::poll() {
    if (!m_metrics || !m_host) return;
    const bool live = m_host->property("running").toBool();
    const double frequency = value("centerFreqHz").toDouble();
    const bool changedChannel = frequency != m_frequency || live != m_wasLive;
    const auto ok = value("ccFecOk").toULongLong(), bad = value("ccFecErr").toULongLong();
    const bool sync = value("syncedHere").toBool();
    const bool active = value("slot1CallState").toInt() == 2 || value("slot2CallState").toInt() == 2;
    const int mode = value("decodeMode").toInt();
    const bool analog = mode == DSDCFG_MODE_ANALOG || mode == DSDCFG_MODE_AM || mode == DSDCFG_MODE_WFM;
    // decode mode flags vary by engine; use the stable metrics mode labels when available.
    const auto health = m_tools ? m_tools->property("health").toMap() : QVariantMap();
    if (changedChannel || ok < m_prevOk || bad < m_prevBad) {
        m_window.clear(); m_syncLosses = 0; m_synced = false; m_silent = 0;
        m_gapBase = dsd_audio_gap_count(); m_prevOk = ok; m_prevBad = bad;
        if (changedChannel) cancelGain(true);
    }
    const int deltaOk = int(std::min<quint64>(ok - m_prevOk, 100000));
    const int deltaBad = int(std::min<quint64>(bad - m_prevBad, 100000));
    if (live && m_synced && !sync && !changedChannel) ++m_syncLosses;
    m_prevOk = ok; m_prevBad = bad; m_synced = sync; m_frequency = frequency; m_wasLive = live;
    m_status["live"] = live; m_status["frequency"] = frequency;
    m_status["canCapture"] = live && !m_scanning && !value("rangeScanActive").toBool() && !m_status.value("capturing").toBool() && value("radioInput").toBool();
    m_status["deltaOk"] = deltaOk; m_status["deltaBad"] = deltaBad;
    m_status["clipValid"] = live && health.value("inputValid").toBool();
    m_status["clip"] = health.value("clipPct");
    m_status["snrValid"] = live && value("snrValid").toBool();
    m_status["snr"] = value("snrDb"); m_status["syncLosses"] = m_syncLosses;
    m_status["audioGaps"] = QVariant::fromValue(dsd_audio_gap_count() - m_gapBase);
    m_status["replaying"] = health.value("replaying", false);
    if (live) {
        m_window.append({{"ok", deltaOk}, {"bad", deltaBad}, {"sync", sync}});
        if (m_window.size() > 30) m_window.removeFirst();
    }
    int good = 0, failed = 0, synced = 0;
    for (const auto& sample : m_window) { good += sample.value("ok").toInt(); failed += sample.value("bad").toInt(); synced += sample.value("sync").toBool(); }
    m_status["validFrames"] = good; m_status["failedFrames"] = failed;
    m_status["framePercent"] = good + failed >= 8 ? 100.0 * good / (good + failed) : -1;
    m_status["syncPercent"] = m_window.isEmpty() ? 0.0 : 100.0 * synced / m_window.size();
    const auto frames = dsd_audio_received_frames();
    m_silent = live && frames == m_frames && !value("audioMuted").toBool() ? m_silent + 1 : 0; m_frames = frames;
    const auto output = m_host->property("audioOutput").toMap();
    m_status["iqFresh"]=live && health.value("iqFresh").toBool();
    m_status["protocolFresh"]=live && sync;
    m_status["voiceActive"]=live && active;
    m_status["pcmFresh"]=live && health.value("audioPcmArriving").toBool();
    QString advice;
    if (!live) advice = m_host->property("inputFailureKind").toInt() == 7 ? tr("Receiver disconnected. Reconnect USB, then retry the source.") : tr("Start a channel to check reception and audio.");
    else if (health.value("testingAudio").toBool()) advice = tr("Playing test tones through the selected output.");
    else if (health.value("workerAudio").toBool()) advice = tr("An extra receiver owns playback. Open Receivers to check its activity and audio counters.");
    else if (health.value("replaying").toBool()) advice = tr("Replay is playing. Reception and recording continue.");
    else if (health.value("focusLost").toBool()) advice = tr("Another app has audio focus. Audio resumes when focus returns.");
    else if (!health.value("playbackError").toString().isEmpty()) advice = health.value("playbackError").toString();
    else if (value("audioMuted").toBool()) advice = tr("Live audio is muted. Tap Unmute to listen.");
    else if (health.contains("mediaVolume") && health.value("mediaVolume").toInt() == 0) advice = tr("Media volume is zero. Press the phone volume-up button.");
    else if (health.value("audioSuppressed").toBool()) advice = tr("Live output is paused. Use Restore speaker audio.");
    else if (health.value("audioPcmArriving").toBool() && !health.value("audioNonzero").toBool()) advice = tr("The decoder is producing silence. Call activity alone does not confirm voice audio.");
    else if (health.value("audioPcmArriving").toBool() && health.contains("testingAudio") && !health.value("audioOutputMoving").toBool()) advice = tr("Decoded audio is arriving but Android is not accepting it. Try Restore speaker audio.");
    else if (!output.value("note").toString().isEmpty()) advice = output.value("note").toString();
    else if (health.value("iqObserved").toBool() && !health.value("iqFresh").toBool()) advice = tr("Radio samples stopped arriving. Check the receiver or RTL-TCP connection.");
    else if (m_silent >= 8 && active) advice = tr("A call is active without audio. Check encryption, filters and the selected output.");
    else if (m_silent >= 8 && !analog && sync) advice = tr("Digital sync is present, but no voice audio is being produced. The channel may be idle or carrying control data.");
    else if (m_silent >= 8 && !analog && health.value("iqFresh").toBool()) advice = tr("Radio samples are arriving, but there is no recent digital sync. Check frequency, mode, signal level and antenna.");
    else if (m_silent >= 8 && analog) advice = tr("No analog audio is being produced. Open squelch and check tone filters and channel activity.");
    else if (m_silent >= 8) advice = tr("No audio is reaching the player. Check squelch, channel activity and filters.");
    else if (m_silent > 0) advice = tr("Waiting for received audio.");
    else advice = tr("Audio is reaching the player. Choose Phone speaker if the route sounds wrong.");
    m_status["audioText"] = advice;
    observeNotebook(live, !changedChannel, active, frequency);
    const bool gainEligible = live && !m_scanning && !value("scannerMode").toBool() && !value("rangeScanActive").toBool() && !value("tunerControlled").toBool() && value("radioInput").toBool()
        && !value("airspy").toMap().contains("gain_mode") && m_trialUid.isEmpty();
    m_status["gainEligible"] = gainEligible;
    observeGain(gainEligible, active, analog, frequency);
    m_status["gainPhase"] = m_gainPhase;
    observeSites(live, active);
    if (++m_flush % 10 == 0) Q_EMIT discoveriesChanged();
    if (m_flush >= 30) { persistNotes(); m_flush = 0; }
    Q_EMIT changed();
}
void ReceiverAssistant::observeGain(bool eligible, bool active, bool analog, double frequency) {
    if (!m_autoGain) return;
    if (!eligible || frequency <= 0) { cancelGain(true); m_status["gainText"] = tr("Waiting for a steady, idle RTL-SDR channel"); return; }
    if (m_gainPhase && m_gainTicks > 2 && value("tunerGainDb").toInt() != (m_gainPhase == 2 ? m_trialGain : m_originalGain)) {
        cancelGain(false); m_autoGain = false;
        m_status["gainText"] = tr("Gain changed outside the trial. Automatic gain stopped."); return;
    }
    if (active) { m_status["gainText"] = tr("Waiting for the active call to finish"); return; }
    if (nowMs() < m_gainCooldown) return;
    if (!m_gainPhase) {
        m_gainPhase = 1; m_gainTicks = 0; m_originalGain = value("tunerGainDb").toInt(); m_gainFrequency = frequency;
        m_good = m_bad = m_nSnr = m_nClip = 0; m_sumSnr = m_sumClip = 0;
        m_status["gainText"] = tr("Measuring original gain for 10 seconds");
        m_status["gainOriginal"] = m_originalGain; m_status["gainKept"] = false;
        m_status["gainBaselineScore"] = -1; m_status["gainTrialScore"] = -1;
    }
    if (++m_gainTicks <= 2) return;
    m_good += m_status.value("deltaOk").toInt(); m_bad += m_status.value("deltaBad").toInt();
    if (m_status.value("snrValid").toBool()) { ++m_nSnr; m_sumSnr += m_status.value("snr").toDouble(); }
    if (m_status.value("clipValid").toBool()) { ++m_nClip; m_sumClip += m_status.value("clip").toDouble(); }
    if (m_gainTicks < 12) return;
    const double clip = m_nClip ? m_sumClip / m_nClip : 0;
    const double result = score(m_good, m_bad, m_nSnr ? m_sumSnr / m_nSnr : 0, m_nSnr >= 5, clip, m_nClip >= 5, analog);
    if (m_gainPhase == 1 && result >= 0) {
        m_baseScore = result;
        m_status["gainBaselineScore"] = result;
        m_trialGain = std::clamp(m_originalGain == 0 ? 20 : m_originalGain + (clip > 0.1 ? -6 : 4), 1, 49);
        m_status["gainTrial"] = m_trialGain;
        if (m_trialGain != m_originalGain && commandGain(m_trialGain)) {
            m_gainPhase = 2; m_gainTicks = 0; m_good = m_bad = m_nSnr = m_nClip = 0; m_sumSnr = m_sumClip = 0;
            m_status["gainText"] = tr("Testing %1 dB; worse results restore the original").arg(m_trialGain); return;
        }
    } else if (m_gainPhase == 2 && result >= m_baseScore + 3) {
        m_status["gainTrialScore"] = result; m_status["gainKept"] = true; m_status["gainOutcome"] = QStringLiteral("kept_measured_improvement");
        m_status["gainCompleted"] = m_status.value("gainCompleted").toInt() + 1;
        m_gainPhase = 0;
        m_status["gainText"] = tr("Kept %1 dB: measured quality improved").arg(m_trialGain);
        m_gainCooldown = nowMs() + 120000; return;
    }
    if (m_gainPhase == 2) m_status["gainTrialScore"] = result;
    m_status["gainOutcome"] = result < 0 ? QStringLiteral("insufficient_evidence") : QStringLiteral("original_restored");
    m_status["gainCompleted"] = m_status.value("gainCompleted").toInt() + 1;
    cancelGain(true); m_gainCooldown = nowMs() + 120000;
    m_status["gainText"] = result < 0 ? tr("Not enough evidence. Original gain restored.") : tr("No clear improvement. Original gain restored.");
}
void ReceiverAssistant::observeSites(bool live, bool active) {
    if (!m_roaming || !m_systems || m_scanning || m_uid.isEmpty()) return;
    if (active || value("heldTg").toUInt() || value("scanHold").toBool() || m_gainPhase) {
        m_status["siteText"] = tr("Keeping this site until the call or hold ends"); return;
    }
    if (!live) {
        if (!m_trialUid.isEmpty() && m_host->property("sessionState").toInt() == 4) {
            const auto origin = m_originUid;
            m_trialUid.clear(); m_originUid.clear(); m_siteCooldown = nowMs() + 300000;
            m_status["siteText"] = tr("Site could not start. Returning to the previous site."); Q_EMIT switchSite(origin);
        }
        return;
    }
    const double quality = m_status.value("framePercent").toDouble();
    const double qualityScore = quality < 0 ? 0 : quality * m_status.value("syncPercent").toDouble() / 100.0;
    if (!m_trialUid.isEmpty()) {
        if (m_uid != m_trialUid || nowMs() < m_siteDeadline) return;
        const QString origin = m_originUid;
        m_trialUid.clear(); m_originUid.clear(); m_siteCooldown = nowMs() + 300000;
        if (quality >= 0 && qualityScore >= m_originScore + 10) m_status["siteText"] = tr("Kept the site with better measured decoding");
        else { m_status["siteText"] = tr("Trial was not better. Returning to the previous site."); Q_EMIT switchSite(origin); }
        return;
    }
    if (nowMs() < m_siteCooldown) return;
    m_weakTicks = qualityScore < 50 ? m_weakTicks + 1 : 0;
    if (m_weakTicks < 20) return;
    const int row = m_systems->rowForUid(m_uid); const auto current = m_systems->get(row);
    const auto siblings = m_systems->siblingRows(row);
    for (int i = 0; i < siblings.size(); ++i) {
        const auto candidate = m_systems->get(siblings[(m_candidateIndex + i) % siblings.size()].toInt());
        if (candidate.value("uid").toString() == m_uid || candidate.value("avoidSite").toBool()
            || candidate.value("sourceType") != current.value("sourceType") || candidate.value("decodeFlag") != current.value("decodeFlag")
            || candidate.value("host") != current.value("host") || candidate.value("port") != current.value("port")) continue;
        m_candidateIndex = (m_candidateIndex + i + 1) % siblings.size();
        m_originUid = m_uid; m_trialUid = candidate.value("uid").toString(); m_originScore = qualityScore;
        m_siteDeadline = nowMs() + 35000; m_weakTicks = 0;
        m_status["siteText"] = tr("Checking %1; reception briefly restarts").arg(candidate.value("name").toString());
        Q_EMIT switchSite(m_trialUid); return;
    }
    m_status["siteText"] = tr("Import another eligible site in the same RadioReference system");
    m_siteCooldown = nowMs() + 30000;
}
void ReceiverAssistant::observeNotebook(bool live, bool stable, bool active, double frequency) {
    if (!m_notebook || !live || frequency <= 0) return;
    const bool confirmed = value("syncedHere").toBool();
    const auto health = m_tools ? m_tools->property("health").toMap() : QVariantMap();
    const bool energy = health.value("inputValid").toBool() && health.value("rmsDbfs").toDouble() > -45;
    if (!confirmed && !energy && !active) { m_noteStreak = 0; return; }
    const QString protocol = confirmed ? value("syncLabel").toString() : QString("Unconfirmed energy");
    const QString identity = QString::number(quint64(frequency)) + ":" + protocol;
    if (!stable || identity != m_noteIdentity) { m_noteIdentity = identity; m_noteStreak = 0; }
    if (++m_noteStreak < 3) return;
    int index = -1;
    for (int i = 0; i < m_notes.size(); ++i) if (m_notes[i].toMap().value("id").toString() == identity) { index = i; break; }
    auto note = index < 0 ? QVariantMap() : m_notes[index].toMap();
    const auto now = QDateTime::currentSecsSinceEpoch();
    if (index < 0) { note["first"] = now; note["id"] = identity; }
    note["last"] = now; note["frequency"] = frequency; note["protocol"] = protocol; note["confirmed"] = confirmed;
    note["tone"] = health.value("tone");
    if (active) { note["talkgroup"] = value(value("slot1CallState").toInt() == 2 ? "slot1TgId" : "slot2TgId");
        note["radio"] = value(value("slot1CallState").toInt() == 2 ? "slot1SrcText" : "slot2SrcText"); }
    if (value("siteConfirmed").toBool()) { note["site"] = value("siteLine"); note["color"] = value("dmrColorCode"); }
    if (index >= 0) m_notes.removeAt(index);
    m_notes.prepend(note); while (m_notes.size() > 500) m_notes.removeLast();
}
void ReceiverAssistant::persistNotes() { json_store_save_array("discoveries.json", QJsonArray::fromVariantList(m_notes)); }
void ReceiverAssistant::clearDiscoveries() { m_notes.clear(); persistNotes(); Q_EMIT discoveriesChanged(); }
bool ReceiverAssistant::saveDiscovery(int index) {
    if (!m_systems || index < 0 || index >= m_notes.size()) return false;
    const auto note = m_notes[index].toMap();
    // A discovery is a listening preset, never an invented trunking definition.
    return m_systems->add({{"name", tr("Discovery %1 MHz").arg(note.value("frequency").toDouble() / 1e6, 0, 'f', 5)},
        {"sourceType", "usb"}, {"freqMhz", QString::number(note.value("frequency").toDouble() / 1e6, 'f', 6)},
        {"decodeFlag", note.value("confirmed").toBool() ? "-fa" : "-fA"}, {"trunking", false}});
}
QString ReceiverAssistant::exportDiscoveries(const QString& url) const { return writeJson(url, QJsonDocument(QJsonArray::fromVariantList(m_notes))); }
QVariantMap ReceiverAssistant::filter(double frequency) const {
    for (const auto& value : m_filters) if (value.toMap().value("frequency").toDouble() == frequency) return value.toMap();
    return {{"ctcss", 0}, {"dcs", -1}, {"inverse", false}, {"color", -1}, {"slot", 0}, {"talkgroup", 0}};
}
QString ReceiverAssistant::saveFilter(double frequency, const QVariantMap& input) {
    bool validTone, validDcs, validColor, validSlot, validTg;
    const double tone = input.value("ctcss").toDouble(&validTone);
    const int dcs = input.value("dcs").toInt(&validDcs), color = input.value("color").toInt(&validColor), slot = input.value("slot").toInt(&validSlot);
    const auto tg = input.value("talkgroup").toLongLong(&validTg);
    if (!std::isfinite(frequency) || frequency < 24000000 || frequency > 1800000000 || std::floor(frequency) != frequency
        || !validTone || !std::isfinite(tone) || (tone != 0 && (tone < 60 || tone > 260))
        || !validDcs || dcs < -1 || dcs > 511 || (tone > 0 && dcs >= 0) || !validColor || color < -1 || color > 15
        || !validSlot || slot < 0 || slot > 2 || !validTg || tg < 0 || tg > 16777215) return tr("Check the frequency, tone, color code, slot and talkgroup.");
    auto updated = m_filters;
    for (int i = updated.size() - 1; i >= 0; --i) if (updated[i].toMap().value("frequency").toDouble() == frequency) updated.removeAt(i);
    if (updated.size() >= 500) return tr("The filter limit is 500 channels.");
    updated.append(QVariantMap{{"frequency", frequency}, {"ctcss", tone}, {"dcs", dcs}, {"inverse", input.value("inverse").toBool()},
        {"color", color}, {"slot", slot}, {"talkgroup", tg}});
    if (!json_store_save_array("receiver_filters.json", QJsonArray::fromVariantList(updated))) return tr("Could not save filters.");
    m_filters = updated; publishFilters(); Q_EMIT changed(); return {};
}
void ReceiverAssistant::clearFilter(double frequency) {
    auto updated = m_filters;
    for (int i = updated.size() - 1; i >= 0; --i) if (updated[i].toMap().value("frequency").toDouble() == frequency) updated.removeAt(i);
    if (json_store_save_array("receiver_filters.json", QJsonArray::fromVariantList(updated))) { m_filters = updated; publishFilters(); Q_EMIT changed(); }
}
void ReceiverAssistant::publishFilters() {
    QVector<dsd_receiver_filter> rules;
    for (const auto& value : m_filters) { const auto r = value.toMap(); rules.append({r.value("frequency").toULongLong(), r.value("ctcss").toDouble(),
        r.value("dcs", -1).toInt(), r.value("inverse").toBool(), r.value("color", -1).toInt(), r.value("slot").toInt(), r.value("talkgroup").toUInt()}); }
    dsd_receiver_filters_set(rules.constData(), size_t(rules.size()));
}
QVariantMap ReceiverAssistant::prepareCapture(const QVariantMap& system, double frequency) {
    const auto source = system.value("sourceType").toString();
    if (!QStringList{"usb", "airspy", "rtltcp"}.contains(source) || frequency <= 0 || system.value("extraArgs").toString().contains("--iq-")) {
        m_status["captureText"] = tr("Use a live RTL-SDR or Airspy source without custom I/Q arguments."); Q_EMIT changed(); return {}; }
    if (!QDir().mkpath(captureDir()) || QStorageInfo(captureDir()).bytesAvailable() < 150 * 1024 * 1024) {
        m_status["captureText"] = tr("At least 150 MB of free storage is needed."); Q_EMIT changed(); return {}; }
    cancelGain(true); setAutoGain(false); setRoaming(false);
    const auto file = captureDir() + "/signal-" + QDateTime::currentDateTimeUtc().toString("yyyyMMdd-HHmmss-zzz") + ".iq";
    auto result = system; result["freqMhz"] = QString::number(frequency / 1e6, 'f', 6); result["trunking"] = false;
    result["iqCapturePath"] = file;
    m_status["capturing"] = true; m_status["canCapture"] = false;
    m_status["captureText"] = tr("Capturing up to 20 seconds or 64 MB. Reception briefly restarts."); Q_EMIT changed(); return result;
}
void ReceiverAssistant::captureFinished() { m_status["capturing"] = false; m_status["captureText"] = tr("Capture stopped. Export both I/Q and metadata together."); Q_EMIT capturesChanged(); Q_EMIT changed(); }
QVariantList ReceiverAssistant::captures() const {
    QVariantList result;
    const auto files = QDir(captureDir()).entryInfoList({"*.iq.json"}, QDir::Files, QDir::Time);
    for (const auto& f : files) { const QString data = f.absoluteFilePath().chopped(5); if (!QFileInfo(data).exists()) continue;
        result.append(QVariantMap{{"name", f.fileName().chopped(5)}, {"path", data}, {"metadata", f.absoluteFilePath()}, {"bytes", QFileInfo(data).size()}}); }
    return result;
}
QString ReceiverAssistant::exportCapture(int index, const QString& folder) const {
    const auto rows = captures(); if (index < 0 || index >= rows.size()) return tr("Capture no longer available.");
    if (m_host && m_host->property("sessionActive").toBool()) return tr("Stop reception before exporting a capture.");
    const auto row = rows[index].toMap();
    QFile output(path(folder));
    if (!output.open(QIODevice::WriteOnly | QIODevice::Truncate)) return output.errorString();
    // POSIX ustar: one portable archive, streamed in bounded chunks, with both native files intact.
    for (const auto& key : {"path", "metadata"}) {
        QFile input(row.value(key).toString());
        if (!input.open(QIODevice::ReadOnly)) return input.errorString();
        QByteArray header(512, '\0');
        const auto name = QFileInfo(input.fileName()).fileName().toUtf8();
        if (name.size() >= 100) return tr("Capture filename is too long.");
        std::copy(name.begin(), name.end(), header.begin());
        auto octal = [&](int offset, int size, quint64 value) {
            const auto digits = QByteArray::number(value, 8).rightJustified(size - 1, '0');
            std::copy(digits.begin(), digits.end(), header.begin() + offset);
        };
        octal(100, 8, 0600); octal(108, 8, 0); octal(116, 8, 0);
        octal(124, 12, input.size()); octal(136, 12, QFileInfo(input.fileName()).lastModified().toSecsSinceEpoch());
        std::fill(header.begin() + 148, header.begin() + 156, ' '); header[156] = '0';
        header.replace(257, 6, QByteArray("ustar\0", 6)); header.replace(263, 2, "00");
        unsigned checksum = 0; for (auto byte : header) checksum += static_cast<unsigned char>(byte);
        octal(148, 7, checksum); header[155] = ' ';
        if (output.write(header) != header.size()) return output.errorString();
        qint64 left = input.size();
        while (left > 0) {
            const auto block = input.read(std::min<qint64>(left, 65536));
            if (block.isEmpty() || output.write(block) != block.size()) return tr("Could not finish the capture export.");
            left -= block.size();
        }
        const QByteArray padding((512 - input.size() % 512) % 512, '\0');
        if (output.write(padding) != padding.size()) return output.errorString();
    }
    if (output.write(QByteArray(1024, '\0')) != 1024 || !output.flush()) return output.errorString();
    return {};
}
}
