// SPDX-License-Identifier: GPL-3.0-or-later
#include "ai_transport.h"
#include "ai_protocol.h"
#include <QJsonDocument>
#include <QJsonObject>
#include <QThread>
#include <QTimer>
#ifdef Q_OS_WIN
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QSettings>
#include <windows.h>
#include <wincrypt.h>
#include <memory>
#endif
#ifdef Q_OS_ANDROID
#include <QJniObject>
#include <QJniEnvironment>
#include <QCoreApplication>
#include <QGuiApplication>
#endif
namespace dsd_qt {
#ifdef Q_OS_WIN
AiTransport::AiTransport(QObject* parent,QNetworkAccessManager* network):QObject(parent),m_network(network?network:new QNetworkAccessManager(this)) {}
#endif
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
#elif defined(Q_OS_WIN)
    const bool get=path=="/models" && body.isEmpty();
    const bool post=!body.isEmpty() && ((provider=="openai" && path=="/responses") || (provider=="deepseek" && path=="/chat/completions"));
    if(!ai::validProvider(provider) || !ai::validKey(key) || (!get && !post) || body.size()>100000 || m_replies.contains(id)) {
        QTimer::singleShot(0,this,[this,id] { Q_EMIT completed(id,0,{}); }); return;
    }
    QNetworkRequest request(QUrl((provider=="openai" ? "https://api.openai.com/v1" : "https://api.deepseek.com")+path));
    request.setRawHeader("Authorization","Bearer "+key.toUtf8());
    request.setHeader(QNetworkRequest::ContentTypeHeader,"application/json");
    request.setRawHeader("Accept","application/json");
    request.setAttribute(QNetworkRequest::RedirectPolicyAttribute,QNetworkRequest::ManualRedirectPolicy);
    request.setAttribute(QNetworkRequest::CookieLoadControlAttribute,QNetworkRequest::Manual);
    request.setAttribute(QNetworkRequest::CookieSaveControlAttribute,QNetworkRequest::Manual);
    request.setTransferTimeout(30000);
    auto* reply=get?m_network->get(request):m_network->post(request,body);
    m_replies.insert(id,reply);
    const auto response=std::make_shared<QByteArray>();
    reply->setReadBufferSize(1048577);
    connect(reply,&QNetworkReply::readyRead,this,[reply,response] {
        response->append(reply->read(1048577-response->size()));
        if(response->size()>1048576) { reply->setProperty("xeraxRejected",true); reply->abort(); }
    });
    auto* timeout=new QTimer(reply); timeout->setSingleShot(true); timeout->start(45000);
    connect(timeout,&QTimer::timeout,reply,[reply] { reply->setProperty("xeraxRejected",true); reply->abort(); });
    connect(reply,&QNetworkReply::finished,this,[this,reply,response,id,timeout] {
        timeout->stop(); m_replies.remove(id);
        response->append(reply->read(1048577-response->size()));
        int status=reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
        // Preserve HTTP errors for useful account/quota messages; never accept a
        // partial success after a TLS/network error or a body/timeout rejection.
        if(response->size()>1048576 || reply->property("xeraxRejected").toBool() ||
           (status>=200 && status<300 && reply->error()!=QNetworkReply::NoError)) status=0;
        reply->deleteLater(); Q_EMIT completed(id,status,status?*response:QByteArray());
    });
#else
    Q_UNUSED(provider); Q_UNUSED(path); Q_UNUSED(key); Q_UNUSED(body);
    QTimer::singleShot(0,this,[this,id] { Q_EMIT completed(id,0,{}); });
#endif
}
void AiTransport::cancel(quint64 id) {
#ifdef Q_OS_ANDROID
    QJniObject::callStaticMethod<void>(bridge,"cancel","(J)V",jlong(id)); clearJavaError();
#elif defined(Q_OS_WIN)
    if(auto reply=m_replies.take(id)) { disconnect(reply,nullptr,this,nullptr); reply->abort(); reply->deleteLater(); }
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
#elif defined(Q_OS_WIN)
    if(!ai::validProvider(provider)) return {};
    auto bytes=QSettings().value("ai/"+provider+"/protectedKey").toByteArray();
    if(bytes.isEmpty() || bytes.size()>65536) return {};
    QByteArray entropy=("XeraX SDR AI:"+provider).toUtf8();
    DATA_BLOB in{DWORD(bytes.size()),reinterpret_cast<BYTE*>(bytes.data())}, salt{DWORD(entropy.size()),reinterpret_cast<BYTE*>(entropy.data())}, out{};
    if(!CryptUnprotectData(&in,nullptr,&salt,nullptr,nullptr,CRYPTPROTECT_UI_FORBIDDEN,&out)) return {};
    const QString key=QString::fromUtf8(reinterpret_cast<const char*>(out.pbData),out.cbData);
    SecureZeroMemory(out.pbData,out.cbData); LocalFree(out.pbData);
    return ai::validKey(key)?key:QString();
#else
    Q_UNUSED(provider); return {};
#endif
}
bool AiTransport::saveKey(const QString& provider,const QString& key) {
#ifdef Q_OS_ANDROID
    const bool saved=QJniObject::callStaticMethod<jboolean>(bridge,"saveKey","(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;)Z",
        QNativeInterface::QAndroidApplication::context().object(),QJniObject::fromString(provider).object(),QJniObject::fromString(key).object());
    return !clearJavaError() && saved;
#elif defined(Q_OS_WIN)
    if(!ai::validProvider(provider) || (!key.isEmpty() && !ai::validKey(key))) return false;
    QSettings settings; const QString path="ai/"+provider+"/protectedKey";
    if(key.isEmpty()) { settings.remove(path); settings.sync(); return settings.status()==QSettings::NoError; }
    auto bytes=key.toUtf8(); QByteArray entropy=("XeraX SDR AI:"+provider).toUtf8();
    DATA_BLOB in{DWORD(bytes.size()),reinterpret_cast<BYTE*>(bytes.data())}, salt{DWORD(entropy.size()),reinterpret_cast<BYTE*>(entropy.data())}, out{};
    const bool ok=CryptProtectData(&in,L"XeraX SDR provider key",&salt,nullptr,nullptr,CRYPTPROTECT_UI_FORBIDDEN,&out);
    SecureZeroMemory(bytes.data(),bytes.size());
    if(!ok) return false;
    settings.setValue(path,QByteArray(reinterpret_cast<const char*>(out.pbData),out.cbData)); LocalFree(out.pbData);
    settings.sync(); return settings.status()==QSettings::NoError;
#else
    Q_UNUSED(provider); Q_UNUSED(key); return false;
#endif
}
}
