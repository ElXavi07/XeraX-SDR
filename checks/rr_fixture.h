// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QQmlPropertyMap>

// UI-only fixture; transport/parser/import integration uses the separate real
// RadioReferenceModel test with captured SOAP replies.
class RrFixture : public QQmlPropertyMap {
    Q_OBJECT
public:
    explicit RrFixture(QObject* parent = nullptr) : QQmlPropertyMap(this, parent) { reset(); }
    Q_INVOKABLE void reset() {
        const QVariantMap values = {
            {"available", true}, {"hasAppKey", true}, {"buildHasAppKey", true},
            {"credentialsReady", true}, {"busy", false}, {"statusText", ""},
            {"errorText", ""}, {"errorIsAuth", false}, {"errorIsSubscription", false},
            {"systemDetails", QVariantMap{}}, {"talkgroupSummary", QVariantMap{}},
            {"sites", QVariantList{}}, {"systems", QVariantList{}},
            {"countries", QVariantList{}}, {"states", QVariantList{}}, {"counties", QVariantList{}},
            {"conventionalCategories", QVariantList{}}, {"conventionalAgencies", QVariantList{}}, {"conventionalFrequencies", QVariantList{}},
            {"conventional", false}, {"trunked", true}, {"countyRequest", 0}, {"requestCount", 0}
        };
        for (auto it = values.begin(); it != values.end(); ++it) insert(it.key(), it.value());
    }
    Q_INVOKABLE void loadCountySystems(int ctid) {
        insert("countyRequest", ctid); insert("requestCount", value("requestCount").toInt() + 1);
    }
    Q_INVOKABLE void loadConventional(int kind, int id) { insert("conventionalKind",kind);insert("conventionalId",id); }
    Q_INVOKABLE void cancel() {}
    Q_INVOKABLE void loadSystem(int) {}
    Q_INVOKABLE void closeSystem() { insert("systemDetails", QVariantMap{}); }
    Q_INVOKABLE QVariantMap buildImportPlan(const QVariantList&, const QVariantMap&) { return {}; }
};
