// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QObject>
#include <QByteArray>
namespace dsd_qt {
class AiTransport : public QObject {
    Q_OBJECT
public:
    using QObject::QObject;
    virtual void send(quint64 id, const QString& provider, const QString& path, const QString& key, const QByteArray& body);
    virtual void cancel(quint64 id);
    virtual QString loadKey(const QString& provider);
    virtual bool saveKey(const QString& provider, const QString& key);
Q_SIGNALS:
    void completed(quint64 id, int status, const QByteArray& body);
};
}
