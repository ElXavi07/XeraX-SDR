// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtTest
import "../../upstream/dsd-neo/src/ui/qt/qml" as Ui
Item {
    id: fixture; width: 390; height: 900
    Ui.ReceiverToolsScreen { id: tools; anchors.fill: parent }
    TestCase {
        name: "ReceiverAssistantAndSpanish"; when: windowShown
        function init() { failOnWarning(/.*/); appLanguage.language = "en"; fixture.width = 390; tools.page = 0; tools.message = ""; tools.visible = true; }
        function cleanup() { appLanguage.language = "en"; Ui.Theme.resetFontScale(); }
        function test_language_updates_in_place() {
            compare(findChild(tools, "receiverTab0").text, "Quality");
            appLanguage.language = "es";
            tryCompare(findChild(tools, "receiverTab0"), "text", "Calidad");
            compare(findChild(tools, "speakerRecovery").text, "Usar altavoz del teléfono");
            appLanguage.language = "en";
            tryCompare(findChild(tools, "receiverTab0"), "text", "Quality");
        }
        function test_narrow_spanish_pages() {
            appLanguage.language = "es"; fixture.width = 320; Ui.Theme.fontScale = 1.3;
            for (var page = 0; page < 4; page++) {
                tools.page = page; wait(50);
                var tab = findChild(tools, "receiverTab" + page);
                verify(tab.width >= 48); verify(tab.height >= 48);
                var pos = tab.mapToItem(tools, 0, 0); verify(pos.x + tab.width <= tools.width);
                if (previewDirectory.length) grabImage(tools).save(previewDirectory + "/assistant-es-320-" + page + ".png");
            }
        }
        function test_english_preview() {
            wait(50);
            if (previewDirectory.length) grabImage(tools).save(previewDirectory + "/assistant-en-390.png");
        }
        function test_channel_rule_validation() {
            tools.page = 1; tools.loadFilter();
            var frequency = findChild(tools, "filterFrequency");
            frequency.text = "invalid"; tools.applyFilter(); verify(tools.message.length > 0);
            frequency.text = "155.250000"; tools.applyFilter();
            compare(receiverAssistant.filter(155250000).color, -1);
            receiverAssistant.clearFilter(155250000);
        }
        function test_main_compiles() {
            var component = Qt.createComponent("../../upstream/dsd-neo/src/ui/qt/qml/Main.qml");
            compare(component.status, Component.Ready, component.errorString());
        }
        function test_adp_profile_guided_entry() {
            tools.page = 3;
            findChild(tools, "createAdpProfile").clicked();
            var editor = findChild(tools, "adpProfileEditor");
            verify(editor.visible); compare(editor.draft.directType, "adp");
            findChild(editor, "decryptionProfileName").text = "Fixture ADP";
            var material = findChild(editor, "profileDirectMaterial");
            material.text = "123456789"; editor.save(); verify(editor.visible); verify(editor.errorText.length > 0);
            material.text = "0001020304";
            var before = decryptionProfiles.count;
            editor.save(); verify(!editor.visible); compare(decryptionProfiles.count, before + 1);
            compare(material.text, "");
            verify(JSON.stringify(decryptionProfiles.entries()).indexOf("0001020304") < 0);
        }
        function test_automatic_key_setup() {
            tools.page = 3;
            var editor = findChild(tools, "adpProfileEditor");
            findChild(tools, "createAutomaticKeys").clicked();
            compare(editor.draft.mode, "automatic"); compare(editor.draft.keySource, "managed");
            editor.visible = false;
            findChild(tools, "createNxdnKeys").clicked();
            compare(editor.draft.protocol, "nxdn"); compare(editor.draft.mode, "automatic");
            verify(editor.kinds.indexOf("scrambler") >= 0);
            editor.visible = false;
        }
    }
}
