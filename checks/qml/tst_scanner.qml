// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtTest
import "../../upstream/dsd-neo/src/ui/qt/qml" as Ui

Item {
    width: 390
    height: 900
    Ui.ScanProfiles { id: profiles; width: parent.width }
    Rectangle {
        id: receptionPreview
        width: parent.width
        height: reception.implicitHeight + 32
        y: 380
        color: Ui.Theme.bg
        Ui.ReceptionCheck { id: reception; width: parent.width - 32; x: 16; y: 16; expanded: true }
    }
    SignalSpy { id: chosen; target: profiles; signalName: "chosen" }
    SignalSpy { id: squelch; target: reception; signalName: "disableSquelch" }

    TestCase {
        name: "XeraXScanner"
        when: windowShown
        function receiver(overrides) {
            return Object.assign({optionsKnown: true, radioInput: true, streamActive: true,
                airspy: {}, audioMuted: false, squelchOff: true, syncedHere: false,
                snrValid: false, snrDb: 99, syncLabel: "DMR", slot1CallState: 0,
                slot2CallState: 0, slot1CallEnc: false, slot2CallEnc: false}, overrides || {});
        }
        function init() {
            chosen.clear(); squelch.clear();
            profiles.settings = {};
            reception.sessionRunning = true;
            reception.receiver = receiver();
        }
        function test_presets() {
            var expected = [
                {defaultDwellMs: 3000, defaultHoldMs: 1200, maxVisitMs: 0, voiceOnly: false},
                {defaultDwellMs: 1000, defaultHoldMs: 800, maxVisitMs: 15000, voiceOnly: true},
                {defaultDwellMs: 5000, defaultHoldMs: 2000, maxVisitMs: 0, voiceOnly: false}
            ];
            for (var i = 0; i < 3; ++i) {
                profiles.choose(i);
                compare(chosen.count, i + 1);
                compare(chosen.signalArguments[i][0], expected[i]);
                profiles.settings = chosen.signalArguments[i][0];
                compare(profiles.selectedIndex, i);
            }
            profiles.settings = Object.assign({}, profiles.settings, {maxVisitMs: 30000});
            compare(profiles.selectedIndex, -1);
            profiles.choose(-1); profiles.choose(99);
            compare(chosen.count, 3);
        }
        function test_status_data() {
            return [
                {tag: "starting", fields: {optionsKnown: false}, code: "starting"},
                {tag: "no samples", fields: {streamActive: false}, code: "no_samples"},
                {tag: "Airspy is not RTL stream", fields: {streamActive: false, airspy: {gain_mode: 0}}, code: "no_sync"},
                {tag: "muted", fields: {audioMuted: true}, code: "muted"},
                {tag: "squelch", fields: {squelchOff: false}, code: "squelch"},
                {tag: "sync", fields: {syncedHere: true}, code: "synced"},
                {tag: "private slot 2", fields: {syncedHere: true, slot2CallState: 2, slot2CallEnc: true}, code: "private_call"},
                {tag: "stale privacy flag", fields: {syncedHere: true, slot1CallState: 0, slot1CallEnc: true}, code: "synced"},
                {tag: "audio source", fields: {radioInput: false, streamActive: false, squelchOff: false}, code: "no_sync"}
            ];
        }
        function test_status(data) {
            reception.receiver = receiver(data.fields);
            compare(reception.statusCode, data.code);
            reception.sessionRunning = false;
            compare(reception.statusCode, "idle");
            compare(findChild(reception, "receptionCheckMeasurements").text, "");
        }
        function test_measurements_and_manual_action() {
            var summary = findChild(reception, "receptionCheckMeasurements");
            compare(summary.text, ""); // invalid 99 dB is not displayed
            reception.receiver = receiver({snrValid: true, snrDb: 12.5, squelchOff: false});
            verify(summary.text.indexOf("12.5") >= 0);
            var action = findChild(reception, "receptionCheckSquelchOff");
            verify(action.visible);
            action.activate();
            compare(squelch.count, 1);
            // A request must not make the UI claim that the engine accepted it.
            compare(reception.statusCode, "squelch");
            reception.receiver = receiver({squelchOff: true});
            verify(!action.visible);
            compare(reception.statusCode, "no_sync");
            reception.receiver = receiver({snrValid: true, snrDb: NaN});
            compare(summary.text, "");
            reception.receiver = receiver({radioInput: false, snrValid: true, snrDb: 12.5});
            compare(summary.text, "");
            if (previewDirectory.length) {
                reception.receiver = receiver({snrValid: true, snrDb: 12.5, squelchOff: false});
                wait(100);
                grabImage(receptionPreview).save(previewDirectory + "/preview-reception.png");
            }
        }
        function test_phone_widths() {
            for (var w of [320, 390, 480]) {
                profiles.width = w;
                reception.width = w;
                wait(0);
                for (var name of ["receptionCheckTitle", "receptionCheckDetail", "receptionCheckSquelchOff"]) {
                    var item = findChild(reception, name);
                    verify(item.width <= w);
                }
                verify(findChild(profiles, "scanPresetDescription").width <= w);
            }
        }
    }
}
