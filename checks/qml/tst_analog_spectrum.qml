// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtTest
import "../../upstream/dsd-neo/src/ui/qt/qml" as Ui
import "../../upstream/dsd-neo/src/ui/qt/qml/Util.js" as Util

Item {
    id: root
    width: 390
    height: 900
    Ui.SpectrumScreen { id: screen; anchors.fill: parent; exploring: true; sharedRadioSheet: radio }
    Ui.RadioSheet { id: radio; anchors.fill: parent; canRestartMode: true }
    Ui.ExploreSetupScreen { id: setup; anchors.fill: parent; visible: false }
    Ui.ReceptionCheck { id: reception; width: 340; visible: false; receiver: metrics; sessionRunning: true; analogMode: radio.analogMode }
    SignalSpy { id: modeRestart; target: radio; signalName: "restartModeRequested" }
    SignalSpy { id: started; target: setup; signalName: "start" }
    TestCase {
        name: "XeraXAnalogAndSpectrum"
        when: windowShown
        function init() {
            failOnWarning(/.*/);
            commands.reset();
            screen.exploring = true;
            screen.fineSwipe = true;
            screen.tuningStepHz = 12500;
            screen.hint = "";
            screen.cancelSwipe();
            screen.stopSweep();
            screen.visible = true;
            radio.visible = false;
            radio.canRestartMode = true;
            setup.visible = false;
            started.clear(); modeRestart.clear();
            tryVerify(function() { return spectrum.hasData; });
            spectrum.resetView();
        }
        function cleanup() { radio.visible = false; setup.visible = false; screen.cancelSwipe(); }
        function test_analog_setup_builds_real_startup_arguments() {
            screen.visible = false;
            setup.visible = true;
            setup.reset("usb", "", 1234, "155.5125", "-fa");
            var chip = findChild(setup, "exploreAnalogMode");
            verify(chip !== null);
            chip.activate();
            compare(setup.decodeFlag, "-fA");
            setup.submit();
            compare(started.count, 1);
            compare(started.signalArguments[0][4], "-fA");
            var args = sessionArgs.build({sourceType: "usb", freqMhz: "155.5125", decodeFlag: setup.decodeFlag, trunking: false});
            verify(args.ok, JSON.stringify(args));
            verify(commands.startupArgs({sourceType: "usb", freqMhz: "155.5125", decodeFlag: setup.decodeFlag, trunking: false}).indexOf("-fA") >= 0);
            prefs.exploreDecodeFlag = "-fA";
            setup.reset("usb", "", 1234, "155.5125", prefs.exploreDecodeFlag);
            compare(setup.decodeFlag, "-fA");
            if (previewDirectory.length) grabImage(root).save(previewDirectory + "/preview-analog-setup.png");
        }
        function test_live_analog_requests_full_restart_and_back() {
            radio.open();
            findChild(radio, "radioDecode_NFM").activate();
            compare(modeRestart.count, 1);
            compare(modeRestart.signalArguments[0][0], "-fA");
            compare(commands.decodeCount, 0);
            commands.metric("decodeMode", commands.decodeModeForFlag("-fA"));
            compare(radio.analogMode, true);
            compare(reception.statusCode, "analog");
            verify(!findChild(radio, "radioModulation").visible);
            findChild(radio, "radioDecode_DMR").activate();
            compare(modeRestart.count, 2);
            compare(modeRestart.signalArguments[1][0], "-fs");
            compare(commands.decodeCount, 0);
            radio.canRestartMode = false;
            findChild(radio, "radioDecode_DMR").activate();
            compare(modeRestart.count, 2);
        }
        function test_digital_to_digital_remains_live() {
            radio.selectDecode("-fi");
            compare(commands.decodeCount, 1);
            compare(modeRestart.count, 0);
        }
        function test_protocol_catalog_and_privacy_mapping() {
            var expected = ["-fA", "-fa", "-ft", "-f1", "-f2 -mq", "-fs", "-fr", "-fi", "-fn", "-fd", "-fy", "-fz", "-fm", "-fx", "-fp", "-fh", "-fH", "-fe", "-fE"];
            expected.forEach(function(flag) {
                var entry = Util.findDecodeMode(flag);
                verify(entry !== null, "missing mode " + flag);
                verify(entry.hint.length > 0);
                var args = commands.startupArgs({sourceType: "usb", freqMhz: "451.5", decodeFlag: flag, trunking: false});
                flag.split(" ").forEach(function(token) { verify(args.indexOf(token) >= 0, "lost " + token); });
                if (!entry.setupOnly) verify(commands.decodeModeForFlag(flag) >= 0, "unmapped live mode " + flag);
            });
            compare(Util.decryptionProtocol("-fm"), "dpmr");
            compare(Util.decryptionProtocol("-fr"), "dmr");
            verify(Util.decryptionProtocol("-fp") !== "dpmr");
            var correct = sessionArgs.build({sourceType: "usb", freqMhz: "451.5", decodeFlag: "-fm", decryptionProtocol: "dpmr"});
            verify(correct.ok);
            var wrong = sessionArgs.build({sourceType: "usb", freqMhz: "451.5", decodeFlag: "-fm", decryptionProtocol: "dmr"});
            verify(!wrong.ok);
        }
        function test_ppm_manual_validation_and_refusal() {
            verify(radio.applyManualPpm("-27")); compare(prefs.ppm, -27); compare(prefs.autoPpm, false);
            verify(!radio.applyManualPpm("201")); verify(!radio.applyManualPpm("1.5")); verify(!radio.applyManualPpm(""));
            compare(prefs.ppm, -27);
            commands.acceptTune=false; verify(!radio.applyManualPpm("33")); compare(prefs.ppm, -27);
            commands.acceptTune=true; verify(radio.changeAutoPpm(true)); compare(prefs.autoPpm, true);
            verify(radio.changeAutoPpm(false)); compare(prefs.autoPpm, false);
        }
        function test_main_shell_compiles() {
            compare(commands.shellCompileError(), "");
        }
        function test_fine_preview_then_one_retune() {
            var start = screen.tunedHz;
            screen.beginDrag();
            screen.updateDrag(-30, 360);
            compare(screen.readoutHz, start + 25000);
            compare(commands.tuneCount, 0);
            screen.endDrag(false);
            compare(commands.tuneCount, 1);
            compare(commands.lastTune, start + 25000);
            verify(screen.swipePending);
        }
        function test_actual_pointer_swipe() {
            var area = findChild(screen, "spectrumTapArea");
            verify(area !== null);
            var x = area.width * 0.6, y = area.height * 0.6;
            mousePress(area, x, y);
            mouseMove(area, x - 25, y, 30);
            mouseMove(area, x - 55, y, 30);
            compare(commands.tuneCount, 0);
            verify(screen.swipeActive);
            verify(screen.readoutHz > screen.tunedHz);
            mouseRelease(area, x - 55, y);
            tryCompare(commands, "tuneCount", 1);
            verify(commands.lastTune > screen.tunedHz);
        }
        function test_cancel_and_controller_takeover_do_not_retune() {
            screen.beginDrag(); screen.updateDrag(40, 360); screen.endDrag(true);
            compare(commands.tuneCount, 0);
            screen.beginDrag(); screen.updateDrag(-50, 360);
            commands.metric("tunerControlled", true);
            screen.endDrag(false);
            compare(commands.tuneCount, 0);
            verify(!screen.swipeActive);
            screen.exploring = false;
            verify(!screen.tuneTo(155000000));
        }
        function test_pan_stays_view_only_even_at_edge() {
            screen.fineSwipe = false;
            spectrum.zoom = 4;
            screen.beginDrag(); screen.updateDrag(-500, 360); screen.endDrag(false);
            compare(commands.tuneCount, 0);
            verify(spectrum.viewOffsetHz > 0);
        }
        function test_pinch_zooms_without_retuning() {
            var area = findChild(screen, "spectrumTapArea");
            var y = area.height * 0.5;
            var touch = touchEvent(area);
            touch.press(0, area, 130, y).press(1, area, 220, y).commit();
            wait(30);
            touch.move(0, area, 100, y).move(1, area, 250, y).commit();
            wait(30);
            touch.move(0, area, 70, y).move(1, area, 280, y).commit();
            wait(30);
            touch.move(0, area, 50, y).move(1, area, 300, y).commit();
            wait(30);
            touch.release(0, area, 70, y).release(1, area, 280, y).commit();
            wait(50);
            verify(spectrum.zoom > 1);
            compare(commands.tuneCount, 0);
        }
        function test_rejected_tune_has_no_false_confirmation() {
            commands.acceptTune = false;
            screen.beginDrag(); screen.updateDrag(-30, 360); screen.endDrag(false);
            verify(!screen.swipePending);
            compare(screen.readoutHz, screen.tunedHz);
            verify(screen.hint.length > 0);
            verify(!screen.tuneTo(4294967296));
            verify(!screen.tuneTo(NaN));
            compare(commands.tuneCount, 1);
        }
        function test_steps_and_peak_snap() {
            findChild(screen, "spectrumFineStep").activate();
            compare(screen.tuningStepHz, 25000);
            findChild(screen, "spectrumFineUp").activate();
            compare(commands.lastTune, screen.tunedHz + 25000);
            commands.reset();
            var area = findChild(screen, "spectrumTapArea");
            // Canned frame's peak: bin 700, center 851 MHz, span 1.536 MHz.
            var peak = 851282000;
            var x = (peak - 18000 - spectrum.viewLowHz) / spectrum.viewSpanHz * area.width;
            mouseClick(area, x, area.height * 0.75);
            tryCompare(commands, "tuneCount", 1);
            verify(Math.abs(commands.lastTune - peak) <= 2000);
        }
        function test_compact_layout_and_preview() {
            commands.metric("decodeMode", commands.decodeModeForFlag("-fA"));
            var area = findChild(screen, "spectrumTapArea");
            verify(area.height > 200);
            var right = findChild(screen, "spectrumSwipeMode");
            verify(right.mapToItem(root, right.width, 0).x <= root.width);
            wait(350);
            if (previewDirectory.length) grabImage(root).save(previewDirectory + "/preview-fine-spectrum.png");
        }
    }
}
