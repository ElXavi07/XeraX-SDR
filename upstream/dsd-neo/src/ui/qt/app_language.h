// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QTranslator>
#include <QHash>
class QQmlEngine;
namespace dsd_qt {
class AppLanguage : public QTranslator {
    Q_OBJECT
    Q_PROPERTY(QString language READ language WRITE setLanguage NOTIFY changed)
  public:
    explicit AppLanguage(QQmlEngine* engine, const QString& catalog = ":/dsdneo/i18n/es.json");
    ~AppLanguage() override;
    QString language() const { return m_language; }
    void setLanguage(const QString&);
    QString translate(const char*, const char*, const char* = nullptr, int = -1) const override;
    bool isEmpty() const override { return false; }
    Q_INVOKABLE QString text(const QString& source) const;
  Q_SIGNALS:
    void changed();
  private:
    QQmlEngine* m_engine;
    QString m_language;
    QHash<QString, QString> m_spanish;
};
}
