// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Window
import QtQuick.Dialogs
Item {
    id: screen
    property int page: 0
    property bool showBack: true
    property string message: ""
    property var usb: []
    property string device: ""
    readonly property var state: receiverExpansion.status
    signal closed
    onVisibleChanged: if(visible) usb=receiverExpansion.devices
    component Label: Text { width: parent.width; wrapMode: Text.Wrap; textFormat: Text.PlainText; font.family: Theme.sans; font.pixelSize: Theme.fontSize(14); color: Theme.textSecondary }
    component Heading: Label { font.pixelSize: Theme.fontSize(19); color: Theme.textPrimary; font.bold: true }
    component Action: OutlineButton { width: parent.width }
    component Card: Rectangle {
        default property alias contents: column.data
        width: parent.width; height: column.height+28; color: Theme.panel; border.color: Theme.panelBorder; radius: 14
        Column { id: column; x: 14; y: 14; width: parent.width-28; spacing: 10 }
    }
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Row {
        id: header; x: 14; y: 12; width: parent.width-28; spacing: 12; height: Math.max(52,labTitle.implicitHeight)
        OutlineButton { visible: screen.showBack; width: 72; text: qsTr("Back"); labelHorizontalPadding: 8; onClicked: screen.closed() }
        Text { id: labTitle; width: parent.width-(screen.showBack?84:0); wrapMode: Text.WordWrap; anchors.verticalCenter: parent.verticalCenter; text: qsTr("Receiver lab"); color: Theme.textPrimary; font.family: Theme.sans; font.pixelSize: Theme.fontSize(22); font.bold: true }
    }
    Grid {
        id: tabs; x: 14; anchors.top: header.bottom; width: parent.width-28; columns: width<500?2:3; spacing: 8
        Repeater {
            model: [qsTr("Receivers"),qsTr("I/Q lab"),qsTr("Nearby"),qsTr("Band survey"),qsTr("Signaling"),qsTr("Reception")]
            OutlineButton { required property int index; required property string modelData; objectName: "expansionTab"+index
                width: (tabs.width-(tabs.columns-1)*8)/tabs.columns; text: modelData; labelHorizontalPadding: 8
                textColor: screen.page===index?Theme.cyan:Theme.textSecondary; onClicked: { screen.page=index; scroll.contentY=0; screen.message=""; } }
        }
    }
    PlexFlickable {
        id: scroll; x: 14; width: parent.width-28; anchors.top: tabs.bottom; anchors.topMargin: 12; anchors.bottom: parent.bottom
        anchors.bottomMargin: Math.max(0,screen.height-Theme.keyboardTop(screen)); clip: true; contentHeight: body.height+24
        Column {
            id: body; width: scroll.width; spacing: 12
            Label { text: screen.message; color: Theme.cyan; visible: text.length>0 }
            Label { visible: !!screen.state.thermalPaused; text: qsTr("Extra processing stopped because the phone is hot. Restart it after cooling.") }
            Label { visible: decoderHost.desktopBuild && (screen.page===0 || screen.page===1); text: qsTr("Extra receiver workers and automated I/Q lab runs are Android-only in this preview. Windows still supports single-receiver listening, file replay, range scanning, signal capture and the experimental equalizer.") }
            Column { visible: screen.page===0 && !decoderHost.desktopBuild; width: parent.width; spacing: 12
                Card {
                    Heading { text: qsTr("Four-channel DMR reception") }
                    Label { text: qsTr("Experimental: receive four nearby DMR frequencies at once with one RTL-SDR. The school frequencies are filled in below. Uses more battery; phone testing is still needed.") }
                    Label { text: qsTr("Four frequencies · MHz") }
                    Grid { width: parent.width; columns: 2; spacing: 8
                        Repeater { id: siteFrequencies; model: ["451.100", "451.850", "451.950", "452.125"]
                            PlexInput { required property int index; required property string modelData
                                width: (parent.width-8)/2; label: qsTr("Channel %1").arg(index+1); text: modelData
                                inputMethodHints: Qt.ImhFormattedNumbersOnly; enabled: !screen.state.siteCapture }
                        }
                    }
                    Action { objectName: "siteCaptureToggle"; text: screen.state.siteCapture?qsTr("Return to normal reception"):qsTr("Start four-channel mode"); onClicked: {
                        if(screen.state.siteCapture) receiverExpansion.stopSiteCapture();
                        else { var values=[]; for(var i=0;i<4;++i) values.push(siteFrequencies.itemAt(i).text);
                            screen.message=receiverExpansion.startSiteCapture(values.join(",")) || qsTr("Starting four-channel reception…"); }
                    } }
                    Label { text: screen.state.siteError || ""; visible: text.length>0 }
                    Label { visible: !!screen.state.siteCapture; text: qsTr("One receiver plays at a time. Automatic audio follows produced voice and keeps the current call. Receiver cards show activity; the main monitor remains the capture source.") }
                    Action { visible: !!screen.state.siteCapture; text: screen.state.siteAuto?qsTr("Automatic audio is on"):qsTr("Resume automatic audio"); onClicked: receiverExpansion.autoSiteAudio() }
                }
                Card {
                    visible: !screen.state.siteCapture
                    Heading { text: qsTr("Hear more than one channel") }
                    Label { text: qsTr("Keep the main RTL-SDR on a fixed channel at 48 kHz bandwidth. Add up to two nearby channels from the same capture. Select one speaker output; recordings can continue on each receiver.") }
                    PlexInput { id: frequency; width: parent.width; label: qsTr("Frequency · MHz"); text: "155.000000"; inputMethodHints: Qt.ImhFormattedNumbersOnly }
                    PlexComboBox { id: mode; width: parent.width; model: [qsTr("Analog NFM"),"P25 Phase 1","P25 Phase 2","DMR","NXDN48","NXDN96",qsTr("Auto digital")]
                        property var flags: ["-fA","-f1","-f2","-fs","-fi","-fn","-fa"] }
                    Action { objectName: "startExtraOne"; text: qsTr("Start receiver 2"); onClicked: screen.message=receiverExpansion.startChannel(0,Number(frequency.text),mode.flags[mode.currentIndex],"") || qsTr("Starting receiver…") }
                    Action { text: qsTr("Start receiver 3"); onClicked: screen.message=receiverExpansion.startChannel(1,Number(frequency.text),mode.flags[mode.currentIndex],"") || qsTr("Starting receiver…") }
                    Action { text: qsTr("Hear main receiver"); onClicked: receiverExpansion.listen(-1) }
                }
                Repeater { model: receiverExpansion.lanes
                    Card { required property var modelData; required property int index
                        Heading { text: qsTr("Receiver %1 · %2").arg(index+2).arg(appLanguage.text(modelData.state || "idle")) }
                        Label { visible: !!screen.state.siteCapture; text: (Number(modelData.plannedFrequency||0)/1e6).toFixed(6)+" MHz"+(modelData.talkgroup?" · TG "+modelData.talkgroup:"") }
                        Label { text: qsTr("Decoded audio: %1 frames · Android output: %2 frames").arg(modelData.pcmFrames||0).arg(modelData.outputFrames||0) }
                        Label { text: (modelData.error?appLanguage.text(modelData.error):"") || qsTr("Received %1 MB · dropped %2 bytes").arg(Number(modelData.bytes||0)/1048576).arg(modelData.dropped||0) }
                        Label { visible: Number(modelData.outputRate||0)>0; text: qsTr("Shared capture: %1 kS/s → receiver: %2 kS/s").arg(Number(modelData.captureRate||0)/1000).arg(Number(modelData.outputRate||0)/1000) }
                        Action { text: screen.state.siteCapture?qsTr("Hold this receiver"):qsTr("Hear this receiver"); enabled: modelData.state==="running"; onClicked: receiverExpansion.listen(index) }
                        Action { text: qsTr("Stop this receiver"); onClicked: receiverExpansion.stopChannel(index) }
                    }
                }
                Card {
                    Heading { text: qsTr("Two-dongle P25 trunking") }
                    Label { text: qsTr("The main receiver stays on the control channel. A second USB RTL-SDR follows admitted P25 Phase 1/2 voice grants. A powered USB hub is usually needed. Select a different receiver below.") }
                    Action { text: qsTr("Refresh USB receivers"); onClicked: screen.usb=receiverExpansion.devices }
                    Repeater { model: screen.usb
                        Column { required property var modelData; width: parent.width; spacing: 6
                            Label { text: modelData.name+" · "+modelData.id+(modelData.main?qsTr(" · main receiver"):"") }
                            Action { text: modelData.permitted?qsTr("Select voice receiver"):qsTr("Grant USB access"); enabled: !modelData.main
                                onClicked: { screen.device=modelData.id; if(!modelData.permitted) receiverExpansion.requestDevice(modelData.id); screen.message=qsTr("Selected: %1").arg(modelData.id); } }
                        }
                    }
                    Action { text: screen.state.dual?qsTr("Stop two-dongle mode"):qsTr("Arm voice receiver"); onClicked: { if(screen.state.dual) receiverExpansion.stopDual(); else screen.message=receiverExpansion.startDual(screen.device) || qsTr("Voice receiver armed"); } }
                    Label { visible: !!screen.state.dual; text: qsTr("Voice %1 MHz · talkgroup %2").arg(Number(screen.state.voiceFrequency||0)/1e6).arg(screen.state.voiceTarget||0) }
                    Label { visible: !!screen.state.dual; text: screen.state.voicePending?qsTr("Applying voice grant…"):qsTr("Last tune acknowledgment: %1 ms").arg(screen.state.tuneLatencyMs||0) }
                    Label { visible: !!screen.state.dual; text: qsTr("Voice grants retune the running decoder. Acknowledgment measures command handling, not time to intelligible audio.") }
                }
                Card {
                    Heading { text: qsTr("Background reception") }
                    Label { text: qsTr("Capture stops after 20 seconds in the Android service and resumes normal reception. USB recovery waits up to one minute for the same receiver and requires existing USB permission and a serial number.") }
                    Action { text: screen.state.recoveryEnabled?qsTr("Disable USB recovery"):qsTr("Enable USB recovery"); onClicked: receiverExpansion.setRecovery(!screen.state.recoveryEnabled) }
                    Label { text: screen.state.recovery || ""; visible: text.length>0 }
                }
            }
            Column { visible: screen.page===1; width: parent.width; spacing: 12
                Card {
                    visible: !decoderHost.desktopBuild
                    Heading { text: qsTr("Test the real receive chain") }
                    Label { text: qsTr("Replay known I/Q through filtering, demodulation, error correction and protocol parsing. Results name the expected decoded evidence. Passing these fixtures does not replace testing with your antenna and phone.") }
                    Action { objectName: "runIqLab"; text: screen.state.labRunning?qsTr("Stop tests"):qsTr("Run bundled I/Q tests"); onClicked: { if(screen.state.labRunning) receiverExpansion.stopTrials(); else screen.message=receiverExpansion.runLab(); } }
                    Label { text: screen.state.trial || ""; visible: !!screen.state.labRunning }
                    Action { text: qsTr("Export test report"); onClicked: reportFile.open() }
                }
                Card {
                    Heading { text: qsTr("Experimental simulcast equalizer") }
                    Label { text: qsTr("Adaptive processing before P25 CQPSK timing recovery. It can improve or worsen a signal. Compare the same capture with bypass and enabled; leave it off if decoded evidence declines.") }
                    Action { text: screen.state.equalizer?qsTr("Bypass equalizer"):qsTr("Enable experimental equalizer"); onClicked: receiverExpansion.setEqualizer(!screen.state.equalizer) }
                    Label { visible: !!screen.state.equalizer; text: qsTr("Modulus error: %1 · this is not a decoded-frame score").arg(Number(screen.state.equalizerError||0).toFixed(4)) }
                }
                Card {
                    visible: !decoderHost.desktopBuild
                    Heading { text: qsTr("Reprocess a saved signal") }
                    PlexComboBox { id: replayMode; width: parent.width; model: ["P25 Phase 1","P25 Phase 2","DMR","NXDN48","NXDN96",qsTr("Analog NFM")]; property var flags: ["-f1","-f2","-fs","-fi","-fn","-fA"] }
                    Label { text: qsTr("P25 compares C4FM and CQPSK. Results retain decoded evidence so you can compare actual output.") }
                    Repeater { model: receiverAssistant.captures
                        Action { required property var modelData; text: modelData.name; onClicked: screen.message=receiverExpansion.reprocess(modelData.metadata,replayMode.flags[replayMode.currentIndex]) }
                    }
                }
                Repeater { model: receiverExpansion.reports.slice(0,20)
                    Card { required property var modelData
                        Heading { text: modelData.name+" · "+appLanguage.text(modelData.result) }
                        Label { text: qsTr("P25 FEC accepted %1 · rejected %2 · PCM %3 bytes").arg(modelData.fecAccepted||0).arg(modelData.fecRejected||0).arg(modelData.pcmBytes||0) }
                        Label { text: qsTr("PCM size confirms produced audio data, not speech intelligibility.") }
                        Label { text: modelData.at+(modelData.expect?"\n"+qsTr("Expected: %1").arg(modelData.expect):"") }
                        Label { text: qsTr("Completed: %1 · %2 seconds").arg(modelData.completed?qsTr("yes"):qsTr("no")).arg((Number(modelData.elapsedMs||0)/1000).toFixed(1)) }
                    }
                }
            }
            Column { visible: screen.page===2; width: parent.width; spacing: 12
                Card {
                    Heading { text: qsTr("Nearby saved channels") }
                    Label { text: screen.state.location || "" }
                    Action { text: qsTr("Center on Indio"); onClicked: receiverExpansion.locate(false) }
                    Action { visible: decoderHost.locationSupported; text: qsTr("Use current location"); onClicked: receiverExpansion.locate(true) }
                    PlexInput { id: radius; width: parent.width; label: qsTr("Radius · miles"); text: "50"; inputMethodHints: Qt.ImhFormattedNumbersOnly; onEditingFinished: receiverExpansion.setRadius(Number(text)) }
                    Action { text: screen.state.geoScanning?qsTr("Stop location selection"):qsTr("Select nearby sites automatically"); onClicked: receiverExpansion.setGeoScan(!screen.state.geoScanning) }
                    Label { text: qsTr("Cycles eligible saved sites every 30 seconds while the app is open. Uses saved coordinates and location accuracy. Calls and holds prevent switching. Missing coordinates remain in your saved systems; they are not assigned a guessed location.") }
                }
                Repeater { model: receiverExpansion.nearby
                    Card { required property var modelData
                        Heading { text: modelData.name }
                        Label { text: qsTr("%1 miles").arg(Number(modelData.distanceMi).toFixed(1))+(modelData.uncertain?qsTr(" · location boundary uncertain"):"") }
                        Action { text: qsTr("Listen"); onClicked: receiverExpansion.selectSite(modelData.uid) }
                    }
                }
                Label { text: qsTr("No saved channels with coordinates inside this radius."); visible: receiverExpansion.nearby.length===0 }
            }
            Column { visible: screen.page===3; width: parent.width; spacing: 12
                Card {
                    Heading { text: qsTr("Measure a band") }
                    Label { text: screen.state.surveyError || ""; visible: text.length>0 }
                    Label { text: qsTr("Survey pauses normal listening. Occupancy is the fraction of sampled seconds with at least 6 dB SNR. Brief transmissions between visits can be missed. Protocol labels require validated frame evidence.") }
                    PlexInput { id: first; width: parent.width; label: qsTr("Start · MHz"); text: "154.000"; inputMethodHints: Qt.ImhFormattedNumbersOnly }
                    PlexInput { id: last; width: parent.width; label: qsTr("End · MHz"); text: "155.000"; inputMethodHints: Qt.ImhFormattedNumbersOnly }
                    PlexInput { id: step; width: parent.width; label: qsTr("Step · kHz"); text: "12.5"; inputMethodHints: Qt.ImhFormattedNumbersOnly }
                    PlexInput { id: dwell; width: parent.width; label: qsTr("Dwell · seconds"); text: "3"; inputMethodHints: Qt.ImhDigitsOnly }
                    Action { objectName: "surveyToggle"; text: screen.state.surveying?qsTr("Stop and restore frequency"):qsTr("Start survey"); onClicked: { if(screen.state.surveying) receiverExpansion.stopSurvey(); else screen.message=receiverExpansion.startSurvey(Number(first.text),Number(last.text),Number(step.text),Number(dwell.text)); } }
                }
                Repeater { model: receiverExpansion.survey
                    Card { required property var modelData; required property int index
                        Heading { text: (modelData.frequency/1e6).toFixed(6)+" MHz · "+Number(modelData.occupancy).toFixed(0)+"%" }
                        Label { text: qsTr("Samples %1 · validated frames %2 · last activity %3").arg(modelData.samples).arg(modelData.ok).arg(modelData.lastActive || "—") }
                        Label { text: modelData.protocol || qsTr("Protocol unconfirmed") }
                        Action { text: qsTr("Listen"); onClicked: receiverExpansion.tuneSurvey(index) }
                        Action { text: qsTr("Save channel"); onClicked: screen.message=receiverExpansion.saveSurvey(index)?qsTr("Channel saved"):qsTr("Could not save channel") }
                    }
                }
            }
            Column { visible: screen.page===4; width: parent.width; spacing: 12
                Card {
                    Heading { text: qsTr("Analog signaling") }
                    Label { text: qsTr("MDC-1200 and FleetSync require a valid CRC before publishing IDs. DTMF and the configured two-tone sequence are decoded from received NFM audio.") }
                    Label { text: screen.state.signaling || qsTr("No signaling decoded yet") }
                    PlexInput { id: toneA; width: parent.width; label: qsTr("First tone · Hz"); text: "600"; inputMethodHints: Qt.ImhFormattedNumbersOnly }
                    PlexInput { id: toneB; width: parent.width; label: qsTr("Second tone · Hz"); text: "1000"; inputMethodHints: Qt.ImhFormattedNumbersOnly }
                    PlexInput { id: toneAMs; width: parent.width; label: qsTr("First tone minimum · ms"); text: "1000"; inputMethodHints: Qt.ImhDigitsOnly }
                    PlexInput { id: toneBMs; width: parent.width; label: qsTr("Second tone minimum · ms"); text: "1000"; inputMethodHints: Qt.ImhDigitsOnly }
                    Action { text: qsTr("Apply two-tone sequence"); onClicked: screen.message=receiverExpansion.setTwoTone(Number(toneA.text),Number(toneB.text),Number(toneAMs.text),Number(toneBMs.text))?qsTr("Sequence applied"):qsTr("Use distinct tones from 300–3000 Hz and durations from 100–5000 ms.") }
                }
                Repeater { model: screen.state.signals || []; Label { required property var modelData; text: modelData.when+" · "+modelData.text } }
            }
            Column { visible: screen.page===5; width: parent.width; spacing: 12
                Card {
                    Heading { text: qsTr("NXDN scrambler search · experimental") }
                    Label { text: qsTr("Finds a candidate for the 15-bit voice scrambler from repeated voice patterns. Applies it to the current call after two separate matches. Supplied keys take priority. Main receiver only; NXDN48/96 superframes. Does not recover DES or AES keys.") }
                    Action { objectName: "nxdnSearchToggle"; text: screen.state.nxdnSearch?qsTr("Stop NXDN search"):qsTr("Start NXDN search"); onClicked: receiverExpansion.setNxdnSearch(!screen.state.nxdnSearch) }
                    Label { visible: !!screen.state.nxdnSearch; text: [qsTr("Waiting for a supported NXDN call"),qsTr("Searching voice patterns…"),qsTr("Candidate found; waiting for another match"),qsTr("Candidate %1 in use · verify that speech is clear").arg(screen.state.nxdnSearchKey),qsTr("Using your supplied key"),qsTr("Waiting for confirmed 15-bit scrambler signaling")][screen.state.nxdnSearchStatus||0] }
                    Label { visible: !!screen.state.nxdnSearch; text: qsTr("Voice frames checked: %1").arg(screen.state.nxdnSearchFrames||0) }
                    Label { text: qsTr("Pattern matches are not proof of the correct key. Short calls, noise or changing speech may produce no result. Candidates reset when the call changes and are never saved automatically. Phone and scrambled-radio testing are still required.") }
                    Action { visible: !!screen.state.nxdnSearch; text: qsTr("Discard candidate and search again"); onClicked: receiverExpansion.setNxdnSearch(true) }
                }
                Card {
                    Heading { text: qsTr("DMR reception evidence") }
                    Action { objectName: "rasReception"; text: screen.state.rasReception?qsTr("Disable DMR RAS reception"):qsTr("Enable DMR RAS reception"); onClicked: receiverExpansion.setRasReception(!screen.state.rasReception) }
                    Label { text: qsTr("Applies the RAS heuristic to the main DMR receiver. Other protocols keep their CRC checks. Use the I/Q lab to verify the known RAS fixture.") }
                    Label { text: qsTr("CRC checked: %1 · suspected RAS: %2 · rejected: %3").arg(screen.state.dmrChecked||0).arg(screen.state.dmrRas||0).arg(screen.state.dmrRejected||0) }
                    Label { text: qsTr("RAS is separate from voice encryption. Suspected RAS is a receive heuristic, not proof of a valid call. Counters describe the main receiver and reset with each session.") }
                }
                Card {
                    Heading { text: qsTr("Supplied-key status") }
                    Label { text: qsTr("P25 AES-128, AES-256, DES and ADP use matching supplied keys. A matching key ID does not prove that the key is correct. Unknown encryption remains encrypted.") }
                    Repeater { model: screen.state.decryption || []
                        Column { required property var modelData; width: parent.width; spacing: 6
                            Label { text: qsTr("Slot %1 · %2 · key ID %3").arg(modelData.slot||1).arg(modelData.algorithm||"—").arg(modelData.keyId||"—") }
                            Label { text: appLanguage.text(modelData.availability||modelData.status||"") }
                            Label { text: appLanguage.text(modelData.blockReason||""); visible: text.length>0 }
                        }
                    }
                }
                Card {
                    Heading { text: qsTr("Compare antenna and gain setups") }
                    Label { text: qsTr("Tune a fixed channel, name your antenna and gain setting, then measure for 30 seconds. Change one setting and repeat. Prefer repeated samples of an active control channel; changing traffic can affect the results.") }
                    PlexInput { id: setupLabel; width: parent.width; label: qsTr("Setup name"); text: qsTr("Antenna A · current gain") }
                    Action { objectName: "receptionSample"; text: screen.state.receptionRunning?qsTr("Cancel measurement"):qsTr("Measure for 30 seconds"); onClicked: { if(screen.state.receptionRunning) receiverExpansion.cancelReceptionSample(); else screen.message=receiverExpansion.startReceptionSample(setupLabel.text); } }
                    Label { visible: !!screen.state.receptionRunning; text: qsTr("Measuring: %1 / 30 seconds").arg(screen.state.receptionSeconds||0) }
                    Action { text: qsTr("Export test report"); onClicked: reportFile.open() }
                    Label { text: qsTr("Compare decoded control frames and SNR together. These measurements do not score speech quality or establish superiority over an SDS100.") }
                }
                Repeater { model: receiverExpansion.receptionReports
                    Card { required property var modelData
                        Heading { text: modelData.name }
                        Label { text: Number(modelData.frequency/1e6).toFixed(6)+" MHz · "+modelData.at }
                        Label { text: modelData.valid?qsTr("Control FEC accepted %1 · rejected %2").arg(modelData.fecAccepted).arg(modelData.fecRejected):qsTr("Invalid sample: reception stopped, frequency changed or counters reset.") }
                        Label { text: modelData.snrSamples?qsTr("Mean SNR %1 dB · %2 readings").arg(Number(modelData.meanSnrDb).toFixed(1)).arg(modelData.snrSamples):qsTr("No valid SNR readings") }
                    }
                }
            }
        }
    }
    Connections { target: screen.Window.window; function onActiveFocusItemChanged() { Qt.callLater(function(){Theme.revealFocus(scroll,body,screen.Window.window.activeFocusItem);}); } }
    FileDialog { id: reportFile; title: qsTr("Save test report"); fileMode: FileDialog.SaveFile; nameFilters: ["JSON (*.json)"]; onAccepted: screen.message=receiverExpansion.exportReports(selectedFile.toString()) || qsTr("Report saved") }
}
