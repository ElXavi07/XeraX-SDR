// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QObject>
#include <QVariant>
#include <QTimer>
namespace dsd_qt {
class CallLibrary:public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantList calls READ calls NOTIFY changed)
    Q_PROPERTY(bool recording READ recording WRITE setRecording NOTIFY changed)
    Q_PROPERTY(QString query READ query WRITE setQuery NOTIFY changed)
    Q_PROPERTY(int retentionDays READ retentionDays WRITE setRetentionDays NOTIFY changed)
    Q_PROPERTY(qint64 bytes READ bytes NOTIFY changed)
public:
    explicit CallLibrary(QObject* parent=nullptr);
    QVariantList calls() const;
    bool recording() const;
    void setRecording(bool);
    QString query() const { return m_query; }
    void setQuery(const QString&);
    int retentionDays() const;
    void setRetentionDays(int);
    qint64 bytes() const { return m_bytes; }
    Q_INVOKABLE void refresh();
    Q_INVOKABLE bool favorite(const QString& id,bool value);
    Q_INVOKABLE QString play(const QString& id);
    Q_INVOKABLE QString exportCall(const QString& id,const QString& directory);
    Q_INVOKABLE bool remove(const QString& id);
    static QString directory();
    static QStringList recordingArgs(const QString& lane=QStringLiteral("main"));
Q_SIGNALS:
    void changed();
private:
    QString safePath(const QString& id) const;
    QVariantList m_calls;
    QString m_query;
    qint64 m_bytes=0;
    QTimer m_timer;
};
}
