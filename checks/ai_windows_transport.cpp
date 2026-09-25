// SPDX-License-Identifier: GPL-3.0-or-later
#include "ai_transport.h"
#include <QCoreApplication>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QTimer>
#include <QEventLoop>
#include <QSettings>
#include <QTemporaryDir>
#include <QFile>
#include <cstdio>
#include <cstring>
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"FAILED line %d: %s\n",__LINE__,#x); return 1; } } while(0)
using namespace dsd_qt;
class Reply:public QNetworkReply {
public:
    QByteArray body; qint64 offset=0; bool aborted=false;
    Reply(const QNetworkRequest& request,QObject* parent,const QByteArray& bytes,int code):QNetworkReply(parent),body(bytes) {
        setRequest(request);setUrl(request.url());setAttribute(QNetworkRequest::HttpStatusCodeAttribute,code);
        open(QIODevice::ReadOnly|QIODevice::Unbuffered);
    }
    void finish() { Q_EMIT readyRead(); if(!aborted){setFinished(true);Q_EMIT finished();} }
    void abort() override { if(aborted || isFinished())return;aborted=true;setError(OperationCanceledError,"cancelled");setFinished(true);Q_EMIT finished(); }
    qint64 bytesAvailable() const override {return body.size()-offset+QNetworkReply::bytesAvailable();}
    qint64 readData(char* data,qint64 length) override {const auto n=qMin(length,body.size()-offset);if(n<=0)return -1;memcpy(data,body.constData()+offset,n);offset+=n;return n;}
};
class Network:public QNetworkAccessManager {
public:
    QNetworkRequest request; QByteArray payload; Operation verb{}; QPointer<Reply> last; int sent=0,code=200; QByteArray response="{\"data\":[]}";
    QNetworkReply* createRequest(Operation op,const QNetworkRequest& r,QIODevice* out=nullptr) override {
        ++sent;request=r;verb=op;payload=out?out->readAll():QByteArray();last=new Reply(r,this,response,code);return last;
    }
};
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv); QTemporaryDir directory; CHECK(directory.isValid());
    QCoreApplication::setOrganizationName("XeraXTests");QCoreApplication::setApplicationName("AITransport");
    QSettings::setDefaultFormat(QSettings::IniFormat);QSettings::setPath(QSettings::IniFormat,QSettings::UserScope,directory.path());
    Network network;AiTransport transport(nullptr,&network);int responses=0,status=-1;QByteArray result;
    QObject::connect(&transport,&AiTransport::completed,[&](quint64,int s,const QByteArray& b){++responses;status=s;result=b;});
    const QString fixture="fixture-only-never-a-real-api-key";
    transport.send(1,"openai","/models",fixture,{});CHECK(network.sent==1);
    CHECK(network.request.url()==QUrl("https://api.openai.com/v1/models") && network.verb==QNetworkAccessManager::GetOperation);
    CHECK(network.request.rawHeader("Authorization")=="Bearer "+fixture.toUtf8());
    CHECK(network.request.attribute(QNetworkRequest::RedirectPolicyAttribute).toInt()==QNetworkRequest::ManualRedirectPolicy);
    network.last->finish();CHECK(responses==1 && status==200 && result.contains("data"));
    transport.send(2,"deepseek","/chat/completions",fixture,"{\"model\":\"fixture\"}");
    CHECK(network.request.url()==QUrl("https://api.deepseek.com/chat/completions") && network.verb==QNetworkAccessManager::PostOperation && network.payload.contains("fixture"));
    transport.cancel(2);CHECK(network.last->aborted && responses==1);
    const auto before=network.sent;
    transport.send(3,"openai","https://untrusted.invalid",fixture,{});QCoreApplication::processEvents();
    CHECK(network.sent==before && status==0);
    transport.send(4,"untrusted","/models",fixture,{});QCoreApplication::processEvents();CHECK(network.sent==before);
    network.code=302;transport.send(5,"openai","/models",fixture,{});network.last->finish();CHECK(status==302 && network.sent==before+1);
    network.code=200;network.response=QByteArray(1048577,'x');transport.send(6,"openai","/models",fixture,{});network.last->finish();CHECK(status==0 && result.isEmpty());
    network.response="{}";transport.send(7,"openai","/models",fixture,{});network.last->abort();CHECK(status==0);
    CHECK(transport.saveKey("openai",fixture));CHECK(transport.loadKey("openai")==fixture);CHECK(transport.loadKey("deepseek").isEmpty());
    QFile settings(QSettings().fileName());CHECK(settings.open(QIODevice::ReadOnly));CHECK(!settings.readAll().contains(fixture.toUtf8()));settings.close();
    QSettings().setValue("ai/deepseek/protectedKey",QSettings().value("ai/openai/protectedKey"));CHECK(transport.loadKey("deepseek").isEmpty());
    QSettings().setValue("ai/openai/protectedKey",QByteArray("corrupt"));CHECK(transport.loadKey("openai").isEmpty());
    CHECK(transport.saveKey("openai",fixture));CHECK(transport.saveKey("openai",{}));CHECK(transport.loadKey("openai").isEmpty());
    CHECK(!transport.saveKey("other",fixture));
    if(app.arguments().contains("--live-tls")) {
        AiTransport live;QEventLoop loop;int complete=0;
        QObject::connect(&live,&AiTransport::completed,[&](quint64,int code,const QByteArray&){if(code==401)++complete;loop.quit();});
        for(const auto& provider:{QString("openai"),QString("deepseek")}) {
            QTimer watchdog;watchdog.setSingleShot(true);QObject::connect(&watchdog,&QTimer::timeout,&loop,&QEventLoop::quit);watchdog.start(50000);
            live.send(100,provider,"/models",fixture,{});loop.exec();
        }
        CHECK(complete==2);printf("Both official providers reached over verified HTTPS; invalid fixture keys rejected as expected.\n");
    }
    printf("Windows AI transport, cancellation, limits and encrypted key storage checks passed.\n");
    return 0;
}
