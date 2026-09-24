// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "ai_transport.h"
#include <QJsonArray>
#include <QJsonObject>
#include <QTimer>
#include <QElapsedTimer>
#include <QVariant>
#include <QPointer>
namespace dsd_qt {
class AiReceiver : public QObject {
    Q_OBJECT
    Q_PROPERTY(bool enabled READ enabled WRITE setEnabled NOTIFY changed)
    Q_PROPERTY(QString provider READ provider WRITE setProvider NOTIFY changed)
    Q_PROPERTY(QString model READ model WRITE setModel NOTIFY changed)
    Q_PROPERTY(QStringList models READ models NOTIFY changed)
    Q_PROPERTY(bool hasKey READ hasKey NOTIFY changed)
    Q_PROPERTY(bool busy READ busy NOTIFY changed)
    Q_PROPERTY(bool verified READ verified NOTIFY changed)
    Q_PROPERTY(QString status READ status NOTIFY changed)
    Q_PROPERTY(QString answer READ answer NOTIFY changed)
    Q_PROPERTY(QVariantList events READ events NOTIFY changed)
    Q_PROPERTY(int requestsToday READ requestsToday NOTIFY changed)
    Q_PROPERTY(int dailyLimit READ dailyLimit WRITE setDailyLimit NOTIFY changed)
    Q_PROPERTY(qint64 tokensToday READ tokensToday NOTIFY changed)
    Q_PROPERTY(QVariantList captures READ captures NOTIFY changed)
public:
    explicit AiReceiver(QObject* parent=nullptr,AiTransport* transport=nullptr);
    ~AiReceiver() override;
    void configure(QObject* metrics,QObject* host,QObject* tools,QObject* assistant,QObject* expansion,QObject* language);
    bool enabled() const { return m_enabled; } void setEnabled(bool);
    QString provider() const { return m_provider; } void setProvider(const QString&);
    QString model() const { return m_model; } void setModel(const QString&);
    QStringList models() const { return m_models; }
    bool hasKey() const { return !m_key.isEmpty(); }
    bool busy() const { return !m_operation.isEmpty(); }
    bool verified() const { return m_verified; }
    QString status() const { return m_status; } QString answer() const { return m_answer; }
    QVariantList events() const { return m_events; }
    int requestsToday() const; qint64 tokensToday() const;
    int dailyLimit() const { return m_dailyLimit; } void setDailyLimit(int);
    QVariantList captures() const;
    Q_INVOKABLE void connectKey(const QString& key);
    Q_INVOKABLE void refreshModels();
    Q_INVOKABLE void forgetKey();
    Q_INVOKABLE void checkModel();
    Q_INVOKABLE void ask(const QString& goal,bool experiments,int captureIndex=-1);
    Q_INVOKABLE void cancel();
    Q_INVOKABLE void clearConversation();
    Q_INVOKABLE void refreshLocal();
    Q_INVOKABLE void poll();
    QJsonObject diagnostics() const;
Q_SIGNALS:
    void changed();
protected:
    virtual qint64 nowMs() const { return m_clock.elapsed(); }
private:
    void finished(quint64,int,const QByteArray&);
    void send(const QString& path,const QJsonObject& body={});
    void nextRequest(); void nextTool(); void toolDone(const QJsonObject&);
    void stopOwnedTools(); void fail(const QString&); void log(const QString&);
    void resetDay(); bool ready(); bool receiverEligible() const;
    QString instructions() const;
    QJsonArray sanitizedReports(const char* property,int maximum,const QString& runId={}) const;
    AiTransport* m_transport;
    QPointer<QObject> m_metrics,m_host,m_tools,m_assistant,m_expansion,m_language;
    QString m_provider="openai",m_model,m_key,m_status,m_answer,m_operation,m_waiting,m_day;
    QStringList m_models;
    QJsonArray m_history,m_pending;
    QJsonObject m_current;
    QVariantList m_events,m_captureSnapshot;
    bool m_enabled=false,m_verified=false,m_experiments=false,m_ownGain=false,m_ownSample=false,m_ownLab=false;
    int m_dailyLimit=25,m_requests=0,m_round=0,m_actions=0,m_captureIndex=-1,m_gainCompleted=0,m_gainGeneration=0;
    QString m_sampleRunId,m_labRunId;
    qint64 m_tokens=0,m_waitStarted=0; double m_frequency=0;
    quint64 m_ticket=0,m_generation=0;
    QVariantMap m_firstReport;
    QTimer m_timer; QElapsedTimer m_clock;
};
}
