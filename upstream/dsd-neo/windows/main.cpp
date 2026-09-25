// SPDX-License-Identifier: GPL-3.0-or-later
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQuickWindow>
#include <QQuickItem>
#include <QTimer>
#include <QDir>
#include <QStandardPaths>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QImage>
#include <QQmlContext>
#include <QSettings>
#include <memory>
#include <dsd-neo/platform/audio_replay.h>
#include "desktop_host.h"
#include "desktop_media.h"
#include "qt_ui.h"

static void smokeTrace(const char* phase) {
    const auto path=qEnvironmentVariable("XERAX_SMOKE_TRACE");
    if(path.isEmpty()) return;
    QFile file(path);
    if(file.open(QIODevice::WriteOnly|QIODevice::Append)) {file.write(phase);file.write("\n");}
}

int main(int argc,char** argv) {
    if(qEnvironmentVariableIsSet("XERAX_SMOKE_TRACE")) qInstallMessageHandler([](QtMsgType,const QMessageLogContext&,const QString& message) {
        QFile file(qEnvironmentVariable("XERAX_SMOKE_TRACE")+".qml.log");
        if(file.open(QIODevice::WriteOnly|QIODevice::Append)) {file.write(message.toUtf8());file.write("\n");}
    });
    smokeTrace("main");
    dsd_qt::ui_apply_style();
    smokeTrace("style");
    QGuiApplication app(argc,argv);
    smokeTrace("application");
    app.setApplicationName("XeraX SDR");
    app.setOrganizationName("XeraX");
    app.setApplicationVersion("4.3.0-windows.1");
    const auto args=app.arguments();
    const int test=args.indexOf("--smoke-seconds");
    if(test>=0) {
        QStandardPaths::setTestModeEnabled(true);
        app.setOrganizationName("XeraX-SDR-Tests");
    }
    // Desktop application storage is writable even when installed under Program Files.
    const auto dataPath=QStandardPaths::writableLocation(QStandardPaths::AppLocalDataLocation);
    QDir().mkpath(dataPath+"/preferences");
    QDir::setCurrent(dataPath);
    // AppPrefs has explicit upstream INI names. Keep it inside this app's own
    // directory, including for smoke tests, rather than sharing upstream settings.
    QSettings::setDefaultFormat(QSettings::IniFormat);
    QSettings::setPath(QSettings::IniFormat,QSettings::UserScope,dataPath+"/preferences");
    if(test>=0) {
        QSettings().setValue("ui/language",qEnvironmentVariable("XERAX_SMOKE_LANGUAGE","en"));
        QSettings prefs(QSettings::IniFormat,QSettings::UserScope,"dsd-neo","dsd-neo-app");
        prefs.setValue("ui/onboardingDone",qEnvironmentVariableIsSet("XERAX_SMOKE_HOME"));
    }
    DesktopHost host;
    QQmlApplicationEngine engine;
    smokeTrace("before-ui-load");
    if(!dsd_qt::ui_load(engine,&host)) return 1;
    smokeTrace("after-ui-load");
    engine.rootContext()->setContextProperty("appVersionText",QString("4.3.0 — Windows preview 1"));
    auto* window=qobject_cast<QQuickWindow*>(engine.rootObjects().first());
    if(window) { window->resize(1050,800); window->setMinimumSize(QSize(420,620)); window->setTitle("XeraX SDR 4.3.0 — Windows preview"); }
    if(test>=0 && window && qEnvironmentVariableIsSet("XERAX_SMOKE_HIDDEN")) window->hide();
    // Explicit, local developer smoke mode uses the real host/engine and bounded exit.
    if(test>=0 && test+1<args.size()) {
        bool ok=false; int seconds=args[test+1].toInt(&ok);
        if(!ok || seconds<1 || seconds>120) return 2;
        const int input=args.indexOf("--receiver-args");
        auto smokeDetails=std::make_shared<QVariantMap>();
        if(qEnvironmentVariableIsSet("XERAX_SMOKE_TONES")) dsd_qt::desktop_test_audio();
        const auto wav=qEnvironmentVariable("XERAX_SMOKE_WAV");
        if(!wav.isEmpty()) {
            (*smokeDetails)["playError"]=dsd_qt::desktop_play(wav);
            (*smokeDetails)["playbackStarted"]=dsd_qt::desktop_media_health().value("replaying");
        }
        if(qEnvironmentVariableIsSet("XERAX_SMOKE_GATE")) {
            QTimer::singleShot(4000,&app,[smokeDetails] {
                dsd_audio_range_suppress(1);
                (*smokeDetails)["gateOutputStart"]=qulonglong(dsd_audio_output_frames());
                (*smokeDetails)["gatePcmStart"]=qulonglong(dsd_audio_received_frames());
            });
            QTimer::singleShot(6000,&app,[smokeDetails] {
                (*smokeDetails)["gateOutputDelta"]=qulonglong(dsd_audio_output_frames()-smokeDetails->value("gateOutputStart").toULongLong());
                (*smokeDetails)["gatePcmDelta"]=qulonglong(dsd_audio_received_frames()-smokeDetails->value("gatePcmStart").toULongLong());
                dsd_audio_range_suppress(0);
            });
        }
        if(input>=0) QTimer::singleShot(250,&host,[&host,args,input] { host.start(args.mid(input+1)); });
        QTimer::singleShot(seconds*1000,&app,[&app,&host,window,smokeDetails] {
            smokeTrace("smoke-timer");
            if(window) {
                for(const auto* name:{"monitorMode","wizardOpen","currentTab","exploreSetupOpen","diagnosticsOpen","licensesOpen","radioReferenceAccountOpen","importsOpen","radioReferenceOpen","scanListOpen","sessionDestination"})
                    (*smokeDetails)[name]=window->property(name);
                for(const auto* name:{"homeScreen","safeArea"}) {
                    auto* item=window->findChild<QQuickItem*>(name);
                    if(item) (*smokeDetails)[name]=QVariantMap{{"width",item->width()},{"height",item->height()},{"visible",item->isVisible()},{"parentVisible",item->parentItem()->isVisible()},{"parentOpacity",item->parentItem()->opacity()}};
                }
            }
            const auto out=qEnvironmentVariable("XERAX_SMOKE_REPORT");
            if(!out.isEmpty()) {
                QFile file(out);
                if(file.open(QIODevice::WriteOnly)) file.write(QJsonDocument(QJsonObject{
                    {"state",int(host.sessionState())},{"pcmFrames",double(dsd_audio_received_frames())},
                    {"nonzeroFrames",double(dsd_audio_nonzero_frames())},{"outputFrames",double(dsd_audio_output_frames())},
                    {"media",QJsonObject::fromVariantMap(dsd_qt::desktop_media_health())},
                    {"details",QJsonObject::fromVariantMap(*smokeDetails)},
                    {"suppressed",dsd_audio_live_suppressed()!=0},
                    {"failure",host.failureText()}}).toJson());
            }
            const auto screenshot=qEnvironmentVariable("XERAX_SMOKE_SCREENSHOT");
            if(window && !screenshot.isEmpty()) window->grabWindow().save(screenshot);
            host.stop();
            app.quit();
        });
    }
    smokeTrace("event-loop");
    return app.exec();
}
