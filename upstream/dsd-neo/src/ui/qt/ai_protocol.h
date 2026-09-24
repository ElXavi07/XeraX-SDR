// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QJsonArray>
#include <QJsonObject>
#include <QStringList>
namespace dsd_qt::ai {
bool validProvider(const QString& provider);
bool validKey(const QString& key);
QStringList models(const QJsonObject& response, bool* valid);
QJsonArray tools(bool check = false);
QJsonObject request(const QString& provider, const QString& model, const QString& instructions,
                    const QJsonArray& history, bool check = false);
struct Reply { QJsonArray history, calls; QString text; qint64 tokens = 0; bool valid = false; };
Reply reply(const QString& provider, const QJsonObject& response);
QJsonObject toolResult(const QString& provider, const QString& id, const QJsonObject& result);
}
