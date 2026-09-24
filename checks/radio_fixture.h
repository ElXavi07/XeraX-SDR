// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QObject>
#include <QQmlPropertyMap>
#include <QQmlComponent>
#include <QQmlEngine>
#include "decode_mode_flag.h"
#include "session_args.h"

// Commands stop at the hardware boundary; UI, frequency mapping and gestures
// use production QML and the real spectrum model against a synthetic RF frame.
class RadioFixture : public QObject {
    Q_OBJECT
    Q_PROPERTY(int tuneCount MEMBER tuneCount NOTIFY changed)
    Q_PROPERTY(double lastTune MEMBER lastTune NOTIFY changed)
    Q_PROPERTY(int decodeCount MEMBER decodeCount NOTIFY changed)
    Q_PROPERTY(bool acceptTune MEMBER acceptTune NOTIFY changed)
public:
    using QObject::QObject;
    QQmlPropertyMap* metrics = nullptr;
    int tuneCount = 0, decodeCount = 0;
    double lastTune = 0;
    bool acceptTune = true;
    Q_INVOKABLE bool manualTuneHz(uint hz) {
        ++tuneCount; lastTune = hz; Q_EMIT changed(); return acceptTune;
    }
    Q_INVOKABLE int decodeModeForFlag(const QString& flag) const { return dsd_qt::decode_mode_for_flag(flag); }
    Q_INVOKABLE bool setDecodeMode(int) { ++decodeCount; Q_EMIT changed(); return true; }
    Q_INVOKABLE void setRangeScanOwned(bool) {}
    Q_INVOKABLE bool rangeDecodeMode(int n) {metrics->insert("decodeMode",n);return setDecodeMode(n);}
    Q_INVOKABLE bool rangeTuneHz(unsigned int hz) {return manualTuneHz(hz);}
    Q_INVOKABLE bool setModulation(int) { return true; }
    Q_INVOKABLE bool setTunerGain(int) { return true; }
    Q_INVOKABLE bool setPpm(int) { return acceptTune; }
    Q_INVOKABLE bool setAutoPpm(bool) { return acceptTune; }
    Q_INVOKABLE bool setSquelchDb(double) { return true; }
    Q_INVOKABLE bool setTrunking(bool) { return true; }
    Q_INVOKABLE QStringList startupArgs(const QVariantMap& system) const {
        return dsd_qt::session_args_build(system, dsd_qt::SessionArgPrefs{}, nullptr);
    }
    Q_INVOKABLE QString shellCompileError() const {
        auto* engine = qobject_cast<QQmlEngine*>(parent());
        QQmlComponent shell(engine, QUrl::fromLocalFile(QStringLiteral(XERAX_QML_DIR "/Main.qml")), QQmlComponent::PreferSynchronous);
        return shell.isReady() ? QString() : shell.errorString();
    }
    Q_INVOKABLE void metric(const QString& key, const QVariant& value) { metrics->insert(key, value); }
    Q_INVOKABLE void reset() {
        tuneCount = decodeCount = 0; lastTune = 0; acceptTune = true;
        metrics->insert("tunerControlled", false);
        metrics->insert("decodeMode", decodeModeForFlag("-fs"));
        Q_EMIT changed();
    }
Q_SIGNALS:
    void changed();
};
