// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Window
import QtQuick.Dialogs

Item {
    id: screen
    signal closed
    property int page: 0
    property bool advanced: false
    property bool expansionOpen: false
    property bool aiOpen: false
    property bool rangeOpen: false
    Loader {
        anchors.fill: parent; z: 20; active: screen.rangeOpen
        sourceComponent: Component { RangeScannerScreen { onClosed: screen.rangeOpen=false } }
    }
    function openScan() { expansionPage.page=2; expansionOpen=true; }
    property string message: ""
    property int captureIndex: -1
    readonly property var viewStatus: receiverAssistant.status
    readonly property bool live: !!viewStatus.live
    function revealInput() { if (screen.Window.window) Theme.revealFocus(scroll, body, screen.Window.window.activeFocusItem); }
    Connections { target: screen.Window.window; function onActiveFocusItemChanged() { Qt.callLater(screen.revealInput); } }
    function loadFilter() {
        frequency.text = Number(metrics.centerFreqHz / 1e6).toFixed(6);
        var rule = receiverAssistant.filter(Math.round(Number(frequency.text) * 1e6));
        ctcss.text = rule.ctcss > 0 ? String(rule.ctcss) : "";
        dcs.text = rule.dcs >= 0 ? ("000" + Number(rule.dcs).toString(8)).slice(-3) : "";
        polarity.currentIndex = rule.inverse ? 1 : 0;
        colorCode.text = rule.color >= 0 ? String(rule.color) : "";
        slot.currentIndex = rule.slot || 0;
        talkgroup.text = rule.talkgroup > 0 ? String(rule.talkgroup) : "";
    }
    function applyFilter() {
        if (dcs.text.length && !/^[0-7]{3}$/.test(dcs.text)) { message = qsTr("DCS uses three octal digits, for example 023."); return; }
        message = receiverAssistant.saveFilter(Math.round(Number(frequency.text) * 1e6), {
            ctcss: ctcss.text.length ? Number(ctcss.text) : 0,
            dcs: dcs.text.length ? parseInt(dcs.text, 8) : -1, inverse: polarity.currentIndex === 1,
            color: colorCode.text.length ? Number(colorCode.text) : -1,
            slot: slot.currentIndex, talkgroup: talkgroup.text.length ? Number(talkgroup.text) : 0
        }) || qsTr("Filter saved and active");
    }
    onVisibleChanged: if (visible) loadFilter()
    Keys.onEscapePressed: screen.closed()
    Keys.onBackPressed: screen.closed()
    component Label: Text {
        width: parent.width; wrapMode: Text.Wrap; textFormat: Text.PlainText
        font.family: Theme.sans; font.pixelSize: Theme.fontSize(14); color: Theme.textSecondary
    }
    component Heading: Label { color: Theme.textPrimary; font.pixelSize: Theme.fontSize(19); font.bold: true }
    component Action: OutlineButton { width: parent.width }
    component Card: Rectangle {
        default property alias contents: column.data
        width: parent.width; implicitHeight: column.height + 28
        height: implicitHeight; radius: 14; color: Theme.panel; border.color: Theme.panelBorder
        Column { id: column; x: 14; y: 14; width: parent.width - 28; spacing: 10 }
    }
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Row {
        id: header; x: 14; y: 12; width: parent.width - 28; spacing: 10
        IconButton { icon: "back"; onClicked: screen.closed() }
        Text { width: parent.width - 58; text: qsTr("Receiver tools"); wrapMode: Text.Wrap
            font.family: Theme.sans; font.pixelSize: Theme.fontSize(23); font.bold: true; color: Theme.textPrimary }
    }
    Grid {
        id: tabs; anchors.top: header.bottom; anchors.topMargin: 12; x: 14; width: parent.width - 28; spacing: 6
        columns: width < 330 || Theme.fontSize(15) > 17 ? 2 : 4
        Repeater {
            model: [qsTr("Quality"), qsTr("Channels"), qsTr("Clips"), qsTr("More")]
            delegate: OutlineButton {
                required property int index; required property string modelData
                objectName: "receiverTab" + index
                labelHorizontalPadding: 12
                width: (tabs.width - (tabs.columns - 1) * tabs.spacing) / tabs.columns
                text: modelData; textColor: screen.page === index ? Theme.cyan : Theme.textSecondary
                onClicked: { screen.page = index; scroll.contentY = 0; screen.message = ""; }
            }
        }
    }
    PlexFlickable {
        id: scroll
        objectName: "assistantScroll"
        anchors.top: tabs.bottom; anchors.topMargin: 12; anchors.bottom: parent.bottom
        anchors.bottomMargin: Math.max(0, screen.height - Theme.keyboardTop(screen))
        onHeightChanged: Qt.callLater(screen.revealInput)
        x: 14; width: parent.width - 28; clip: true; contentHeight: body.height + 24
        Column {
            id: body; width: scroll.width; spacing: 12
            Action { objectName: "openReceiverLab"; text: qsTr("Receivers, I/Q lab and scanning"); onClicked: screen.expansionOpen=true }
            Action { objectName: "openAiReceiver"; visible: !decoderHost.desktopBuild; text: qsTr("AI receiver · OpenAI / DeepSeek"); onClicked: screen.aiOpen=true }
            Label { visible: decoderHost.desktopBuild; text: qsTr("Windows preview: core reception and scanning are available. AI providers, extra receiver workers, GPS and Android background services are not included in this desktop preview.") }
            Action { objectName: "openRangeScanner"; text: qsTr("Frequency range scanner"); onClicked: screen.rangeOpen=true }
            Label { text: screen.message; visible: text.length > 0; color: Theme.cyan }
            Column {
                visible: screen.page === 0; width: parent.width; spacing: 12
                Card {
                    Heading { text: qsTr("Decode quality") }
                    Label { text: screen.live ? qsTr("Last 30 seconds on this frequency") : qsTr("Start listening to see live measurements") }
                    Label { text: qsTr("Valid control frames: %1 · failed: %2").arg(screen.viewStatus.validFrames || 0).arg(screen.viewStatus.failedFrames || 0) }
                    Label { text: screen.viewStatus.framePercent >= 0 ? qsTr("Frame success: %1%").arg(Number(screen.viewStatus.framePercent).toFixed(1)) : qsTr("Frame success: not enough frames") }
                    Label { text: qsTr("Sync losses: %1 · audio gap events: %2").arg(screen.viewStatus.syncLosses || 0).arg(screen.viewStatus.audioGaps || 0) }
                    Label { text: screen.viewStatus.clipValid ? qsTr("Input clipping: %1%").arg(Number(screen.viewStatus.clip).toFixed(3)) : qsTr("Input clipping: unavailable") }
                    Label { text: screen.viewStatus.snrValid ? qsTr("SNR: %1 dB").arg(Number(screen.viewStatus.snr).toFixed(1)) : qsTr("SNR: unavailable") }
                    Label { text: qsTr("Control-frame counts apply where the decoder publishes them. Audio gaps count player underruns, not radio silence.") }
                }
                Card {
                    visible: !!decoderHost.localDeviceBrokered
                    Heading { text: qsTr("USB receiver check") }
                    Label { text: qsTr("RTL-SDR Blog V3 / V4, compatible RTL2832U, Airspy R2 / Mini and HackRF One (experimental RX).") }
                    Label { text: qsTr("Connected USB devices: %1").arg(((receiverTools.health.usb || {}).devices || []).length) }
                    Repeater {
                        model: (receiverTools.health.usb || {}).devices || []
                        Label { required property var modelData
                            text: modelData.name + " · " + modelData.id + "\n" + (modelData.supported ? qsTr("Supported driver") : qsTr("No driver in this app")) + " · " + (modelData.permission ? qsTr("Permission granted") : qsTr("Permission needed"))
                        }
                    }
                    Label { visible: !((receiverTools.health.usb || {}).devices || []).length
                        text: qsTr("No USB device is visible to Android. Check the OTG adapter, data cable and receiver power, then reconnect.") }
                    Label { text: decoderHost.localDeviceStatus || "" }
                    Action { text: qsTr("Request USB access again"); enabled: !decoderHost.running; onClicked: decoderHost.requestLocalDeviceAccess() }
                    Label { text: qsTr("PPM adjusts frequency error after connection; it cannot fix a missing USB device. HackRF currently supports reception up to 2 GHz; hardware testing is pending.") }
                }
                Card {
                    Heading { text: qsTr("Improve reception") }
                    Action { objectName: "autoGainButton"; text: receiverAssistant.autoGain ? qsTr("Stop automatic gain") : qsTr("Try automatic gain")
                        onClicked: receiverAssistant.autoGain = !receiverAssistant.autoGain }
                    Label { text: { var lang = appLanguage.language; return appLanguage.text(screen.viewStatus.gainText || ""); } }
                    Label { text: qsTr("One small gain trial on a steady RTL channel. Calls pause the trial; weak evidence or worse decoding restores the original. Trials are spaced two minutes apart.") }
                    Action { text: receiverAssistant.roaming ? qsTr("Turn site selection off") : qsTr("Choose sites automatically")
                        onClicked: receiverAssistant.roaming = !receiverAssistant.roaming }
                    Label { text: { var lang = appLanguage.language; return appLanguage.text(screen.viewStatus.siteText || ""); } }
                    Label { text: qsTr("Uses saved sites in the same RadioReference system. A trial briefly restarts reception. Calls and holds take priority; unsuccessful trials return to the previous site.") }
                }
                Card {
                    Heading { text: qsTr("Audio help") }
                    Label { text: qsTr("I/Q input: %1 · digital sync: %2 · voice call: %3 · audio data: %4")
                        .arg(receiverTools.health.iqFresh?qsTr("arriving"):qsTr("unconfirmed"))
                        .arg(screen.viewStatus.protocolFresh?qsTr("yes"):qsTr("no"))
                        .arg(screen.viewStatus.voiceActive?qsTr("yes"):qsTr("no"))
                        .arg(screen.viewStatus.pcmFresh?qsTr("arriving"):qsTr("waiting")) }
                    Label { visible: !!receiverTools.health.iqObserved; text: qsTr("Capture %1 MHz · %2 kS/s · last samples %3 ms ago")
                        .arg((Number(receiverTools.health.captureHz||0)/1e6).toFixed(6)).arg(Number(receiverTools.health.captureRate||0)/1000).arg(receiverTools.health.iqAgeMs) }
                    Label { text: { var lang = appLanguage.language; return appLanguage.text(screen.viewStatus.audioText || ""); } }
                    Label { text: qsTr("Output: %1").arg(decoderHost.audioRoute || qsTr("System default")) }
                    Action { objectName: "speakerRecovery"; text: qsTr("Use phone speaker"); onClicked: { decoderHost.selectAudioOutput("speaker"); receiverTools.stopPlayback(); } }
                    Action { text: qsTr("Use system audio output"); onClicked: { decoderHost.selectAudioOutput("default"); receiverTools.stopPlayback(); } }
                    Action { text: qsTr("Unmute"); visible: !!metrics.audioMuted; onClicked: commands.toggleMute() }
                    Action { text: qsTr("Retry disconnected source"); visible: !screen.live; onClicked: receiverAssistant.retryRequested() }
                }
            }
            Column {
                visible: screen.page === 1; width: parent.width; spacing: 12
                Card {
                    Heading { text: qsTr("Channel filters") }
                    Label { text: qsTr("Blank means any. Filters apply to audio on this exact frequency. Tone detection needs a few seconds; use at least 3 seconds of scan dwell. Raw recordings keep the original signal.") }
                    Label { text: qsTr("Frequency (MHz)") }
                    PlexInput { id: frequency; objectName: "filterFrequency"; width: parent.width; inputMethodHints: Qt.ImhFormattedNumbersOnly }
                    Action { text: qsTr("Load current channel"); onClicked: screen.loadFilter() }
                    Label { text: qsTr("CTCSS tone (Hz) — narrow FM") }
                    PlexInput { id: ctcss; width: parent.width; placeholderText: qsTr("Any tone"); inputMethodHints: Qt.ImhFormattedNumbersOnly }
                    Label { text: qsTr("DCS code — use instead of CTCSS") }
                    PlexInput { id: dcs; width: parent.width; placeholderText: qsTr("Any code, or 023"); maximumLength: 3 }
                    PlexComboBox { id: polarity; width: parent.width; model: [qsTr("Normal DCS"), qsTr("Inverted DCS")] }
                    Label { text: qsTr("DMR color code (0–15)") }
                    PlexInput { id: colorCode; width: parent.width; placeholderText: qsTr("Any color code"); maximumLength: 2; inputMethodHints: Qt.ImhDigitsOnly }
                    PlexComboBox { id: slot; width: parent.width; model: [qsTr("Both time slots"), qsTr("Time slot 1"), qsTr("Time slot 2")] }
                    Label { text: qsTr("Talkgroup ID") }
                    PlexInput { id: talkgroup; width: parent.width; placeholderText: qsTr("Any talkgroup"); inputMethodHints: Qt.ImhDigitsOnly }
                    Action { objectName: "applyReceiverFilter"; text: qsTr("Apply filter"); onClicked: screen.applyFilter() }
                    Action { text: qsTr("Clear this channel's filters"); onClicked: { receiverAssistant.clearFilter(Math.round(Number(frequency.text) * 1e6)); screen.loadFilter(); screen.message = qsTr("Filters cleared"); } }
                }
                Card {
                    Heading { text: qsTr("Discovery notebook") }
                    Action { text: receiverAssistant.notebook ? qsTr("Pause discoveries") : qsTr("Remember discoveries"); onClicked: receiverAssistant.notebook = !receiverAssistant.notebook }
                    Label { text: qsTr("Stores up to 500 observations on this phone. Energy alone is unconfirmed. Three consecutive observations are required; scanning too quickly may miss entries.") }
                    Action { text: qsTr("Export notebook"); onClicked: notebookFile.open() }
                    Action { text: qsTr("Clear notebook"); onClicked: clearNotebook.visible = true }
                    Label { text: qsTr("The latest 30 entries appear below. Export includes the full notebook.") }
                }
                Repeater {
                    model: screen.page === 1 ? receiverAssistant.discoveries.slice(0, 30) : []
                    delegate: Card {
                        required property var modelData; required property int index
                        Heading { text: (modelData.frequency / 1e6).toFixed(5) + " MHz" }
                        Label { text: (modelData.confirmed ? modelData.protocol : qsTr("Unconfirmed energy")) + " · " + appLanguage.text(modelData.tone || "") }
                        Label { text: qsTr("First: %1\nLast: %2").arg(new Date(modelData.first * 1000).toLocaleString(Qt.locale(appLanguage.language))).arg(new Date(modelData.last * 1000).toLocaleString(Qt.locale(appLanguage.language))) }
                        Label { visible: !!modelData.talkgroup; text: qsTr("Talkgroup: %1 · radio: %2").arg(modelData.talkgroup || "—").arg(modelData.radio || "—") }
                        Action { text: qsTr("Save listening preset"); onClicked: screen.message = receiverAssistant.saveDiscovery(index) ? qsTr("Listening preset saved") : qsTr("Could not save preset") }
                    }
                }
            }
            Column {
                visible: screen.page === 2; width: parent.width; spacing: 12
                Card {
                    Heading { text: qsTr("Replay received audio") }
                    Label { text: qsTr("%1 seconds buffered. Reception, scanning and recording continue during playback.").arg(receiverTools.replaySeconds.toFixed(1)) }
                    Action { objectName: "liveReplayButton"; text: qsTr("Replay last 30 seconds"); enabled: receiverTools.replaySeconds > 0
                        onClicked: screen.message = receiverTools.playReplay(30) || qsTr("Replay requested") }
                    Action { text: qsTr("Replay last 60 seconds"); enabled: receiverTools.replaySeconds > 0
                        onClicked: screen.message = receiverTools.playReplay(60) || qsTr("Replay requested") }
                    Action { text: qsTr("Return to live"); onClicked: receiverTools.stopPlayback() }
                    Action { text: qsTr("Save audio clip"); enabled: receiverTools.replaySeconds > 0; onClicked: audioFile.open() }
                    Label { text: qsTr("Silent gaps are omitted. Playback returns to live automatically when the clip ends.") }
                }
                Card {
                    Heading { text: qsTr("Capture raw signal") }
                    Label { text: qsTr("Capture this channel for up to 20 seconds or 64 MB. The receiver briefly restarts before and after capture. Start from a single channel, not a scan list. Saved files include I/Q data and tuning metadata.") }
                    Action { objectName: "rawCaptureButton"; text: qsTr("Capture current signal"); enabled: !!screen.viewStatus.canCapture; onClicked: receiverAssistant.captureRequested() }
                    Action { text: qsTr("Finish capture and resume"); enabled: !!screen.viewStatus.capturing; onClicked: receiverAssistant.finishCaptureRequested() }
                    Label { text: screen.viewStatus.captureText || "" }
                }
                Repeater {
                    model: receiverAssistant.captures
                    delegate: Card {
                        required property var modelData; required property int index
                        Label { text: modelData.name + " · " + (modelData.bytes / 1048576).toFixed(1) + " MB" }
                        Action { text: qsTr("Export signal and metadata"); enabled: !screen.live
                            onClicked: { screen.captureIndex = index; captureFile.open(); } }
                    }
                }
            }
            Column {
                visible: screen.page === 3; width: parent.width; spacing: 12
                Card {
                    Heading { text: "Language / Idioma" }
                    PlexComboBox { objectName: "toolsLanguageSelector"; width: parent.width; model: ["English", "Español"]
                        currentIndex: appLanguage.language === "es" ? 1 : 0
                        onActivated: appLanguage.language = currentIndex === 1 ? "es" : "en" }
                    Label { text: qsTr("Change the language at any time. Protocol names and database labels stay as supplied.") }
                }
                Card {
                    Heading { text: qsTr("Advanced receiver tools") }
                    Label { text: qsTr("Receiver profiles, manual gain comparison, local site map, activity alerts and portable backup.") }
                    Action { text: qsTr("Open advanced tools"); onClicked: { receiverAssistant.autoGain = false; receiverAssistant.roaming = false; screen.advanced = true; } }
                }
                Card {
                    Heading { text: qsTr("ADP / ARC4 privacy") }
                    Label { text: qsTr("P25 Phase 1/2 ADP and DMR Enhanced Privacy use the supplied 40-bit key. Create a profile here, then select it under Decryption keys in your saved system.") }
                    Action {
                        objectName: "createAdpProfile"
                        text: qsTr("Create ADP / ARC4 profile")
                        enabled: typeof decryptionProfiles !== "undefined"
                        onClicked: { adpEditor.open("", "mixed"); adpEditor.setField("mode", "direct"); adpEditor.setField("directType", "adp"); }
                    }
                }
                Card {
                    Heading { text: qsTr("Automatic saved keys") }
                    Label { text: qsTr("A received key ID selects a matching key from your assigned profile. A match means a saved key is available; it does not verify its value. Missing keys stay unavailable.") }
                    Action { objectName: "createAutomaticKeys"; text: qsTr("Set up automatic P25 / DMR keys"); onClicked: adpEditor.open("", "mixed") }
                    Action { objectName: "createNxdnKeys"; text: qsTr("Set up NXDN scrambler keys"); onClicked: adpEditor.open("", "nxdn") }
                    Label { text: qsTr("NXDN scrambler values are decimal 0–32767. NXDN48 can match a received key ID (hex 00–3F); destination mappings also support NXDN96. Use a direct profile for a fixed supplied value.") }
                }
            }
        }
    }
    Loader { anchors.fill: parent; z: 30; active: screen.aiOpen
        sourceComponent: AiReceiverScreen { onClosed: screen.aiOpen=false } }
    ExpansionScreen { id: expansionPage; anchors.fill: parent; z: 20; visible: screen.expansionOpen; enabled: visible; onClosed: screen.expansionOpen=false }
    NavigationLayer { surface: expansionPage; active: screen.visible && screen.expansionOpen; onLeave: screen.expansionOpen=false }
    AdvancedReceiverToolsScreen { id: advancedPage; anchors.fill: parent; z: 10; visible: screen.advanced; enabled: visible; onClosed: screen.advanced = false }
    DecryptionProfileEditor { id: adpEditor; objectName: "adpProfileEditor"; onSaved: screen.message = qsTr("Key profile saved. Select it under Decryption keys for your system.") }
    NavigationLayer { surface: advancedPage; active: screen.visible && screen.advanced; onLeave: screen.advanced = false }
    ConfirmDialog { id: clearNotebook; visible: false; title: qsTr("Clear notebook?"); message: qsTr("This removes stored observations from this phone."); confirmText: qsTr("Clear"); onConfirmed: receiverAssistant.clearDiscoveries() }
    FileDialog { id: audioFile; title: qsTr("Save audio clip"); fileMode: FileDialog.SaveFile; nameFilters: ["WAV (*.wav)"]
        onAccepted: screen.message = receiverTools.saveReplay(selectedFile.toString(), 60) || qsTr("Audio saved") }
    FileDialog { id: notebookFile; title: qsTr("Export notebook"); fileMode: FileDialog.SaveFile; nameFilters: ["JSON (*.json)"]
        onAccepted: screen.message = receiverAssistant.exportDiscoveries(selectedFile.toString()) || qsTr("Notebook saved") }
    FileDialog { id: captureFile; title: qsTr("Export signal and metadata"); fileMode: FileDialog.SaveFile; nameFilters: ["TAR (*.tar)"]
        onAccepted: screen.message = receiverAssistant.exportCapture(screen.captureIndex, selectedFile.toString()) || qsTr("Capture exported") }
}
