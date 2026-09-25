// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QObject>
#include <QVariant>
#include <QTimer>
#include <QElapsedTimer>
#include <QVector>
namespace dsd_qt {
class SavedSystemsModel;
class ReceiverAssistant : public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantMap status READ status NOTIFY changed)
    Q_PROPERTY(QVariantList discoveries READ discoveries NOTIFY discoveriesChanged)
    Q_PROPERTY(QVariantList captures READ captures NOTIFY capturesChanged)
    Q_PROPERTY(bool autoGain READ autoGain WRITE setAutoGain NOTIFY changed)
    Q_PROPERTY(bool roaming READ roaming WRITE setRoaming NOTIFY changed)
    Q_PROPERTY(bool notebook READ notebook WRITE setNotebook NOTIFY changed)
  public:
    explicit ReceiverAssistant(QObject* parent = nullptr);
    ~ReceiverAssistant() override;
    void configure(QObject* metrics, QObject* commands, QObject* host, QObject* tools, SavedSystemsModel* systems);
    QVariantMap status() const { return m_status; }
    QVariantList discoveries() const { return m_notes; }
    QVariantList captures() const;
    bool autoGain() const { return m_autoGain; }
    bool roaming() const { return m_roaming; }
    bool notebook() const { return m_notebook; }
    void setAutoGain(bool);
    void setRoaming(bool);
    void setNotebook(bool);
    Q_INVOKABLE void setSession(const QString& uid, bool scanning);
    Q_INVOKABLE QVariantMap filter(double frequency) const;
    Q_INVOKABLE QString saveFilter(double frequency, const QVariantMap& rule);
    Q_INVOKABLE void clearFilter(double frequency);
    Q_INVOKABLE void clearDiscoveries();
    Q_INVOKABLE bool saveDiscovery(int index);
    Q_INVOKABLE QString exportDiscoveries(const QString& url) const;
    Q_INVOKABLE QString exportDiagnostics(const QString& url) const;
    Q_INVOKABLE QVariantMap prepareCapture(const QVariantMap& system, double frequency);
    Q_INVOKABLE void captureFinished();
    Q_INVOKABLE QString exportCapture(int index, const QString& folder) const;
    Q_INVOKABLE void poll();
    // Pure scoring shared by gain and roaming; invalid evidence never becomes a success score.
    static double score(int ok, int bad, double snr, bool snrValid, double clip, bool clipValid, bool analog);
  Q_SIGNALS:
    void changed();
    void discoveriesChanged();
    void capturesChanged();
    void switchSite(const QString& uid);
    void captureRequested();
    void finishCaptureRequested();
    void retryRequested();
  protected:
    virtual qint64 nowMs() const { return m_clock.elapsed(); }
  private:
    QVariant value(const char*) const;
    bool commandGain(int gain);
    void publishFilters();
    void persistNotes();
    void cancelGain(bool restore);
    void observeNotebook(bool live, bool stable, bool active, double frequency);
    void observeGain(bool eligible, bool active, bool analog, double frequency);
    void observeSites(bool live, bool active);
    QObject *m_metrics = nullptr, *m_commands = nullptr, *m_host = nullptr, *m_tools = nullptr;
    SavedSystemsModel* m_systems = nullptr;
    QTimer m_timer;
    QElapsedTimer m_clock;
    QVariantMap m_status;
    QVariantList m_notes, m_filters;
    QString m_uid, m_trialUid, m_originUid, m_noteIdentity;
    bool m_scanning = false, m_autoGain = false, m_roaming = false, m_notebook = false;
    bool m_wasLive = false, m_synced = false;
    bool m_resetMetricsPending = false;
    int m_decodeMode = -1;
    double m_frequency = 0;
    quint64 m_prevOk = 0, m_prevBad = 0, m_gapBase = 0, m_frames = 0;
    int m_syncLosses = 0, m_noteStreak = 0, m_silent = 0, m_flush = 0;
    int m_gainPhase = 0, m_gainTicks = 0, m_originalGain = 0, m_trialGain = 0;
    double m_gainFrequency = 0, m_baseScore = -1;
    int m_good = 0, m_bad = 0, m_nSnr = 0, m_nClip = 0;
    double m_sumSnr = 0, m_sumClip = 0;
    qint64 m_gainCooldown = 0, m_siteCooldown = 0, m_siteDeadline = 0;
    int m_weakTicks = 0, m_candidateIndex = 0;
    double m_originScore = -1;
    QVector<QVariantMap> m_window;
};
}
