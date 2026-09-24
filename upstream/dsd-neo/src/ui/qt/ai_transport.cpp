// SPDX-License-Identifier: GPL-3.0-or-later
#include "ai_transport.h"
#include <QJsonDocument>
#include <QJsonObject>
#include <QThread>
#include <QTimer>
#ifdef Q_OS_ANDROID
#include <QJniObject>
#include <QJniEnvironment>
#include <QCoreApplication>
#include <QGuiApplication>
#endif
namespace dsd_qt {
#ifdef Q_OS_ANDROID
static constexpr auto bridge = "io/github/arancormonk/dsdneo/AiProviderBridge";
static bool clearJavaError() { QJniEnvironment env; if (!env->ExceptionCheck()) return false; env->ExceptionClear(); return true; }
#endif
void AiTransport::send(quint64 id, const QString& provider, const QString& path, const QString& key, const QByteArray& body) {
#ifdef Q_OS_ANDROID
    auto* job = QThread::create([id,provider,path,key,body]() {
        const auto result = QJniObject::callStaticObjectMethod(bridge,"request","(JLjava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;",
            jlong(id),QJniObject::fromString(provider).object(),QJniObject::fromString(path).object(),
            QJniObject::fromString(key).object(),QJniObject::fromString(QString::fromUtf8(body)).object());
        const bool failed = clearJavaError();
        QThread::currentThread()->setProperty("result",failed ? QByteArray() : result.toString().toUtf8());
    });
    connect(job,&QThread::finished,this,[this,job,id] {
        const auto result=QJsonDocument::fromJson(job->property("result").toByteArray()).object();
        Q_EMIT completed(id,result.value("status").toInt(),result.value("body").toString().toUtf8());
    });
    connect(job,&QThread::finished,job,&QObject::deleteLater);
    job->start(QThread::LowPriority);
#else
    Q_UNUSED(provider); Q_UNUSED(path); Q_UNUSED(key); Q_UNUSED(body);
    QTimer::singleShot(0,this,[this,id] { Q_EMIT completed(id,0,{}); });
#endif
}
void AiTransport::cancel(quint64 id) {
#ifdef Q_OS_ANDROID
    QJniObject::callStaticMethod<void>(bridge,"cancel","(J)V",jlong(id)); clearJavaError();
#else
    Q_UNUSED(id);
#endif
}
QString AiTransport::loadKey(const QString& provider) {
#ifdef Q_OS_ANDROID
    const auto key=QJniObject::callStaticObjectMethod(bridge,"loadKey","(Landroid/content/Context;Ljava/lang/String;)Ljava/lang/String;",
        QNativeInterface::QAndroidApplication::context().object(),QJniObject::fromString(provider).object());
    if(clearJavaError()) return {};
    return key.toString();
#else
    Q_UNUSED(provider); return {};
#endif
}
bool AiTransport::saveKey(const QString& provider,const QString& key) {
#ifdef Q_OS_ANDROID
    const bool saved=QJniObject::callStaticMethod<jboolean>(bridge,"saveKey","(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;)Z",
        QNativeInterface::QAndroidApplication::context().object(),QJniObject::fromString(provider).object(),QJniObject::fromString(key).object());
    return !clearJavaError() && saved;
#else
    Q_UNUSED(provider); Q_UNUSED(key); return false;
#endif
}
}
