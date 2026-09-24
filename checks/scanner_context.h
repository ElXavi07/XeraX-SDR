#include "receiver_expansion.h"
#include "call_library.h"
// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QGuiApplication>
#include <QFontDatabase>
#include <QQmlContext>
#include <QQmlEngine>
#include <QQmlPropertyMap>
#include <QStandardPaths>
#include <QUuid>
#include "app_prefs.h"
#include "saved_systems_model.h"
#include "scan_lists_model.h"
#include "scan_list_targets.h"
#include "session_args.h"
#include "spectrum_model.h"
#include "spectrum_view_item.h"
#include "site_groups.h"
#include "radio_fixture.h"
#include "rr_fixture.h"
#include "receiver_tools.h"
#include "receiver_assistant.h"
#include "ai_receiver.h"
#include "range_scanner.h"
#include "app_language.h"
#include "decryption_profiles_model.h"

// External file picking is outside this test. The scan store, argument validator,
// and target generator are the production implementations.
class FixtureImports : public QObject {
    Q_OBJECT
    Q_PROPERTY(int count READ count CONSTANT)
public:
    using QObject::QObject;
    int count() const { return 0; }
    Q_INVOKABLE QVariantList entriesForType(const QString&) const { return {}; }
};

class FixtureScanStarter : public QObject {
    Q_OBJECT
public:
    using QObject::QObject;
    Q_INVOKABLE QVariantMap validate(const QVariantMap& list) const {
        const auto result = dsd_qt::scan_list_targets(list, {});
        return {{"ok", result.ok}, {"targetCount", result.targetCount},
                {"warnings", result.warnings}, {"error", result.error}};
    }
};

class ScannerSetup : public QObject {
    Q_OBJECT
public Q_SLOTS:
    void applicationAvailable() {
        qmlRegisterType<dsd_qt::SiteInteractionGuard>("DsdNeo", 1, 0, "SiteInteractionGuard");
        qmlRegisterType<dsd_qt::SpectrumTraceItem>("DsdNeo", 1, 0, "SpectrumTrace");
        qmlRegisterType<dsd_qt::WaterfallItem>("DsdNeo", 1, 0, "Waterfall");
        qputenv("QT_QUICK_CONTROLS_STYLE", "Basic");
        QStandardPaths::setTestModeEnabled(true);
        QCoreApplication::setOrganizationName("XeraXTests");
        QCoreApplication::setApplicationName("qml-" + QUuid::createUuid().toString(QUuid::WithoutBraces));
        QFontDatabase::addApplicationFont(QStringLiteral(XERAX_QML_DIR "/../fonts/IBMPlexSans-Regular.ttf"));
        QFontDatabase::addApplicationFont(QStringLiteral(XERAX_QML_DIR "/../fonts/IBMPlexMono-Regular.ttf"));
    }
    void qmlEngineAvailable(QQmlEngine* engine) {
        auto* context = engine->rootContext();
        auto* prefs = new dsd_qt::AppPrefs(engine);
        prefs->setAppearance(2);
        auto* systems = new dsd_qt::SavedSystemsModel(engine);
        auto* args = new dsd_qt::SessionArgsBuilder(prefs, engine);
        args->setSavedSystems(systems);
        context->setContextProperty("prefs", prefs);
        context->setContextProperty("sessionArgs", args);
        auto* lists = new dsd_qt::ScanListsModel(engine);
        context->setContextProperty("scanLists", lists);
        auto* decryption = new dsd_qt::DecryptionProfilesModel(engine);
        decryption->setReferences(systems, lists);
        context->setContextProperty("decryptionProfiles", decryption);
        context->setContextProperty("receiverTools", new dsd_qt::ReceiverTools(prefs, systems, lists, nullptr, engine));
        context->setContextProperty("savedSystems", systems);
        context->setContextProperty("importedFiles", new FixtureImports(engine));
        context->setContextProperty("scanListStarter", new FixtureScanStarter(engine));
        auto* metrics = QQmlPropertyMap::create(engine);
        const QVariantMap values = {{"tunerControlled", false}, {"centerFreqHz", 851000000},
            {"syncedHere", false}, {"snrValid", false}, {"snrDb", 0.0}, {"cfoHz", 0.0},
            {"syncLabel", ""}, {"slot1CallState", 0}, {"slot2CallState", 0},
            {"radioInput", true}, {"channelBandwidthHz", 12500}, {"uiMessage", ""},
            {"trunkableSync", false}, {"scannerMode", false}, {"trunkingEnabled", false},
            {"tunerGainDb", 0}, {"ppm", 0}, {"squelchDb", -120.0}, {"squelchOff", true},
            {"modulation", 0}, {"optionsKnown", true}, {"streamActive", true}, {"audioMuted", false},
            {"airspy", QVariantMap{}}};
        for (auto it = values.begin(); it != values.end(); ++it) metrics->insert(it.key(), it.value());
        auto* radio = new RadioFixture(engine);
        radio->metrics = metrics;
        radio->reset();
        context->setContextProperty("metrics", metrics);
        context->setContextProperty("commands", radio);
        auto* host = QQmlPropertyMap::create(engine);
        host->insert("running", true);
        host->insert("sessionState", 2);
        host->insert("sessionActive", true);
        host->insert("audioRoute", "Speaker");
        host->insert("audioOutput", QVariantMap{});
        host->insert("locationSupported", false);
        context->setContextProperty("decoderHost", host);
        auto* assistant = new dsd_qt::ReceiverAssistant(engine);
        assistant->configure(metrics, radio, host, nullptr, systems);
        assistant->poll();
        context->setContextProperty("receiverAssistant", assistant);
        context->setContextProperty("receiverExpansion",new dsd_qt::ReceiverExpansion(engine));
        context->setContextProperty("aiReceiver",new dsd_qt::AiReceiver(engine));
        auto* rangeScanner=new dsd_qt::RangeScanner(engine);
        rangeScanner->configure(metrics,radio,host,nullptr,nullptr,assistant,nullptr,systems);
        context->setContextProperty("rangeScanner",rangeScanner);
        context->setContextProperty("callLibrary",new dsd_qt::CallLibrary(engine));
        context->setContextProperty("appLanguage", new dsd_qt::AppLanguage(engine, QStringLiteral(XERAX_QML_DIR "/../i18n/es.json")));
        context->setContextProperty("radioReference", new RrFixture(engine));
        context->setContextProperty("spectrum", new dsd_qt::SpectrumModel(engine));
        context->setContextProperty("sansFontFamily", "IBM Plex Sans");
        context->setContextProperty("monoFontFamily", "IBM Plex Mono");
        context->setContextProperty("previewDirectory", QString::fromLocal8Bit(qgetenv("XERAX_PREVIEW_DIR")));
    }
};
