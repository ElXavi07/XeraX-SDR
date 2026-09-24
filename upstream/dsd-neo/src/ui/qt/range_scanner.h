// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QObject>
#include <QPointer>
#include <QTimer>
#include <QElapsedTimer>
#include <QVariantMap>
#include <QSet>
#include <QVector>
#include "range_scan_math.h"
namespace dsd_qt {
class SavedSystemsModel;
class RangeScanner: public QObject {
    Q_OBJECT
    Q_PROPERTY(bool active READ active NOTIFY changed)
    Q_PROPERTY(QVariantMap settings READ settings NOTIFY changed)
    Q_PROPERTY(QVariantMap status READ status NOTIFY changed)
    Q_PROPERTY(QVariantList hits READ hits NOTIFY hitsChanged)
public:
    explicit RangeScanner(QObject* parent=nullptr);
    ~RangeScanner() override;
    void configure(QObject* metrics,QObject* commands,QObject* host,QObject* spectrum,
                   QObject* tools,QObject* assistant,QObject* expansion,SavedSystemsModel* systems);
    bool active() const { return m_active; }
    QVariantMap settings() const { return m_settings; }
    QVariantMap status() const { return m_status; }
    QVariantList hits() const { return m_hits; }
    Q_INVOKABLE QString validate(const QVariantMap&) const;
    Q_INVOKABLE QString saveSettings(const QVariantMap&);
    Q_INVOKABLE QString start(const QVariantMap&);
    Q_INVOKABLE void stop();
    Q_INVOKABLE void hold(bool);
    Q_INVOKABLE void skip();
    Q_INVOKABLE void avoid();
    Q_INVOKABLE void clearAvoids();
    Q_INVOKABLE bool saveHit(int index);
    Q_INVOKABLE bool saveFrequency(unsigned int frequency);
    Q_INVOKABLE void setSession(const QVariantMap&);
    Q_INVOKABLE void poll();
Q_SIGNALS:
    void changed();
    void hitsChanged();
    void restartRequested(const QVariantMap& system);
protected:
    struct Frame { QVector<float> bins; uint32_t center=0,span=0,serial=0; };
    virtual Frame readFrame() const;
    virtual qint64 nowMs() const;
    virtual quint64 pcmFrames() const;
    virtual void gateAudio(bool quiet);
private:
    QVariant value(const char*) const;
    QString readiness() const;
    bool command(const char*,unsigned int);
    bool modeCommand(int);
    void own(bool);
    void finish(const QString&);
    void tune(uint32_t,bool candidate);
    void nextTile(uint32_t span);
    void nextCandidate();
    void noteHit(double,const QString&,bool);
    void publish();
    QPointer<QObject> m_metrics,m_commands,m_host,m_spectrum,m_tools,m_assistant,m_expansion;
    QPointer<SavedSystemsModel> m_systems;
    QTimer m_timer;
    QElapsedTimer m_clock;
    QVariantMap m_settings,m_status,m_session,m_pending;
    QVariantList m_hits;
    xerax::range_scan::Plan m_plan;
    xerax::range_scan::Tile m_tile;
    QVector<uint32_t> m_candidates;
    QSet<uint32_t> m_avoids;
    QVector<int> m_votes;
    bool m_active=false,m_held=false,m_candidate=false,m_tuning=false,m_modeReady=false;
    bool m_analog=false,m_everActive=false;
    int m_mode=0,m_nextIndex=0,m_pass=0,m_seenFrames=0,m_observations=0;
    int m_settle=160,m_probeFrames=2,m_acquire=2500,m_tail=1200,m_maxVisit=15000;
    double m_threshold=10;
    uint32_t m_expected=0,m_lastSerial=0,m_span=0;
    quint64 m_lastPcm=0;
    qint64 m_started=0,m_requested=0,m_landed=0,m_lastFrame=0,m_lastActive=0,m_pendingAt=0;
    QString m_phase,m_message;
    qint64 m_published=-1000,m_hitsPublished=-1000;
    bool m_hitsDirty=false;
};
}
