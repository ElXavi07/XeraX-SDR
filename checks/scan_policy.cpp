// SPDX-License-Identifier: GPL-3.0-or-later
#include <QCoreApplication>
#include <QFile>
#include <QStandardPaths>
#include <QUuid>
#include <cstdio>
#include "json_store.h"
#include "scan_lists_model.h"
#include "scan_list_targets.h"
#include "session_args.h"

int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    QStandardPaths::setTestModeEnabled(true);
    QCoreApplication::setOrganizationName("XeraXTests");
    QCoreApplication::setApplicationName("scan-" + QUuid::createUuid().toString(QUuid::WithoutBraces));
    using namespace dsd_qt;
    int failures = 0;
    auto check = [&](bool ok, const char* label) {
        if (!ok) { ++failures; std::fprintf(stderr, "%s\n", label); }
    };
    QVariantMap list{{"sourceType", "usb"}, {"defaultDwellMs", 3000}, {"defaultHoldMs", 1200}};
    SessionArgPrefs prefs;
    QString error;
    auto args = [&]() { return session_args_scan_build(list, "451.5", "targets.csv", prefs, &error); };
    check(!args().isEmpty() && !args().contains("--scan-max-visit-ms"), "legacy list must inherit");
    for (int value : {-1, 0, 1000, 15000, 3600000}) {
        list["maxVisitMs"] = value;
        const auto built = args();
        check(error.isEmpty() && !built.isEmpty(), "valid cap refused");
        check(scan_list_settings_error(list).isEmpty(), "target validation disagrees");
        check(value < 0 ? !built.contains("--scan-max-visit-ms")
                        : built.mid(built.size() - 2) == QStringList{"--scan-max-visit-ms", QString::number(value)},
              "cap must reach engine unchanged, including explicit zero");
    }
    for (const QVariant& value : QVariantList{-2, 1, 999, 3600001, "bad", "1500ms", "1500.5", true, "9999999999999999"}) {
        list["maxVisitMs"] = value;
        check(args().isEmpty() && !error.isEmpty(), "invalid cap reached engine");
        check(!scan_list_settings_error(list).isEmpty(), "invalid cap accepted by target validator");
    }
    list["maxVisitMs"] = 0;
    {
        QVariantMap mixed = list;
        mixed["entries"] = QVariantList{
            QVariantMap{{"uid", "nfm1"}, {"kind", "freq"}, {"protocol", "nfm"}, {"freqMhz", "154.13"}},
            QVariantMap{{"uid", "p251"}, {"kind", "freq"}, {"protocol", "p25"}, {"freqMhz", "460.1"}}};
        const auto targets = scan_list_targets(mixed, {});
        check(targets.ok && targets.targetCount == 2 && targets.csv.contains("nfm-conventional,154130000")
              && targets.csv.contains("p25-conventional,460100000"), "mixed analog/digital scan generation failed");
    }
    for (const QString& field : {QString("defaultDwellMs"), QString("defaultHoldMs")}) {
        for (int value : {0, 250, 600000}) {
            list[field] = value;
            check(!args().isEmpty(), "valid dwell/hold refused");
        }
        for (int value : {-1, 1, 249, 600001}) {
            list[field] = value;
            check(args().isEmpty(), "invalid dwell/hold reached engine");
        }
        list[field] = 1200;
    }
    prefs.extraArgs = "--scan-max-visit-ms 9000";
    list["maxVisitMs"] = -1;
    check(args().count("--scan-max-visit-ms") == 1 && args().last() == "9000", "inherit must preserve advanced cap");
    list["maxVisitMs"] = 0;
    check(args().last() == "0" && args().count("--scan-max-visit-ms") == 2, "explicit off must override advanced cap");
    list["maxVisitMs"] = 15000;
    check(args().last() == "15000", "per-list cap precedence");
    list["voiceOnly"] = true;
    check(args().contains("--scan-voice-only"), "voice-only lost");
    {
        ScanListsModel model;
        check(model.newDraft().value("maxVisitMs").toInt() == -1, "new list inheritance default");
        list["name"] = "Test list";
        check(model.add(list), "save failed");
        ScanListsModel reloaded;
        check(reloaded.get(0).value("maxVisitMs").toInt() == 15000, "cap not persisted");
        check(reloaded.update(0, {{"name", "Renamed"}}), "update failed");
        ScanListsModel renamed;
        check(renamed.get(0).value("maxVisitMs").toInt() == 15000, "partial update dropped cap");
        check(renamed.update(0, {{"maxVisitMs", 0}}), "off update failed");
        ScanListsModel off;
        check(off.get(0).value("maxVisitMs").toInt() == 0, "explicit off not persisted");
    }
    QFile::remove(json_store_path("scan_lists.json"));
    std::fprintf(stderr, "%d scanner policy failures\n", failures);
    return failures ? 1 : 0;
}
