// SPDX-License-Identifier: GPL-3.0-or-later
#include "app_language.h"
#include <QQmlEngine>
#include <QCoreApplication>
#include <QSettings>
#include <QLocale>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#ifdef Q_OS_ANDROID
#include <QJniObject>
#endif
namespace dsd_qt {
AppLanguage::AppLanguage(QQmlEngine* engine, const QString& catalog) : QTranslator(engine), m_engine(engine) {
    QFile file(catalog);
    if (file.open(QIODevice::ReadOnly)) {
        const auto entries = QJsonDocument::fromJson(file.readAll()).object();
        for (auto it = entries.begin(); it != entries.end(); ++it) m_spanish.insert(it.key(), it.value().toString());
    }
    m_language = QSettings().value("ui/language", QLocale::system().language() == QLocale::Spanish ? "es" : "en").toString();
    QCoreApplication::installTranslator(this);
#ifdef Q_OS_ANDROID
    const auto context = QNativeInterface::QAndroidApplication::context();
    QJniObject::callStaticMethod<void>("io/github/arancormonk/dsdneo/ReceiverExtras", "initialize", "(Landroid/content/Context;)V", context.object());
    QJniObject::callStaticMethod<void>("io/github/arancormonk/dsdneo/ReceiverExtras", "setLanguage", "(Ljava/lang/String;)V", QJniObject::fromString(m_language).object());
#endif
}
AppLanguage::~AppLanguage() { QCoreApplication::removeTranslator(this); }
void AppLanguage::setLanguage(const QString& lang) {
    if ((lang != "en" && lang != "es") || lang == m_language) return;
    m_language = lang; QSettings().setValue("ui/language", lang);
#ifdef Q_OS_ANDROID
    QJniObject::callStaticMethod<void>("io/github/arancormonk/dsdneo/ReceiverExtras", "setLanguage", "(Ljava/lang/String;)V", QJniObject::fromString(lang).object());
#endif
    if (m_engine) m_engine->retranslate();
    Q_EMIT changed();
}
QString AppLanguage::translate(const char*, const char* source, const char*, int) const {
    return m_language == "es" && source ? m_spanish.value(QString::fromUtf8(source)) : QString();
}
QString AppLanguage::text(const QString& source) const { return m_language == "es" ? m_spanish.value(source, source) : source; }
}
