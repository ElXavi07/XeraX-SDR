// SPDX-License-Identifier: GPL-3.0-or-later
#include "ai_protocol.h"
#include <QJsonDocument>
#include <QSet>
#include <QRegularExpression>
#include <algorithm>
namespace dsd_qt::ai {
bool validProvider(const QString& p) { return p == "openai" || p == "deepseek"; }
bool validKey(const QString& k) {
    if (k.size() < 16 || k.size() > 4096) return false;
    for (auto c : k) if (c.unicode() < 33 || c.unicode() > 126) return false;
    return true;
}
QStringList models(const QJsonObject& response, bool* valid) {
    *valid = response.value("data").isArray();
    QStringList result;
    if (!*valid) return result;
    const auto rows = response.value("data").toArray();
    if (rows.size() > 5000) { *valid = false; return {}; }
    const QRegularExpression idPattern("^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$");
    for (const auto& row : rows) {
        const auto id = row.toObject().value("id").toString();
        if (idPattern.match(id).hasMatch()) result.append(id);
    }
    result.removeDuplicates(); result.sort(Qt::CaseInsensitive);
    return result;
}
QJsonArray tools(bool check) {
    QJsonArray result;
    auto add = [&](const QString& name, const QString& description, QJsonObject properties = {}) {
        QJsonArray required; for (auto i = properties.begin(); i != properties.end(); ++i) required.append(i.key());
        result.append(QJsonObject{{"type","function"},{"name",name},{"description",description},{"strict",true},
            {"parameters",QJsonObject{{"type","object"},{"properties",properties},{"required",required},{"additionalProperties",false}}}});
    };
    if (check) { add("connection_check","Call this function once with no arguments to check receiver-tool support."); return result; }
    add("receiver_diagnostics","Read current receiver measurements, availability, recent lab results and local capture indexes. Missing or unsupported counters are not evidence of zero errors.");
    add("measure_reception","Measure a fixed channel locally for 30 seconds. This does not change settings. Requires a running fixed channel.");
    add("optimize_gain","Run one bounded local gain comparison on an idle, fixed RTL-SDR channel. Uses actual frame/SNR measurements, restores worse settings. Requires user to enable experiments; may have insufficient evidence. No retuning or protocol change.");
    add("compare_capture","Reprocess the user's selected local I/Q capture with the chosen decoder and offset/filter alternatives. Samples stay on phone. Results are comparisons, not proof of recovered speech. Requires experiments and no other workers.",
        {{"capture_index",QJsonObject{{"type","integer"}}},
         {"mode",QJsonObject{{"type","string"},{"enum",QJsonArray{"P25-1","P25-2","DMR","NXDN48","NXDN96","NFM","AM"}}}}});
    return result;
}
QJsonObject request(const QString& p, const QString& model, const QString& instructions, const QJsonArray& history, bool check) {
    if (p == "openai") return {{"model",model},{"instructions",instructions},{"input",history},
        {"tools",tools(check)},{"tool_choice",check ? QJsonValue(QJsonObject{{"type","function"},{"name","connection_check"}}) : QJsonValue("auto")},
        {"parallel_tool_calls",false},{"store",false},{"include",QJsonArray{"reasoning.encrypted_content"}},
        {"max_output_tokens",check?2048:4096}};
    QJsonArray messages{QJsonObject{{"role","system"},{"content",instructions}}};
    for (const auto& item : history) messages.append(item);
    QJsonArray functions;
    for (const auto& item : tools(check)) {
        auto f = item.toObject(); f.remove("type"); f.remove("strict"); // DeepSeek strict uses a separate beta endpoint.
        functions.append(QJsonObject{{"type","function"},{"function",f}});
    }
    QJsonObject body{{"model",model},{"messages",messages},{"tools",functions},
        {"tool_choice",check ? QJsonValue(QJsonObject{{"type","function"},{"function",QJsonObject{{"name","connection_check"}}}}) : QJsonValue("auto")},
        {"max_tokens",check?2048:4096},{"stream",false}};
    // The compatibility check forces one function, which requires non-thinking mode.
    // Investigations use the selected model's default reasoning behavior.
    if(check) body["thinking"]=QJsonObject{{"type","disabled"}};
    return body;
}
Reply reply(const QString& p, const QJsonObject& response) {
    Reply r;
    auto call = [&](const QJsonObject& c, const QString& id, const QString& name, const QString& args) {
        Q_UNUSED(c);
        if (id.isEmpty() || id.size() > 256 || name.size() > 100 || args.size() > 4096) return false;
        r.calls.append(QJsonObject{{"id",id},{"name",name},{"arguments",args}}); return true;
    };
    if (p == "openai") {
        if (response.value("status").toString() != "completed" || !response.value("output").isArray()) return r;
        for (const auto& item : response.value("output").toArray()) {
            const auto o = item.toObject(); const auto type = o.value("type").toString();
            if (type == "message") {
                for (const auto& v : o.value("content").toArray()) {
                    const auto part = v.toObject();
                    if (part.value("type") == "output_text") r.text += part.value("text").toString() + "\n";
                    if (part.value("type") == "refusal") r.text += part.value("refusal").toString() + "\n";
                }
            } else if (type == "function_call") {
                if (!call(o,o.value("call_id").toString(),o.value("name").toString(),o.value("arguments").toString())) return r;
            } else if (type != "reasoning") return r;
            r.history.append(o); // Preserve reasoning/encrypted_content for stateless tool continuation.
        }
        r.tokens = qint64(response.value("usage").toObject().value("total_tokens").toDouble());
    } else {
        const auto choices = response.value("choices").toArray(); if (choices.size() != 1) return r;
        const auto choice = choices.first().toObject(); const auto finish = choice.value("finish_reason").toString();
        if (finish != "stop" && finish != "tool_calls") return r;
        const auto msg = choice.value("message").toObject(); if (msg.value("role") != "assistant") return r;
        r.text = msg.value("content").toString();
        for (const auto& item : msg.value("tool_calls").toArray()) {
            const auto o = item.toObject(), f = o.value("function").toObject();
            if (o.value("type") != "function" || !call(o,o.value("id").toString(),f.value("name").toString(),f.value("arguments").toString())) return r;
        }
        r.history.append(msg); // Includes reasoning_content if supplied by provider.
        r.tokens = qint64(response.value("usage").toObject().value("total_tokens").toDouble());
    }
    QSet<QString> ids; for (const auto& c : r.calls) { const auto id=c.toObject().value("id").toString(); if(ids.contains(id)) return r; ids.insert(id); }
    r.valid = r.calls.size() <= 4 && (!r.text.trimmed().isEmpty() || !r.calls.isEmpty());
    r.text = r.text.trimmed().left(20000); r.tokens = std::clamp<qint64>(r.tokens,0,1000000);
    return r;
}
QJsonObject toolResult(const QString& p, const QString& id, const QJsonObject& result) {
    const auto text = QString::fromUtf8(QJsonDocument(result).toJson(QJsonDocument::Compact));
    return p == "openai" ? QJsonObject{{"type","function_call_output"},{"call_id",id},{"output",text}}
        : QJsonObject{{"role","tool"},{"tool_call_id",id},{"content",text}};
}
}
