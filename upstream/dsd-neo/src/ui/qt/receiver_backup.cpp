// SPDX-License-Identifier: GPL-3.0-or-later
#include "receiver_tools.h"
#include "app_prefs.h"
#include "saved_systems_model.h"
#include "scan_lists_model.h"
#include "decoder_host.h"
#include "json_store.h"
#include <QDirIterator>
#include <dsd-neo/engine/trunk_scan.h>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSaveFile>
#include <QUrl>
#include <QUuid>
#include <algorithm>

namespace dsd_qt {
namespace {
const char* preferences[] = {"appearance", "textScale", "metricUnits", "backgroundListening", "keepScreenAwake",
    "skipEncrypted", "persistTgLockouts", "hangtimeSec", "autoPpm", "gainDb", "ppm", "bandwidthKhz", "biasTee"};
QString pathOf(const QString& url) { QUrl u(url); return u.isLocalFile() ? u.toLocalFile() : url; }
QVariant clean(QVariant value) {
    if (value.metaType().id() == QMetaType::QVariantList) {
        auto rows = value.toList(); for (auto& row : rows) row = clean(row); return rows;
    }
    if (value.metaType().id() != QMetaType::QVariantMap) return value;
    auto row = value.toMap();
    // RadioReference account and executable argument overrides never travel in a backup.
    for (const auto& key : row.keys()) {
        if (key.startsWith("rr") || key.contains("password", Qt::CaseInsensitive) || key == "extraArgs"
            || key == "encForceKey" || key.startsWith("encKey") || key.startsWith("decryption") || key.contains("keyCsv", Qt::CaseInsensitive)
            || key.startsWith("keys") || key == "dmrTgKeyCsvPath") row.remove(key);
        else row[key] = clean(row[key]);
    }
    return row;
}
void collectPaths(const QVariant& value, QSet<QString>& files) {
    if (value.metaType().id() == QMetaType::QVariantList) { for (const auto& item : value.toList()) collectPaths(item, files); }
    else if (value.metaType().id() == QMetaType::QVariantMap) {
        const auto row = value.toMap();
        for (auto i = row.cbegin(); i != row.cend(); ++i) {
            if (i.key().endsWith("CsvPath") && !i.value().toString().isEmpty()) files.insert(i.value().toString());
            collectPaths(i.value(), files);
        }
    }
}
QVariant relocate(QVariant value, const QMap<QString, QString>& files) {
    if (value.metaType().id() == QMetaType::QString) return files.value(value.toString(), value.toString());
    if (value.metaType().id() == QMetaType::QVariantList) {
        auto list = value.toList(); for (auto& item : list) item = relocate(item, files); return list;
    }
    if (value.metaType().id() == QMetaType::QVariantMap) {
        auto map = value.toMap(); for (auto i = map.begin(); i != map.end(); ++i) i.value() = relocate(i.value(), files); return map;
    }
    return value;
}
}
QString ReceiverTools::backup(const QString& url) {
    QVariantList systems, lists;
    for (int i = 0; i < m_systems->count(); ++i) {
        auto row = clean(m_systems->get(i)).toMap();
        if (row.value("sourceType") == "file") continue; // Large I/Q recordings remain separately managed.
        systems.append(row);
    }
    for (int i = 0; i < m_lists->count(); ++i) {
        auto row = clean(m_lists->get(i)).toMap();
        if (row.value("targetSource") == "csv") {
            dsd_trunk_scan_target_list targets{}; char error[256]{};
            if (dsd_trunk_scan_load_targets_csv(row.value("targetsCsvPath").toString().toUtf8().constData(), nullptr,
                    &targets, error, sizeof error)) return tr("Could not read an imported scan list: %1").arg(QString::fromUtf8(error));
            QVariantList entries;
            for (size_t j=0;j<targets.count;j++) {
                const auto& t=targets.targets[j];
                if (t.row_options.present) {
                    dsd_trunk_scan_target_list_reset(&targets);
                    return tr("A CSV list uses scoped options. Export that list with its CSV companions separately; portable backup cannot preserve those overrides yet.");
                }
                const char* modes[]={"-ft","-fs","-fs","-fn","-fn","-fi","-fi","-ft","-fA"};
                const bool trunk=t.type==DSD_TRUNK_SCAN_TARGET_P25_TRUNK || t.type==DSD_TRUNK_SCAN_TARGET_DMR_TRUNK
                    || t.type==DSD_TRUNK_SCAN_TARGET_NXDN_TRUNK || t.type==DSD_TRUNK_SCAN_TARGET_NXDN48_TRUNK;
                const QString uid=QUuid::createUuid().toString(QUuid::WithoutBraces);
                systems.append(QVariantMap{{"uid",uid},{"name",QString::fromUtf8(t.id)},
                    {"sourceType",row.value("sourceType","usb")},{"freqMhz",QString::number(t.frequency_hz/1e6,'f',6)},
                    {"decodeFlag",QString::fromLatin1(modes[t.type])},{"trunking",trunk},
                    {"chanCsvPath",QString::fromUtf8(t.chan_csv)},{"p25BandplanCsvPath",QString::fromUtf8(t.p25_bandplan_csv)},
                    {"gainDb",t.rtl_gain_is_set?t.rtl_gain_db:-1}});
                const char* mods[]={"","auto","c4fm","cqpsk","gfsk"};
                // The UI accepts an empty modulation as the inherited/automatic choice.
                const QString modulation=t.modulation>=2 && t.modulation<=4 ? QString::fromLatin1(mods[t.modulation]):QString();
                entries.append(QVariantMap{{"uid",QUuid::createUuid().toString(QUuid::WithoutBraces)},
                    {"kind","system"},{"systemUid",uid},{"enabled",true},{"priority",t.priority!=0},
                    {"dwellMs",t.dwell_is_set?t.dwell_ms:0},{"holdMs",t.activity_hold_is_set?t.activity_hold_ms:0},
                    {"gainDb",t.rtl_gain_is_set?t.rtl_gain_db:-1},{"modulation",modulation}});
            }
            dsd_trunk_scan_target_list_reset(&targets);
            row["entries"]=entries;row["targetSource"]="manual";row.remove("targetsCsvPath");
        }
        lists.append(row);
    }
    QSet<QString> systemIds; for (const auto& item:systems) systemIds.insert(item.toMap().value("uid").toString());
    for (const auto& item:lists) for (const auto& value:item.toMap().value("entries").toList()) {
        const auto e=value.toMap();
        if (e.value("kind")=="system" && !systemIds.contains(e.value("systemUid").toString()))
            return tr("A scan list references a missing system or a recording that cannot travel in this backup.");
    }
    QSet<QString> paths; collectPaths(systems, paths); collectPaths(lists, paths);
    QJsonObject files;
    qint64 total = 0;
    for (const auto& path : paths) {
        QFile file(path);
        if (!file.open(QIODevice::ReadOnly) || file.size() > 8 * 1024 * 1024)
            return tr("A referenced CSV is missing or exceeds 8 MB: %1").arg(QFileInfo(path).fileName());
        const auto bytes = file.readAll(); total += bytes.size();
        if (total > 32 * 1024 * 1024) return tr("Referenced CSV files exceed the 32 MB backup limit.");
        files[path] = QString::fromLatin1(bytes.toBase64());
    }
    QJsonObject prefs;
    for (const char* name : preferences) if (m_prefs->property(name).isValid()) prefs[name] = QJsonValue::fromVariant(m_prefs->property(name));
    QJsonObject document{{"format", "xerax-backup"}, {"version", 1}, {"systems", QJsonArray::fromVariantList(systems)},
        {"lists", QJsonArray::fromVariantList(lists)}, {"preferences", prefs}, {"files", files},
        {"profiles", QJsonArray::fromVariantList(profiles())}};
    QFile file(pathOf(url));
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate)) return file.errorString();
    const auto bytes = QJsonDocument(document).toJson(QJsonDocument::Compact);
    return file.write(bytes) == bytes.size() && file.flush() ? QString() : tr("Could not finish writing the backup.");
}
QString ReceiverTools::restore(const QString& url) {
    if (m_host && m_host->sessionActive()) return tr("Stop reception before restoring a backup.");
    QFile file(pathOf(url));
    if (!file.open(QIODevice::ReadOnly)) return file.errorString();
    if (file.size() > 48 * 1024 * 1024) return tr("Backup exceeds 48 MB.");
    QJsonParseError parse;
    const auto doc = QJsonDocument::fromJson(file.readAll(), &parse).object();
    if (parse.error != QJsonParseError::NoError || doc.value("format") != "xerax-backup" || doc.value("version") != 1
        || !doc.value("systems").isArray() || !doc.value("lists").isArray() || !doc.value("files").isObject()
        || doc.value("systems").toArray().size() > 10000 || doc.value("lists").toArray().size() > 1000)
        return tr("This is not a supported XeraX backup.");
    auto systems = clean(doc.value("systems").toArray().toVariantList()).toList();
    auto lists = clean(doc.value("lists").toArray().toVariantList()).toList();
    const auto fileMap = doc.value("files").toObject();
    QMap<QString, QByteArray> contents;
    qint64 total = 0;
    for (auto it = fileMap.begin(); it != fileMap.end(); ++it) {
        auto decoded = QByteArray::fromBase64Encoding(it.value().toString().toLatin1(), QByteArray::AbortOnBase64DecodingErrors);
        if (!decoded || decoded.decoded.size() > 8 * 1024 * 1024) return tr("A bundled CSV is invalid.");
        total += decoded.decoded.size();
        if (total > 32 * 1024 * 1024) return tr("Bundled files exceed 32 MB.");
        contents[it.key()] = decoded.decoded;
    }
    QSet<QString> required; collectPaths(systems, required); collectPaths(lists, required);
    for (const auto& path : required) if (!contents.contains(path)) return tr("Backup is missing a referenced CSV.");
    QSet<QString> ids;
    for (const auto& item : systems) {
        auto row = item.toMap(); const auto uid = row.value("uid").toString();
        if (row.isEmpty() || row.value("sourceType") == "file" || uid.isEmpty() || ids.contains(uid)) return tr("Invalid or duplicate system identity.");
        ids.insert(uid);
    }
    for (const auto& item : lists) {
        auto row = item.toMap();
        if (row.isEmpty() || row.value("targetSource") == "csv") return tr("Unsupported scan-list entry.");
        for (const auto& v : row.value("entries").toList()) {
            const auto e = v.toMap();
            if (e.value("kind") == "system" && !ids.contains(e.value("systemUid").toString()))
                return tr("A scan-list entry references a missing saved system.");
        }
    }
    const QString dir = json_store_path("restored/" + QUuid::createUuid().toString(QUuid::WithoutBraces));
    if (!QDir().mkpath(dir)) return tr("Could not create restore directory.");
    QMap<QString, QString> relocated;
    int index = 0;
    for (auto it = contents.cbegin(); it != contents.cend(); ++it) {
        const QString dest = dir + '/' + QString::number(index++) + ".csv";
        QSaveFile output(dest);
        if (!output.open(QIODevice::WriteOnly) || output.write(it.value()) != it.value().size() || !output.commit())
            return tr("Could not restore bundled CSV files.");
        relocated[it.key()] = dest;
    }
    systems = relocate(systems, relocated).toList(); lists = relocate(lists, relocated).toList();
    const int oldSystems = m_systems->count(), oldLists = m_lists->count();
    auto rollback = [&] {
        while (m_lists->count() > oldLists) { if (!m_lists->remove(m_lists->count() - 1)) break; }
        while (m_systems->count() > oldSystems) { int n = m_systems->count(); m_systems->remove(n - 1); if (m_systems->count() == n) break; }
    };
    QMap<QString, QString> newIds;
    for (const auto& item : systems) {
        auto row = item.toMap();
        if (!m_systems->add(row)) { rollback(); return tr("Could not save restored systems."); }
        newIds[row.value("uid").toString()] = m_systems->get(m_systems->count() - 1).value("uid").toString();
    }
    for (const auto& item : lists) {
        auto row = item.toMap(); row.remove("uid");
        auto entries = row.value("entries").toList();
        for (auto& value : entries) {
            auto e = value.toMap(); if (e.value("kind") == "system") e["systemUid"] = newIds.value(e.value("systemUid").toString());
            value = e;
        }
        row["entries"] = entries;
        if (!m_lists->add(row)) { rollback(); return tr("Could not save restored lists."); }
    }
    const auto prefs = doc.value("preferences").toObject();
    for (const char* name : preferences) if (prefs.contains(name)) m_prefs->setProperty(name, prefs.value(name).toVariant());
    for (const auto& v : doc.value("profiles").toArray()) {
        auto p = v.toObject();
        saveProfile(p.value("name").toString(), p.value("gainDb").toInt(), p.value("ppm").toInt(),
            p.value("bandwidthKhz").toInt(), p.value("biasTee").toBool());
    }
    Q_EMIT changed(); return {};
}
}
