// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QObject>
#include <QByteArray>
#ifdef Q_OS_WIN
#include <QHash>
#include <QPointer>
class QNetworkAccessManager;
class QNetworkReply;
#endif
namespace dsd_qt {
class AiTransport : public QObject {
    Q_OBJECT
public:
#ifdef Q_OS_WIN
    explicit AiTransport(QObject* parent=nullptr,QNetworkAccessManager* network=nullptr);
#else
    using QObject::QObject;
#endif
    virtual void send(quint64 id, const QString& provider, const QString& path, const QString& key, const QByteArray& body);
    virtual void cancel(quint64 id);
    virtual QString loadKey(const QString& provider);
    virtual bool saveKey(const QString& provider, const QString& key);
Q_SIGNALS:
    void completed(quint64 id, int status, const QByteArray& body);
#ifdef Q_OS_WIN
private:
    QNetworkAccessManager* m_network;
    QHash<quint64,QPointer<QNetworkReply>> m_replies;
#endif
};
}
