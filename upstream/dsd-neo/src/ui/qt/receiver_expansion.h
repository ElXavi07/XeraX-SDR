// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QObject>
#include <QTimer>
#include <QVariant>
#include <QElapsedTimer>
#include <dsd-neo/platform/reception_sample.h>
namespace dsd_qt {
class DecoderHost; class SavedSystemsModel; class SessionArgsBuilder;
class ReceiverExpansion:public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantMap status READ status NOTIFY changed)
    Q_PROPERTY(QVariantList lanes READ lanes NOTIFY changed)
    Q_PROPERTY(QVariantList reports READ reports NOTIFY changed)
    Q_PROPERTY(QVariantList receptionReports READ receptionReports NOTIFY changed)
    Q_PROPERTY(QVariantList nearby READ nearby NOTIFY changed)
    Q_PROPERTY(QVariantList survey READ survey NOTIFY changed)
    Q_PROPERTY(QVariantList devices READ devices NOTIFY changed)
public:
    explicit ReceiverExpansion(QObject* parent=nullptr);
    ~ReceiverExpansion() override;
    void configure(QObject* metrics,QObject* commands,DecoderHost*,SavedSystemsModel*,SessionArgsBuilder*);
    QVariantMap status() const { return m_status; }
    QVariantList lanes() const { return m_lanes; }
    QVariantList reports() const { return m_reports; }
    QVariantList receptionReports() const { return m_receptionReports; }
    Q_INVOKABLE QString startReceptionSample(const QString& label);
    Q_INVOKABLE void cancelReceptionSample();
    QVariantList nearby() const { return m_nearby; }
    QVariantList survey() const { return m_survey; }
    QVariantList devices() const;
    Q_INVOKABLE void setSession(const QVariantMap&);
    Q_INVOKABLE QString startSiteCapture(const QString& frequencies);
    Q_INVOKABLE void stopSiteCapture();
    Q_INVOKABLE void autoSiteAudio();
    Q_INVOKABLE QString startChannel(int lane,double mhz,const QString& flag,const QString& device=QString());
    Q_INVOKABLE void stopChannel(int lane);
    Q_INVOKABLE void listen(int lane);
    Q_INVOKABLE QString startDual(const QString& device);
    Q_INVOKABLE void stopDual();
    Q_INVOKABLE bool requestDevice(const QString& id);
    Q_INVOKABLE void setEqualizer(bool enabled);
    Q_INVOKABLE void setRasReception(bool enabled);
    Q_INVOKABLE void setNxdnSearch(bool enabled);
    Q_INVOKABLE bool setTwoTone(double a,double b,int aMs,int bMs);
    Q_INVOKABLE void setRecovery(bool enabled);
    Q_INVOKABLE QVariantMap restoredSession() const;
    Q_INVOKABLE QString runLab();
    Q_INVOKABLE QString reprocess(const QString& metadata,const QString& flag);
    Q_INVOKABLE void stopTrials();
    Q_INVOKABLE QString exportReports(const QString& url);
    Q_INVOKABLE void locate(bool live);
    Q_INVOKABLE void setRadius(double miles);
    Q_INVOKABLE void setGeoScan(bool enabled);
    Q_INVOKABLE QString startSurvey(double firstMhz,double lastMhz,double stepKhz,int dwellSeconds);
    Q_INVOKABLE void stopSurvey();
    Q_INVOKABLE bool saveSurvey(int index);
    Q_INVOKABLE bool tuneSurvey(int index);
    Q_INVOKABLE void poll();
Q_SIGNALS:
    void changed();
    void selectSite(const QString& uid);
    void captureRestored();
    void restartRequested(const QVariantMap& system);
private:
    QVariant value(const char*) const;
    bool startWorker(int,const QStringList&,const QString& device=QString());
    bool tuningAllowed() const;
    bool tune(double hz);
    void rankSites();
    void nextTrial();
    xerax::ReceptionReading receptionReading() const;
    xerax::ReceptionSample m_reception;
    QString m_receptionLabel;
    QVariantList m_receptionReports;
    QObject *m_metrics=nullptr,*m_commands=nullptr;
    DecoderHost* m_host=nullptr;
    SavedSystemsModel* m_systems=nullptr;
    SessionArgsBuilder* m_args=nullptr;
    QVariantMap m_status,m_session;
    QVariantList m_lanes,m_reports,m_nearby,m_survey,m_trials;
    QVariantMap m_trial,m_siteOriginal;
    bool m_siteStarted=false;
    QTimer m_timer;
    QElapsedTimer m_clock;
    double m_lat=33.7206,m_lon=-116.2156,m_accuracy=0,m_radius=50;
    bool m_gps=false,m_geo=false,m_surveying=false;
    qint64 m_fix=0,m_locationRequest=0,m_lastLocate=0,m_lastSwitch=0,m_terminalAt=0;
    QString m_lastSite;
    int m_dwell=3,m_surveyIndex=0,m_surveyTicks=0,m_surveyWait=0;
    double m_originalFrequency=0;
    quint64 m_good=0;
    qint64 m_captureRestored=-1;
};
}
