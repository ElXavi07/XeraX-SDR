// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtTest
import "../../upstream/dsd-neo/src/ui/qt/qml" as Ui

Item {
    width: 390
    height: 900
    Ui.ScanListScreen { id: editor; anchors.fill: parent }
    TestCase {
        name: "XeraXScanEditor"
        when: windowShown
        function init() {
            failOnWarning(/.*/);
            while (scanLists.count)
                scanLists.remove(0);
            editor.openFor(-1);
            editor.setDraft("name", "Scanner test");
            editor.addFrequency("Test channel", "dmr", "451.5");
            editor.advancedOpen = true;
            wait(250);
        }
        function cleanup() {
            while (scanLists.count)
                scanLists.remove(0);
        }
        function edit(field, value) {
            field.input.forceActiveFocus();
            field.input.selectAll();
            keyClick(Qt.Key_Backspace);
            for (var i = 0; i < value.length; ++i)
                keyClick(value.charAt(i));
            wait(0);
        }
        function test_preset_to_save_reload() {
            var preset = findChild(editor, "scanPreset1");
            verify(preset !== null);
            preset.activate();
            compare(editor.draft.maxVisitMs, 15000);
            compare(editor.draft.defaultDwellMs, 1000);
            compare(editor.draft.voiceOnly, true);
            var limit = findChild(editor, "scanTuner_maxVisitMs");
            compare(limit.text, "15000");
            verify(editor.validate());
            editor.save();
            compare(scanLists.count, 1);
            editor.openFor(0);
            compare(limit.text, "15000");
            compare(editor.draft.voiceOnly, true);
            if (previewDirectory.length) {
                wait(100);
                grabImage(editor).save(previewDirectory + "/preview-scanner.png");
                editor.advancedOpen = true;
                wait(250);
                var scroll = findChild(editor, "scanListScroll");
                scroll.contentY = Math.max(0, limit.mapToItem(scroll.contentItem, 0, 0).y - 340);
                wait(100);
                grabImage(editor).save(previewDirectory + "/preview-scan-timing.png");
            }
        }
        function test_maximum_visit_validation() {
            editor.advancedOpen = true;
            var limit = findChild(editor, "scanTuner_maxVisitMs");
            for (var text of ["1", "999", "3600001", "-1"]) {
                edit(limit, text);
                verify(limit.error.length > 0, text);
                verify(!editor.validateTunerSettings(), text);
            }
            for (var text of ["", "0", "1000", "15000", "3600000"]) {
                edit(limit, text);
                compare(limit.error, "");
                verify(editor.validateTunerSettings(), text);
                compare(editor.draft.maxVisitMs, text === "" ? -1 : Number(text));
            }
        }
        function test_dwell_lower_bound() {
            var dwell = findChild(editor, "scanTuner_defaultDwellMs");
            edit(dwell, "249");
            verify(dwell.error.length > 0);
            verify(!editor.validateTunerSettings());
            edit(dwell, "250");
            compare(dwell.error, "");
            verify(editor.validateTunerSettings());
        }
    }
}
