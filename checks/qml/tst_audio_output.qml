// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtTest
import "../../upstream/dsd-neo/src/ui/qt/qml" as Ui

Item {
    id: root
    width: 390
    height: 560
    Rectangle { anchors.fill: parent; color: "#0a131a" }
    Ui.AudioOutputPicker { id: picker; x: 20; y: 28; width: parent.width - 40 }
    SignalSpy { id: chosen; target: picker; signalName: "outputSelected" }
    SignalSpy { id: restore; target: picker; signalName: "restoreRequested" }
    SignalSpy { id: test; target: picker; signalName: "testRequested" }
    TestCase {
        name: "XeraXAudioOutput"
        when: windowShown
        function init() {
            failOnWarning(/.*/);
            root.width = 390; root.height = 560;
            chosen.clear();
            picker.errorText = ""; picker.diagnosticsAvailable = false; picker.health = ({}); restore.clear(); test.clear();
            picker.reportedRoute = "Wired headphones";
            picker.routing = {choices: [
                {key: "default", label: "System default"},
                {key: "speaker", label: "Phone speaker"},
                {key: "device:31", label: "Wired headphones · USB-C adapter"},
                {key: "device:42", label: "Bluetooth audio · Earbuds"}],
                selected: "speaker", requestedId: 17, actualId: 31, note: ""};
        }
        function test_speaker_button_and_actual_route() {
            var button = findChild(picker, "usePhoneSpeaker");
            mouseClick(button, button.width / 2, button.height / 2);
            compare(chosen.count, 1);
            compare(chosen.signalArguments[0][0], "speaker");
            verify(picker.routeMismatch);
            verify(findChild(picker, "audioOutputReported").text.indexOf("Wired headphones") >= 0);
            picker.routing = Object.assign({}, picker.routing, {actualId: 17});
            picker.reportedRoute = "Speaker";
            verify(!picker.routeMismatch);
        }
        function test_output_menu_selection() {
            var combo = findChild(picker, "audioOutputSelector");
            compare(combo.currentIndex, 1);
            combo.activated(3);
            compare(chosen.count, 1);
            compare(chosen.signalArguments[0][0], "device:42");
            // Requests do not pretend that the platform accepted a new selection.
            compare(picker.routing.selected, "speaker");
            picker.routing = Object.assign({}, picker.routing, {selected: "device:42", requestedId: 42});
            compare(combo.currentIndex, 3);
            combo.activated(-1);
            combo.activated(99);
            compare(chosen.count, 1);
        }
        function test_removed_device_and_errors() {
            picker.routing = {choices: [{key: "default", label: "System default"}, {key: "speaker", label: "Phone speaker"}],
                selected: "speaker", requestedId: 17, actualId: 17, note: "Selected output disconnected; requesting phone speaker."};
            compare(findChild(picker, "audioOutputSelector").currentIndex, 1);
            verify(findChild(picker, "audioOutputError").visible);
            picker.errorText = "Output is no longer available.";
            compare(findChild(picker, "audioOutputError").text, picker.errorText);
            picker.routing = {};
            verify(!findChild(picker, "usePhoneSpeaker").visible);
            verify(!findChild(picker, "audioOutputSelector").visible);
        }
        function test_audio_diagnostics() {
            root.height = 900;
            picker.diagnosticsAvailable = true;
            picker.health = {focusLost: true};
            verify(findChild(picker, "audioFlowStatus").text.indexOf("another app") >= 0);
            picker.health = {audioPcmArriving: true, audioNonzero: true};
            verify(findChild(picker, "audioFlowStatus").text.indexOf("waiting for Android") >= 0);
            picker.health = {audioPcmArriving: true, audioNonzero: false};
            verify(findChild(picker, "audioFlowStatus").text.indexOf("silence") >= 0);
            picker.health = {audioOutputMoving: true};
            verify(findChild(picker, "audioFlowStatus").text.indexOf("accepting") >= 0);
            var repair = findChild(picker, "restoreSpeakerAudio"), tone = findChild(picker, "testAudioOutput");
            wait(0);
            mouseClick(repair, repair.width / 2, repair.height / 2); compare(restore.count, 1);
            mouseClick(tone, tone.width / 2, tone.height / 2); compare(test.count, 1);
            picker.health = {testingAudio: true};
            verify(!repair.enabled && !tone.enabled);
            picker.health = {audioPcmArriving: true, audioNonzero: true, audioOutputMoving: true};
            try {
                Ui.Theme.fontScale = 1.3;
                for (var width of [320, 390, 480]) {
                    root.width = width; wait(0);
                    verify(picker.height < root.height - picker.y);
                    verify(repair.mapToItem(root, repair.width, 0).x <= root.width);
                }
                root.width = 320; wait(50);
                if (previewDirectory.length) grabImage(root).save(previewDirectory + "/audio-diagnostics-411.png");
            } finally { Ui.Theme.fontScale = 1; }
        }
        function test_layout_and_preview() {
            for (var width of [320, 390, 480]) {
                root.width = width;
                wait(0);
                verify(picker.height < root.height - 28);
                var combo = findChild(picker, "audioOutputSelector");
                verify(combo.mapToItem(root, combo.width, 0).x <= root.width);
            }
            root.width = 390;
            wait(50);
            if (previewDirectory.length) grabImage(root).save(previewDirectory + "/preview-audio-output.png");
        }
    }
}
