// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtTest
import "../../upstream/dsd-neo/src/ui/qt/qml" as Ui

Item {
    id: fixture
    width: 390
    height: 900
    Component { id: settingsComponent; Ui.SettingsScreen {} }
    Loader { id: screenLoader; anchors.fill: parent }
    SignalSpy { id: changes; target: prefs; signalName: "nxdnFastAcquisitionChanged" }

    TestCase {
        name: "NxdnAcquisitionSettings"
        when: windowShown

        function init() {
            failOnWarning(/.*/);
            commands.reset();
            prefs.nxdnFastAcquisition = false;
            appLanguage.language = "en";
            decoderHost.sessionState = 2;
            Ui.Navigation.layers = [];
            Ui.Navigation.modals = [];
            changes.clear();
        }

        function cleanup() {
            screenLoader.sourceComponent = null;
            Ui.Navigation.rootSurfaces = [];
            prefs.nxdnFastAcquisition = false;
            decoderHost.desktopBuild = false;
            appLanguage.language = "en";
        }

        function test_next_session_toggle_data() {
            return [
                { tag: "android-en", desktop: false, language: "en", width: 390 },
                { tag: "android-es", desktop: false, language: "es", width: 390 },
                { tag: "windows-en", desktop: true, language: "en", width: 1024 },
                { tag: "windows-es", desktop: true, language: "es", width: 1024 }
            ];
        }

        function test_next_session_toggle(data) {
            fixture.width = data.width;
            decoderHost.desktopBuild = data.desktop;
            appLanguage.language = data.language;
            screenLoader.sourceComponent = settingsComponent;
            verify(screenLoader.item !== null);
            Ui.Navigation.rootSurfaces = [screenLoader.item];
            var toggle = findChild(screenLoader.item, "nxdnFastAcquisitionToggle");
            verify(toggle !== null);
            compare(toggle.checked, false);
            compare(toggle.title, data.language === "es"
                    ? "Detección más rápida de NXDN48 (experimental)"
                    : "Faster NXDN48 detection (experimental)");
            verify(toggle.subtitle.indexOf("CRC") >= 0);
            verify(toggle.subtitle.indexOf(data.language === "es" ? "próxima vez" : "next time") >= 0);
            var scroll = findChild(screenLoader.item, "settingsScroll");
            scroll.contentY = toggle.mapToItem(scroll.contentItem, 0, 0).y - 16;
            waitForRendering(screenLoader.item);
            mouseClick(toggle, toggle.width / 2, toggle.height / 2);
            compare(prefs.nxdnFastAcquisition, true);
            compare(toggle.checked, true);
            compare(changes.count, 1);
            compare(decoderHost.sessionState, 2);
            if (previewDirectory.length) {
                wait(160); // Let the switch animation settle in the saved preview.
                grabImage(screenLoader.item).save(previewDirectory + "/nxdn-acquisition-" + data.tag + ".png");
            }

            // Reopening Settings preserves the choice. The running session is untouched.
            screenLoader.sourceComponent = null;
            screenLoader.sourceComponent = settingsComponent;
            Ui.Navigation.rootSurfaces = [screenLoader.item];
            toggle = findChild(screenLoader.item, "nxdnFastAcquisitionToggle");
            compare(toggle.checked, true);
            toggle.forceActiveFocus();
            keyClick(Qt.Key_Space);
            compare(prefs.nxdnFastAcquisition, false);
            compare(toggle.checked, false);
            compare(changes.count, 2);
            compare(decoderHost.sessionState, 2);
        }
    }
}
