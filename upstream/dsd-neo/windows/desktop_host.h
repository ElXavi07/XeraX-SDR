// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "decoder_host.h"
#include <QThread>
#include <atomic>
#include "run_status.h"

class DesktopHost final : public dsd_qt::DecoderHost {
    Q_OBJECT
public:
    explicit DesktopHost(QObject* parent=nullptr);
    ~DesktopHost() override;
    bool isRunning() const override { return m_state==Running; }
    bool desktopBuild() const override { return true; }
    bool signalsSessionInitialized() const override { return true; }
    SessionState sessionState() const override { return m_state; }
    QString statusText() const override;
    QString failureText() const override { return m_error; }
    int inputFailureKind() const override { return m_result.input_failure.kind; }
    int inputFailureCode() const override { return m_result.input_failure.native_code; }
    int terminalReason() const override { return m_result.reason; }
    QString audioRoute() const override;
    QVariantMap audioOutput() const override;
    QVariantMap decoderHardware() const override { return m_hardware; }
    bool selectAudioOutput(const QString& key) override;
    Q_INVOKABLE bool start(const QStringList&) override;
    Q_INVOKABLE void stop() override;
private:
    void changeState(SessionState state);
    QThread* m_thread=nullptr;
    QVariantMap m_hardware;
    SessionState m_state=Idle;
    QString m_error;
    std::atomic<bool> m_stop{false};
    dsd_android::RunStatus m_result;
};
