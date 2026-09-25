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
#include <QIcon>
#include <windows.h>
#include <shobjidl.h>
#include <memory>
#include <dsd-neo/platform/audio_replay.h>
#include "desktop_host.h"
#include "desktop_media.h"
#include "qt_ui.h"
#include "ai_transport.h"

static void smokeTrace(const char* phase) {
    const auto path=qEnvironmentVariable("XERAX_SMOKE_TRACE");
    if(path.isEmpty()) return;
    QFile file(path);
    if(file.open(QIODevice::WriteOnly|QIODevice::Append)) {file.write(phase);file.write("\n");}
}

// Repeater delegates belong to the visual tree but may have a different QObject
// owner. Use the same rendered controls the user can reach with mouse/keyboard.
static QQuickItem* visualItem(QQuickItem* root,const QString& name) {
    if(!root) return nullptr;
    if(root->objectName()==name) return root;
    for(auto* child:root->childItems()) if(auto* found=visualItem(child,name)) return found;
    return nullptr;
}

int main(int argc,char** argv) {
    SetCurrentProcessExplicitAppUserModelID(L"XeraX.SDR.Desktop");
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
    app.setApplicationVersion("4.3.2-rc.2-windows.1");
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
        prefs.setValue("ui/appearance",qEnvironmentVariable("XERAX_SMOKE_APPEARANCE","2").toInt());
    }
    DesktopHost host;
    QQmlApplicationEngine engine;
    smokeTrace("before-ui-load");
    if(!dsd_qt::ui_load(engine,&host)) return 1;
    smokeTrace("after-ui-load");
    engine.rootContext()->setContextProperty("appVersionText",QString("4.3.2-rc.2 — Windows preview 1"));
    app.setWindowIcon(QIcon(":/dsdneo/qml/xerax-icon.svg"));
    auto* window=qobject_cast<QQuickWindow*>(engine.rootObjects().first());
    if(window) { window->resize(1240,840); window->setMinimumSize(QSize(420,620)); window->setTitle("XeraX SDR 4.3.2-rc.2 — Windows preview 1"); }
    if(test>=0 && window && qEnvironmentVariableIsSet("XERAX_SMOKE_HIDDEN")) window->hide();
    // Explicit, local developer smoke mode uses the real host/engine and bounded exit.
    if(test>=0 && test+1<args.size()) {
        bool ok=false; int seconds=args[test+1].toInt(&ok);
        if(!ok || seconds<1 || seconds>120) return 2;
        const int input=args.indexOf("--receiver-args");
        auto smokeDetails=std::make_shared<QVariantMap>();
        if(qEnvironmentVariableIsSet("XERAX_SMOKE_TLS")) {
            auto* probe=new dsd_qt::AiTransport(&app);
            QObject::connect(probe,&dsd_qt::AiTransport::completed,&app,[smokeDetails](quint64 id,int status,const QByteArray&) {
                (*smokeDetails)[id==101?"openaiTlsHttpStatus":"deepseekTlsHttpStatus"]=status;
            });
            // No account or paid request: both providers must reject this fixture.
            probe->send(101,"openai","/models","fixture-only-never-a-real-api-key",{});
            probe->send(102,"deepseek","/models","fixture-only-never-a-real-api-key",{});
        }
        if(window) {
            const auto size=qEnvironmentVariable("XERAX_SMOKE_SIZE").split('x');
            if(size.size()==2) window->resize(size[0].toInt(),size[1].toInt());
            QTimer::singleShot(600,&app,[window,smokeDetails] {
                // Activate real UI controls and let their handlers own navigation.
                const auto route=qEnvironmentVariable("XERAX_SMOKE_ROUTE");
                QString object;
                if(route=="receiver") object="desktopConfigureReceiver";
                else if(route=="range" || route=="range-close") object="desktopScanFrequencies";
                else if(route=="scan" || route=="scan-range" || route=="lab") object="desktopNav1";
                else if(route=="calls") object="desktopNav2";
                else if(route=="tools" || route=="quality") object="desktopNav3";
                else if(route=="ai") object="desktopAiButton";
                if(!object.isEmpty()) {
                    auto* control=visualItem(window->contentItem(),object);
                    (*smokeDetails)["routeActivated"]=control && QMetaObject::invokeMethod(control,object.startsWith("desktopNav")?"choose":"activate");
                }
            });
            QTimer::singleShot(1000,&app,[window,smokeDetails] {
                const auto route=qEnvironmentVariable("XERAX_SMOKE_ROUTE");
                if(route=="quality") {
                    auto* control=visualItem(window->contentItem(),"settingsReceiverTools");
                    (*smokeDetails)["qualityOpened"]=control && QMetaObject::invokeMethod(control,"tapped");
                }
                if(route=="scan-range" || route=="lab") {
                    auto* control=visualItem(window->contentItem(),route=="lab"?"desktopOpenLab":"desktopStartRange");
                    (*smokeDetails)["secondActionActivated"]=control && QMetaObject::invokeMethod(control,"activate");
                }
                if(route=="range-close") {
                    auto* screen=window->findChild<QObject*>("exploreSetupScreen");
                    (*smokeDetails)["closeActivated"]=screen && QMetaObject::invokeMethod(screen,"requestClose");
                }
            });
        }
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
                (*smokeDetails)["windowIconAvailable"]=!window->icon().isNull();
                for(const auto* name:{"monitorMode","wizardOpen","currentTab","exploreSetupOpen","diagnosticsOpen","licensesOpen","radioReferenceAccountOpen","importsOpen","radioReferenceOpen","scanListOpen","sessionDestination","desktopLabOpen"})
                    (*smokeDetails)[name]=window->property(name);
                for(const auto* name:{"homeScreen","safeArea","desktopSidebar","desktopScanScreen","desktopLabScreen","exploreSetupScreen","aiReceiverScreen"}) {
                    auto* item=visualItem(window->contentItem(),name);
                    if(item) (*smokeDetails)[name]=QVariantMap{{"width",item->width()},{"height",item->height()},{"visible",item->isVisible()},{"parentVisible",item->parentItem()->isVisible()},{"parentOpacity",item->parentItem()->opacity()}};
                }
                if(auto* setup=window->findChild<QObject*>("exploreSetupScreen")) (*smokeDetails)["rangeMode"]=setup->property("rangeMode");
            }
            const auto out=qEnvironmentVariable("XERAX_SMOKE_REPORT");
            if(!out.isEmpty()) {
                QFile file(out);
                if(file.open(QIODevice::WriteOnly)) file.write(QJsonDocument(QJsonObject{
                    {"state",int(host.sessionState())},{"pcmFrames",double(dsd_audio_received_frames())},
                    {"nonzeroFrames",double(dsd_audio_nonzero_frames())},{"outputFrames",double(dsd_audio_output_frames())},
                    {"media",QJsonObject::fromVariantMap(dsd_qt::desktop_media_health())},
                    {"hardware",QJsonObject::fromVariantMap(host.decoderHardware())},
                    {"details",QJsonObject::fromVariantMap(*smokeDetails)},
                    {"suppressed",dsd_audio_live_suppressed()!=0},
                    {"failure",host.failureText()}}).toJson());
            }
            const auto screenshot=qEnvironmentVariable("XERAX_SMOKE_SCREENSHOT");
            if(window && !screenshot.isEmpty()) window->grabWindow().save(screenshot);
            host.stop();
            // A mobile-style back handler can veto quit to leave a subpage.
            // A bounded developer run exits its event loop directly.
            if(window && qEnvironmentVariableIsSet("XERAX_SMOKE_NATIVE_CLOSE")) window->close();
            else app.exit(0);
        });
    }
    smokeTrace("event-loop");
    return app.exec();
}
