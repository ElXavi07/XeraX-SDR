// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Window
import QtQuick.Dialogs

Item {
    id: screen
    signal closed
    property string message: ""
    property var siteRows: []
    property var comparisons: []
    property var gains: [10, 20, 30, 40, 49]
    property int gainIndex: -1
    property int seconds: 0
    property int oldGain: 0
    property real testFrequency: 0
    property real fecStart: 0
    property real errStart: 0
    property real snrTotal: 0
    property int snrCount: 0
    property real clipTotal: 0
    property int clipCount: 0
    property int selectedSite: -1
    readonly property bool live: decoderHost.sessionState === 2
    Keys.onEscapePressed: screen.closed()
    Keys.onBackPressed: screen.closed()
    onVisibleChanged: {
        if (visible) { siteRows = receiverTools.sites(33.7206, -116.2156); siteMap.requestPaint(); }
        else { cancelGain(); receiverTools.stopPlayback(); }
    }
    onLiveChanged: if (!live) cancelGain()
    function cancelGain() {
        if (gainIndex >= 0 && live) commands.setTunerGain(oldGain);
        gainIndex = -1;
    }
    function startGain() {
        if (!live || metrics.tunerControlled || !metrics.radioInput || (metrics.airspy && metrics.airspy.gain_mode !== undefined)) {
            message = qsTr("Start a single RTL-SDR channel in Explore before comparing gain. Airspy uses its own gain controls."); return;
        }
        oldGain = metrics.tunerGainDb; testFrequency = metrics.centerFreqHz;
        comparisons = []; gainIndex = 0; nextGain();
    }
    function nextGain() {
        if (gainIndex >= gains.length) {
            commands.setTunerGain(oldGain); gainIndex = -1;
            message = qsTr("Original gain restored. Compare clipping and CRC success; changing radio traffic can affect the result."); return;
        }
        seconds = 0; snrTotal = 0; snrCount = 0; clipTotal = 0; clipCount = 0;
        if (!commands.setTunerGain(gains[gainIndex])) { cancelGain(); message = qsTr("Gain command was rejected."); }
    }
    Timer {
        interval: 1000; repeat: true; running: screen.gainIndex >= 0 && screen.visible
        onTriggered: {
            if (!screen.live || metrics.tunerControlled || Math.abs(metrics.centerFreqHz - screen.testFrequency) > 100) {
                screen.cancelGain(); screen.message = qsTr("Comparison canceled because the channel changed."); return;
            }
            screen.seconds++;
            if (screen.seconds === 2) { screen.fecStart = Number(metrics.ccFecOk); screen.errStart = Number(metrics.ccFecErr); }
            if (screen.seconds > 2) {
                if (metrics.snrValid) { screen.snrTotal += metrics.snrDb; screen.snrCount++; }
                if (receiverTools.health.inputValid) { screen.clipTotal += receiverTools.health.clipPct; screen.clipCount++; }
            }
            if (screen.seconds >= 12) {
                var ok = Math.max(0, Number(metrics.ccFecOk) - screen.fecStart);
                var bad = Math.max(0, Number(metrics.ccFecErr) - screen.errStart);
                var rows = screen.comparisons.slice();
                rows.push({gain: screen.gains[screen.gainIndex], snr: screen.snrCount ? screen.snrTotal / screen.snrCount : null,
                    clip: screen.clipCount ? screen.clipTotal / screen.clipCount : null, frames: ok + bad,
                    crc: ok + bad >= 10 ? 100 * ok / (ok + bad) : null});
                screen.comparisons = rows; screen.gainIndex++; screen.nextGain();
            }
        }
    }
    component Label: Text {
        width: parent.width; wrapMode: Text.Wrap; textFormat: Text.PlainText
        font.family: Theme.sans; font.pixelSize: Theme.fontSize(14); color: Theme.textPrimary
    }
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Row {
        id: header; x: 18; y: 12; spacing: 14; height: 46
        IconButton { icon: "back"; onClicked: screen.closed() }
        Label { width: screen.width - 90; text: qsTr("Receiver tools"); font.pixelSize: Theme.fontSize(23) }
    }
    PlexFlickable {
        anchors.top: header.bottom; anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        contentHeight: body.height + 32; clip: true
        Column {
            id: body; x: 18; width: parent.width - 36; spacing: 14
            Label { text: screen.message; visible: text.length > 0; color: Theme.cyan }
            Label { text: receiverTools.health.tone || qsTr("No stable tone identified") }
            Label { text: qsTr("Received audio replay"); font.bold: true; font.pixelSize: Theme.fontSize(19) }
            Label { text: qsTr("%1 seconds buffered · up to 60 seconds · silent gaps omitted. Reception continues during replay; save a WAV at any time.").arg(receiverTools.replaySeconds.toFixed(1)) }
            Flow {
                width: parent.width; spacing: 8
                OutlineButton { text: qsTr("Replay 30 s"); onClicked: screen.message = receiverTools.playReplay(30) || qsTr("Playing received audio") }
                OutlineButton { text: qsTr("Replay 60 s"); onClicked: screen.message = receiverTools.playReplay(60) || qsTr("Playing received audio") }
                OutlineButton { text: qsTr("Stop replay"); onClicked: receiverTools.stopPlayback() }
                OutlineButton { text: qsTr("Save WAV"); onClicked: clipFile.open() }
                OutlineButton { text: qsTr("Clear buffer"); onClicked: receiverTools.clearReplay() }
            }
            Label { text: qsTr("Reception comparison"); font.bold: true; font.pixelSize: Theme.fontSize(19) }
            Label { text: qsTr("Try five gain settings on the same frequency. Each settles for 2 seconds, then measures for 10 seconds. Use an active channel; CRC results need at least 10 control frames. No gain setting can restore an overloaded signal.") }
            Label { text: receiverTools.health.inputValid ? qsTr("Input %1 dBFS · clipping %2%").arg(Number(receiverTools.health.rmsDbfs).toFixed(1)).arg(Number(receiverTools.health.clipPct).toFixed(3)) : qsTr("Input level unavailable") }
            Flow {
                width: parent.width; spacing: 8
                OutlineButton { text: screen.gainIndex >= 0 ? qsTr("Testing %1 dB · %2 s").arg(screen.gains[screen.gainIndex]).arg(screen.seconds) : qsTr("Compare gain"); enabled: screen.gainIndex < 0; onClicked: screen.startGain() }
                OutlineButton { text: qsTr("Cancel and restore"); visible: screen.gainIndex >= 0; onClicked: screen.cancelGain() }
            }
            Repeater {
                model: screen.comparisons
                delegate: Column {
                    required property var modelData
                    width: body.width; spacing: 4
                    Label { text: modelData.gain + " dB · SNR " + (modelData.snr === null ? "—" : modelData.snr.toFixed(1))
                        + " · clipping " + (modelData.clip === null ? "—" : modelData.clip.toFixed(3) + "%")
                        + " · CRC " + (modelData.crc === null ? qsTr("insufficient frames") : modelData.crc.toFixed(1) + "%") }
                    OutlineButton { text: qsTr("Use %1 dB").arg(modelData.gain); enabled: screen.gainIndex < 0 && screen.live
                        onClicked: { if (commands.setTunerGain(modelData.gain)) prefs.gainDb = modelData.gain; } }
                }
            }
            Label { text: qsTr("Receiver profiles"); font.bold: true; font.pixelSize: Theme.fontSize(19) }
            Label { text: qsTr("Name profiles for each dongle, antenna and band. Applying one changes defaults for the next session.") }
            PlexInput { id: profileName; width: parent.width; placeholderText: qsTr("Example: RTL V3 · VHF roof antenna") }
            OutlineButton { text: qsTr("Save current defaults"); onClicked: screen.message = receiverTools.saveProfile(profileName.text, prefs.gainDb, prefs.ppm, prefs.bandwidthKhz, prefs.biasTee) ? qsTr("Profile saved") : qsTr("Check the name and receiver settings.") }
            Repeater {
                model: receiverTools.profiles
                delegate: Flow {
                    required property var modelData; required property int index
                    width: body.width; spacing: 6
                    OutlineButton { text: modelData.name; onClicked: { receiverTools.applyProfile(index); screen.message = qsTr("Profile applied to next-session defaults"); } }
                    OutlineButton { text: qsTr("Remove"); onClicked: receiverTools.removeProfile(index) }
                }
            }
            Label { text: qsTr("Local site map · Indio, 50 mi"); font.bold: true; font.pixelSize: Theme.fontSize(19) }
            Label { text: qsTr("Offline position plot of your saved sites. North is up. Blue: saved, green: digital call observed, gray: avoided. Database locations may be coverage centers.") }
            Canvas {
                id: siteMap; width: parent.width; height: width; property real radius: width * 0.43
                onPaint: {
                    var ctx = getContext("2d"); ctx.reset(); ctx.fillStyle = "#101b29"; ctx.fillRect(0, 0, width, height);
                    ctx.strokeStyle = "#405568"; ctx.lineWidth = 1;
                    for (var r = 1; r <= 2; r++) { ctx.beginPath(); ctx.arc(width/2, height/2, radius*r/2, 0, 2*Math.PI); ctx.stroke(); }
                    ctx.fillStyle = "#ffffff"; ctx.font = "13px sans-serif"; ctx.fillText("N", width/2-5, 17); ctx.fillText("Indio", width/2+7, height/2+5);
                    ctx.beginPath(); ctx.arc(width/2, height/2, 3, 0, 2*Math.PI); ctx.fill();
                    for (var i=0; i<screen.siteRows.length; i++) {
                        var s=screen.siteRows[i]; if (s.distanceMi > 50) continue;
                        var dx=(s.siteLon+116.2156)*57.45/50*radius;
                        var dy=(s.siteLat-33.7206)*69.0/50*radius;
                        ctx.fillStyle=s.avoidSite ? "#81909b" : s.heardAt > 0 ? "#73dfa1" : "#52c5ff";
                        ctx.beginPath(); ctx.arc(width/2+dx, height/2-dy, 5, 0, 2*Math.PI); ctx.fill();
                    }
                }
            }
            Repeater {
                model: screen.siteRows
                delegate: Label { required property var modelData; visible: modelData.distanceMi <= 50
                    text: modelData.name + " · " + modelData.distanceMi.toFixed(1) + " mi" }
            }
            Label { visible: screen.siteRows.length === 0; text: qsTr("Import or save sites with location metadata to populate this map.") }
            Label { text: qsTr("Portable backup"); font.bold: true; font.pixelSize: Theme.fontSize(19) }
            Label { text: qsTr("Merge saved systems, scan lists, CSV labels and receiver defaults onto another phone. Accounts, radio keys and recordings are excluded. Existing systems remain; restored copies get new IDs. Imported target CSVs become editable lists; lists with scoped CSV options need a separate CSV export.") }
            Flow {
                width: parent.width; spacing: 8
                OutlineButton { text: qsTr("Save backup"); onClicked: backupFile.open() }
                OutlineButton { text: qsTr("Restore backup"); enabled: !screen.live; onClicked: restoreFile.open() }
            }
            Label { text: qsTr("Activity alerts"); font.bold: true; font.pixelSize: Theme.fontSize(19) }
            Label { text: qsTr("Enter talkgroups and radio IDs, for example tg:1234, rid:5678. Alerts match across systems, need Android notification permission, and repeat at most once per 30 seconds. Clear the field to disable.") }
            PlexInput { id: alertRules; width: parent.width; text: receiverTools.alertRules(); placeholderText: "tg:1234, rid:5678" }
            OutlineButton { text: qsTr("Save alert rules"); onClicked: screen.message = receiverTools.setAlertRules(alertRules.text) ? qsTr("Alert rules saved") : qsTr("Use tg: or rid: followed by a number from 1 to 16777215, up to 64 rules.") }
            Label { text: qsTr("Phone health"); font.bold: true; font.pixelSize: Theme.fontSize(19) }
            Label { text: qsTr("Battery: %1% · thermal level: %2 · battery saver: %3").arg(receiverTools.health.battery === undefined ? "—" : receiverTools.health.battery)
                .arg(receiverTools.health.thermal === undefined ? "—" : receiverTools.health.thermal).arg(receiverTools.health.powerSave ? qsTr("on") : qsTr("off")) }
        }
    }
    FileDialog { id: clipFile; title: qsTr("Save received audio"); fileMode: FileDialog.SaveFile; nameFilters: ["WAV audio (*.wav)"]
        onAccepted: screen.message = receiverTools.saveReplay(selectedFile.toString(), 60) || qsTr("Audio saved") }
    FileDialog { id: backupFile; title: qsTr("Save XeraX backup"); fileMode: FileDialog.SaveFile; nameFilters: ["XeraX backup (*.json)"]
        onAccepted: screen.message = receiverTools.backup(selectedFile.toString()) || qsTr("Backup saved") }
    FileDialog { id: restoreFile; title: qsTr("Restore XeraX backup"); fileMode: FileDialog.OpenFile; nameFilters: ["XeraX backup (*.json)"]
        onAccepted: { screen.message = receiverTools.restore(selectedFile.toString()) || qsTr("Backup restored"); screen.siteRows = receiverTools.sites(33.7206, -116.2156); siteMap.requestPaint(); } }
}
