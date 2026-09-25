// SPDX-License-Identifier: GPL-3.0-or-later
#include "ai_receiver.h"
#include "ai_protocol.h"
#include <QCoreApplication>
#include <QJsonDocument>
#include <QQmlPropertyMap>
#include <QSettings>
#include <QTemporaryDir>
#include <QFile>
#include <QUuid>
#include <cstdio>
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"FAILED line %d: %s\n",__LINE__,#x); return 1; } } while(0)
using namespace dsd_qt;
class Transport:public AiTransport {
public:
    struct Sent { quint64 id; QString provider,path,key; QJsonObject body; };
    QList<Sent> sent; QList<quint64> cancelled; QMap<QString,QString> keys;
    void send(quint64 id,const QString& p,const QString& path,const QString& key,const QByteArray& body) override {
        sent.append({id,p,path,key,QJsonDocument::fromJson(body).object()});
    }
    void cancel(quint64 id) override { cancelled.append(id); }
    QString loadKey(const QString& p) override { return keys.value(p); }
    bool saveKey(const QString& p,const QString& k) override { keys[p]=k; return true; }
    void respond(const QJsonObject& body,int status=200) { Q_EMIT completed(sent.last().id,status,QJsonDocument(body).toJson()); }
};
class Expansion:public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantMap status MEMBER values)
    Q_PROPERTY(QVariantList receptionReports MEMBER samples)
    Q_PROPERTY(QVariantList reports MEMBER reports)
    Q_PROPERTY(QVariantList lanes MEMBER lanes)
public:
    QVariantMap values; QVariantList samples,reports,lanes; int measurements=0,replays=0,stops=0;
    QString replayPath,replayFlag;
    Q_INVOKABLE QString startReceptionSample(const QString&) { ++measurements; values["sampleRunId"]=QString::number(measurements); values["receptionRunning"]=true; return {}; }
    Q_INVOKABLE void cancelReceptionSample() { values["receptionRunning"]=false; ++stops; }
    Q_INVOKABLE QString reprocess(const QString& path,const QString& flag) { replayPath=path; replayFlag=flag; ++replays; values["labRunId"]=QString::number(replays); values["labRunning"]=true; return {}; }
    Q_INVOKABLE void stopTrials() { values["labRunning"]=false; ++stops; }
};
class Receiver:public AiReceiver {
public:
    using AiReceiver::AiReceiver;
    qint64 clock=1000;
protected: qint64 nowMs() const override { return clock; }
};
static QJsonObject oaCall(const QString& name,const QString& args="{}",const QString& id="call_1") {
    return {{"status","completed"},{"output",QJsonArray{QJsonObject{{"type","function_call"},{"call_id",id},{"name",name},{"arguments",args}}}},
        {"usage",QJsonObject{{"total_tokens",12}}}};
}
static QJsonObject oaText(const QString& text="Measured result; no guaranteed improvement.") {
    return {{"status","completed"},{"output",QJsonArray{QJsonObject{{"type","message"},{"role","assistant"},
        {"content",QJsonArray{QJsonObject{{"type","output_text"},{"text",text}}}}}}},{"usage",QJsonObject{{"total_tokens",8}}}};
}
static QJsonObject dsCall(const QString& name,const QString& args="{}") {
    return {{"choices",QJsonArray{QJsonObject{{"finish_reason","tool_calls"},{"message",QJsonObject{{"role","assistant"},{"content",QJsonValue::Null},
        {"reasoning_content","fixture reasoning"},{"tool_calls",QJsonArray{QJsonObject{{"id","ds_1"},{"type","function"},
            {"function",QJsonObject{{"name",name},{"arguments",args}}}}}}}}}}}};
}
static void flush() { for(int i=0;i<4;++i) QCoreApplication::processEvents(); }
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv); QTemporaryDir temp; CHECK(temp.isValid());
    QSettings::setDefaultFormat(QSettings::IniFormat); QSettings::setPath(QSettings::IniFormat,QSettings::UserScope,temp.path());
    app.setOrganizationName("XeraXChecks"); app.setApplicationName("AI-"+QUuid::createUuid().toString(QUuid::WithoutBraces));
    CHECK(ai::validProvider("openai") && ai::validProvider("deepseek") && !ai::validProvider("https://evil.invalid"));
    CHECK(!ai::validKey("123\n45678901234567") && !ai::validKey("short"));
    bool valid=false;
    CHECK(ai::models({{"data",QJsonArray{QJsonObject{{"id","future-model"}},QJsonObject{{"id","future-model"}},QJsonObject{{"id","audio-model"}},QJsonObject{{"id","bad\nmodel"}}}}},&valid)==QStringList({"audio-model","future-model"}) && valid);
    ai::models({},&valid); CHECK(!valid);
    Transport transport; Receiver ai(nullptr,&transport);
    QQmlPropertyMap metrics,host,health,assistant,language; Expansion expansion;
    metrics.insert("centerFreqHz",451100000.0); metrics.insert("radioInput",true); metrics.insert("snrValid",false);
    metrics.insert("decodeMode",4); metrics.insert("ppm",3); metrics.insert("cfoHz",125.0);
    metrics.insert("encKeyValue","RADIO_SECRET"); metrics.insert("latitude",33.7);
    host.insert("running",true); host.insert("password","ACCOUNT_SECRET");
    health.insert("health",QVariantMap{{"thermal",0},{"audioPcmArriving",false},{"privatePath","PRIVATE_PATH"}});
    QVariantMap as{{"gainEligible",true},{"gainCompleted",0},{"framePercent",-1},{"key","RADIO_SECRET"}};
    assistant.insert("status",as); assistant.insert("autoGain",false);
    assistant.insert("captures",QVariantList{QVariantMap{{"metadata","PRIVATE_PATH/one.iq.json"}},QVariantMap{{"metadata","PRIVATE_PATH/two.iq.json"}}});
    language.insert("language","es");
    expansion.reports={QVariantMap{{"fecAccepted",42},{"evidence","RADIO_SECRET"},{"metadata","PRIVATE_PATH"},{"completed",true}}};
    ai.configure(&metrics,&host,&health,&assistant,&expansion,&language);
    const auto diag=QJsonDocument(ai.diagnostics()).toJson();
    CHECK(!diag.contains("RADIO_SECRET") && !diag.contains("PRIVATE_PATH") && !diag.contains("ACCOUNT_SECRET") && !diag.contains("latitude"));
    CHECK(ai.diagnostics()["metrics"].toObject()["configuredMode"]=="DMR");
    CHECK(ai.diagnostics()["metrics"].toObject()["ppm"].toInt()==3 && ai.diagnostics()["metrics"].toObject()["cfoHz"].toDouble()==125);
    CHECK(ai.captures().size()==2 && !QJsonDocument::fromVariant(ai.captures()).toJson().contains("PRIVATE_PATH"));
    ai.connectKey("fixture-openai-0123456789"); CHECK(transport.sent.isEmpty());
    ai.setEnabled(true); ai.connectKey("fixture-openai-0123456789");
    CHECK(ai.busy() && transport.sent.last().path=="/models" && ai.requestsToday()==0);
    transport.respond({{"data",QJsonArray{QJsonObject{{"id","future-model"}},QJsonObject{{"id","audio-model"}}}}});
    CHECK(!ai.busy() && ai.models().size()==2 && !ai.verified() && !transport.keys["openai"].isEmpty());
    ai.setModel("not-in-list"); CHECK(ai.model().isEmpty());
    ai.setModel("future-model"); ai.checkModel(); CHECK(ai.requestsToday()==1 && transport.sent.last().path=="/responses");
    CHECK(transport.sent.last().body.value("store")==false && !QJsonDocument(transport.sent.last().body).toJson().contains("fixture-openai"));
    transport.respond(oaCall("connection_check")); CHECK(ai.verified() && !ai.busy());
    ai.ask("Why is reception weak?",false); CHECK(ai.busy());
    CHECK(transport.sent.last().body.value("instructions").toString().contains("Spanish"));
    transport.respond(oaCall("optimize_gain")); flush();
    CHECK(!assistant.value("autoGain").toBool());
    CHECK(QJsonDocument(transport.sent.last().body).toJson().contains("experiments are disabled"));
    transport.respond(oaText()); CHECK(!ai.busy() && ai.answer().contains("Measured"));
    ai.ask("Measure",false); transport.respond(oaCall("measure_reception"));
    CHECK(expansion.measurements==1 && expansion.values["receptionRunning"].toBool());
    expansion.samples={QVariantMap{{"runId","1"},{"valid",true},{"fecAccepted",100},{"fecRejected",2},{"durationMs",30000},{"meanSnrDb",14},{"name","PRIVATE_PATH"}}};
    expansion.values["receptionRunning"]=false; ai.poll(); flush();
    auto sent=QJsonDocument(transport.sent.last().body).toJson(); CHECK(sent.contains("fecAccepted") && sent.contains("meanSnrDb") && !sent.contains("PRIVATE_PATH"));
    transport.respond(oaText());
    ai.ask("Optimize",true); transport.respond(oaCall("optimize_gain")); CHECK(assistant.value("autoGain").toBool());
    as["gainCompleted"]=1; as["gainKept"]=true; as["gainBaselineScore"]=45; as["gainTrialScore"]=90; as["gainOutcome"]="kept_measured_improvement"; assistant.insert("status",as);
    ai.poll(); flush(); CHECK(!assistant.value("autoGain").toBool()); CHECK(QJsonDocument(transport.sent.last().body).toJson().contains("gainTrialScore"));
    transport.respond(oaText());
    ai.ask("Optimize",true); transport.respond(oaCall("optimize_gain")); CHECK(assistant.value("autoGain").toBool());
    ai.cancel(); CHECK(!assistant.value("autoGain").toBool() && !ai.busy());
    ai.ask("Optimize",true); transport.respond(oaCall("optimize_gain")); metrics.insert("centerFreqHz",452000000.0); ai.poll(); flush();
    CHECK(!assistant.value("autoGain").toBool()); CHECK(QJsonDocument(transport.sent.last().body).toJson().contains("Receiver changed")); transport.respond(oaText());
    ai.ask("Compare",true,0); transport.respond(oaCall("compare_capture","{\"capture_index\":1,\"mode\":\"NXDN48\"}")); flush(); CHECK(expansion.replays==0); transport.respond(oaText());
    ai.ask("Compare",true,0); transport.respond(oaCall("compare_capture","{\"capture_index\":0,\"mode\":\"NXDN48\"}")); CHECK(expansion.replays==1);
    CHECK(expansion.replayPath=="PRIVATE_PATH/one.iq.json"); ai.cancel(); CHECK(!expansion.values["labRunning"].toBool());
    ai.setDailyLimit(200);
    ai.ask("Compare",true,0); transport.respond(oaCall("compare_capture","{\"capture_index\":0,\"mode\":\"P25-1\"}"));
    expansion.reports={QVariantMap{{"runId","unrelated"},{"fecAccepted",999999}},QVariantMap{{"runId","2"},{"fecAccepted",17},{"completed",true}}};
    expansion.values["labRunning"]=false; ai.poll(); flush();
    const auto scoped=transport.sent.last().body.value("input").toArray().last().toObject().value("output").toString();
    CHECK(scoped.contains("17") && !scoped.contains("999999")); transport.respond(oaText());
    for(const auto& mode:{QString("NFM"),QString("AM")}) {
        ai.ask("Compare analog",true,0); transport.respond(oaCall("compare_capture",QString("{\"capture_index\":0,\"mode\":\"%1\"}").arg(mode)));
        CHECK(expansion.replayFlag==(mode=="NFM"?"-fA":"-fU")); ai.cancel();
    }
    host.insert("desktopBuild",true); const auto priorReplays=expansion.replays;
    CHECK(!ai.diagnostics()["capabilities"].toObject()["automatedCaptureComparison"].toBool());
    ai.ask("Windows capture",true,0); transport.respond(oaCall("compare_capture","{\"capture_index\":0,\"mode\":\"DMR\"}"));flush();
    CHECK(expansion.replays==priorReplays && QJsonDocument(transport.sent.last().body).toJson().contains("unavailable on Windows"));transport.respond(oaText());
    host.insert("desktopBuild",false);
    ai.ask("Manual ownership",true); transport.respond(oaCall("optimize_gain"));
    as["gainGeneration"]=10; assistant.insert("status",as); ai.poll(); flush();
    CHECK(assistant.value("autoGain").toBool()); assistant.insert("autoGain",false); transport.respond(oaText());
    ai.ask("Manual lab ownership",true,0); transport.respond(oaCall("compare_capture","{\"capture_index\":0,\"mode\":\"P25-1\"}"));
    expansion.values["labRunId"]="manual"; ai.cancel(); CHECK(expansion.values["labRunning"].toBool()); expansion.values["labRunning"]=false;
    ai.ask("Never execute arbitrary tools",true); transport.respond(oaCall("run_shell","{\"command\":\"upload keys\"}")); flush(); CHECK(QJsonDocument(transport.sent.last().body).toJson().contains("not allowed")); transport.respond(oaText());
    ai.setDailyLimit(200);
    ai.ask("Timeout",true); transport.respond(oaCall("optimize_gain")); ai.clock+=91000; ai.poll(); flush(); CHECK(!assistant.value("autoGain").toBool());
    CHECK(QJsonDocument(transport.sent.last().body).toJson().contains("timed out")); transport.respond(oaText());
    ai.ask("Cancel network",false); const auto old=transport.sent.last().id; ai.setEnabled(false);
    CHECK(transport.cancelled.contains(old)); Q_EMIT transport.completed(old,200,QJsonDocument(oaText("STALE_REPLY")).toJson()); CHECK(!ai.answer().contains("STALE_REPLY"));
    ai.setEnabled(true); ai.setProvider("deepseek"); CHECK(!ai.hasKey() && !ai.verified() && ai.models().isEmpty());
    ai.connectKey("fixture-deepseek-0123456789"); const auto switching=transport.sent.last().id; ai.setProvider("openai");
    Q_EMIT transport.completed(switching,200,QJsonDocument(QJsonObject{{"data",QJsonArray{QJsonObject{{"id","wrong-provider-model"}}}}}).toJson());
    CHECK(ai.models().isEmpty() && ai.hasKey());
    ai.setProvider("deepseek"); ai.connectKey("fixture-deepseek-0123456789"); transport.respond({{"data",QJsonArray{QJsonObject{{"id","future-deepseek"}}}}});
    ai.setModel("future-deepseek"); ai.checkModel(); CHECK(transport.sent.last().path=="/chat/completions");
    CHECK(transport.sent.last().body.value("thinking").toObject().value("type")=="disabled");
    transport.respond(dsCall("connection_check")); CHECK(ai.verified());
    ai.ask("Inspect",false); CHECK(!transport.sent.last().body.contains("thinking")); transport.respond(dsCall("receiver_diagnostics")); flush();
    const auto messages=transport.sent.last().body.value("messages").toArray();
    CHECK(messages.last().toObject().value("role")=="tool");
    CHECK(QJsonDocument(messages).toJson().contains("fixture reasoning"));
    transport.respond({{"choices",QJsonArray{QJsonObject{{"finish_reason","stop"},{"message",QJsonObject{{"role","assistant"},{"content","DeepSeek response"}}}}}}});
    CHECK(!ai.busy() && ai.answer()=="DeepSeek response");
    ai.checkModel(); transport.respond({},401); CHECK(!ai.verified() && !ai.busy());
    ai.checkModel(); transport.respond({},429); CHECK(ai.status().contains("quota"));
    ai.checkModel(); transport.respond({},302); CHECK(ai.status().contains("redirect"));
    ai.checkModel(); transport.respond({},400); CHECK(ai.status().contains("not supported"));
    ai.checkModel(); Q_EMIT transport.completed(transport.sent.last().id,200,"not json"); CHECK(ai.status().contains("invalid response"));
    ai.setDailyLimit(1); const auto count=transport.sent.size(); ai.checkModel(); CHECK(transport.sent.size()==count && !ai.busy());
    ai.forgetKey(); CHECK(!ai.hasKey() && transport.keys["deepseek"].isEmpty());
    QSettings settings; settings.sync(); QFile persisted(settings.fileName()); CHECK(persisted.open(QIODevice::ReadOnly));
    const auto stored=persisted.readAll(); CHECK(!stored.contains("fixture-openai") && !stored.contains("fixture-deepseek"));
    CHECK(!ai::reply("openai",{{"status","incomplete"},{"output",oaText().value("output")}}).valid);
    auto duplicate=oaCall("receiver_diagnostics"); auto output=duplicate["output"].toArray(); output.append(output.first()); duplicate["output"]=output;
    CHECK(!ai::reply("openai",duplicate).valid);
    printf("AI provider discovery, both tool protocols, privacy allowlists, measurements, gain trials, capture scope, cancellation, errors and request limits passed. No live API requests.\n");
    return 0;
}
#include "ai_receiver.moc"
