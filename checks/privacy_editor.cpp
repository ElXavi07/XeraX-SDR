// SPDX-License-Identifier: GPL-3.0-or-later
#include <QGuiApplication>
#include <QQuickView>
#include <QQuickItem>
#include <QQmlContext>
#include <QStandardPaths>
#include <QThread>
#include <QImage>
#include <QFontDatabase>
#include <cstdio>
#include "session_args.h"

int main(int argc, char **argv) {
    QGuiApplication app(argc, argv);
    QStandardPaths::setTestModeEnabled(true);
    dsd_qt::SessionArgsBuilder builder(nullptr);
    QQuickView view;
    const int sans = QFontDatabase::addApplicationFont(QStringLiteral(XERAX_QML_DIR "/../fonts/IBMPlexSans-Regular.ttf"));
    const int mono = QFontDatabase::addApplicationFont(QStringLiteral(XERAX_QML_DIR "/../fonts/IBMPlexMono-Regular.ttf"));
    if (sans < 0 || mono < 0) return 1;
    view.rootContext()->setContextProperty("sansFontFamily", QFontDatabase::applicationFontFamilies(sans).first());
    view.rootContext()->setContextProperty("monoFontFamily", QFontDatabase::applicationFontFamilies(mono).first());
    view.setColor(QColor("#0A1219"));
    view.rootContext()->setContextProperty("sessionArgs", &builder);
    view.setSource(QUrl::fromLocalFile(QStringLiteral(XERAX_QML_DIR "/EncryptionEditor.qml")));
    if (view.status() != QQuickView::Ready) return 1;
    auto *editor = view.rootObject();
    editor->setProperty("width", 390);
    view.setResizeMode(QQuickView::SizeRootObjectToView);
    view.resize(420, 700);
    int failures = 0;
    auto check = [&](const char *protocol, const char *type, const char *value, bool expected) {
        editor->setProperty("protocol", protocol);
        editor->setProperty("keyType", type);
        editor->setProperty("keyValue", value);
        QCoreApplication::processEvents();
        if (editor->property("valid").toBool() != expected) {
            std::fprintf(stderr, "Privacy editor validation failed for %s/%s\n", protocol, type);
            failures++;
        }
    };
    check("dmr", "basic", "0", true);
    check("dmr", "basic", "255", true);
    check("dmr", "basic", "256", false);
    check("dmr", "basic", "-1", false);
    check("dmr", "rc4", "0011223344", true);
    check("dmr", "rc4", "not-hex", false);
    check("nxdn", "scrambler", "0", true);
    check("nxdn", "scrambler", "32767", true);
    check("nxdn", "scrambler", "32768", false);
    check("p25", "basic", "1", false);
    check("nxdn", "scrambler", "32767", true);
    view.show();
    for (int i=0; i<8; i++) { QCoreApplication::processEvents(); QThread::msleep(20); }
    if (argc > 1 && !view.grabWindow().save(QString::fromLocal8Bit(argv[1]))) {
        std::fprintf(stderr, "Could not render privacy editor preview\n");
        failures++;
    }
    std::fprintf(stderr, "%d privacy editor failures\n", failures);
    return failures ? 1 : 0;
}
