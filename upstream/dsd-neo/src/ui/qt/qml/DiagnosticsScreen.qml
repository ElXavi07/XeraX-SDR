// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Window

Item {
    id: screen
    signal closed
    function receptionSummary() {
        var h=receiverTools.health;
        var result={time:new Date().toISOString(),running:decoderHost.running,
            tunedHz:metrics.centerFreqHz,captureHz:h.captureHz,captureRate:h.captureRate,
            iqBytes:h.iqBytes,iqAgeMs:h.iqAgeMs,iqFresh:h.iqFresh,digitalSync:metrics.syncedHere,
            pcmFrames:h.audioPcmFrames,outputFrames:h.audioOutputFrames,
            receiverAudio:receiverExpansion.status.audible,siteCapture:receiverExpansion.status.siteCapture};
        result.receivers=receiverExpansion.lanes.map(function(x) { return {state:x.state,
            frequency:x.frequency,plannedFrequency:x.plannedFrequency,bytes:x.bytes,dropped:x.dropped,
            pcmFrames:x.pcmFrames,outputFrames:x.outputFrames,active:x.active,audible:x.audible,error:x.error}; });
        return "XeraX reception status\n"+JSON.stringify(result,null,2)+"\n\n";
    }

    Keys.onEscapePressed: Navigation.back(screen.Window.window)
    Keys.onBackPressed: Navigation.back(screen.Window.window)
    // The layer clears input during activation; take focus after its bindings settle.
    onVisibleChanged: if (visible) Qt.callLater(function () {
        if (screen.visible && Navigation.allows(screen))
            screen.forceActiveFocus();
    })

    Rectangle {
        anchors.fill: parent
        color: Theme.bg
    }

    Item {
        id: header
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: Theme.screenPadding
        height: 46

        IconButton {
            id: back
            objectName: "diagnosticsBack"
            icon: "back"
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            onClicked: screen.closed()
        }

        Text {
            anchors.left: back.right
            anchors.leftMargin: 14
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            text: qsTr("Diagnostics")
            font.family: Theme.sans
            font.pixelSize: Theme.fontSize(22)
            font.weight: Font.Bold
            font.letterSpacing: -0.22
            color: Theme.textPrimary
            elide: Text.ElideRight
        }
    }

    Column {
        id: controls
        anchors.top: header.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: Theme.screenPadding
        spacing: Theme.gap

        Text {
            width: parent.width
            text: qsTr("Current-process decoder and host diagnostics plus a bounded redacted persistent tail from previous runs. Not a native-crash or ANR capture.")
            wrapMode: Text.Wrap
            font.family: Theme.sans
            font.pixelSize: Theme.fontSize(14)
            color: Theme.textPrimary
        }

        Flow {
            width: parent.width
            spacing: Theme.gap

            OutlineButton {
                objectName: "diagnosticsPause"
                text: diagnosticsLog.paused ? qsTr("Resume (%1)").arg(diagnosticsLog.pendingCount) : qsTr("Pause")
                onClicked: diagnosticsLog.paused = !diagnosticsLog.paused
            }
            OutlineButton {
                objectName: "diagnosticsCopy"
                text: qsTr("Copy")
                onClicked: diagnosticsLog.copyAll(screen.receptionSummary())
            }
            OutlineButton {
                objectName: "diagnosticsClear"
                text: qsTr("Clear")
                onClicked: clearConfirm.open()
            }
            OutlineButton {
                objectName: "diagnosticsShare"
                visible: decoderHost.shareSupported
                text: qsTr("Share diagnostics")
                onClicked: decoderHost.shareDiagnostics(screen.receptionSummary()+diagnosticsLog.allText(), qsTr("XeraX SDR diagnostics"))
            }
        }
    }

    ListView {
        id: list
        anchors.top: controls.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: Theme.screenPadding
        clip: true
        model: diagnosticsLog
        delegate: Text {
            required property string line
            width: list.width
            text: line
            textFormat: Text.PlainText
            wrapMode: Text.WrapAnywhere
            color: Theme.textPrimary
            font.family: Theme.mono
            font.pixelSize: Theme.fontSize(12)
        }
    }

    ConfirmDialog {
        id: clearConfirm
        objectName: "diagnosticsClearConfirm"
        title: qsTr("Clear diagnostics?")
        message: qsTr("The current log and the saved previous-run tail are removed.")
        confirmText: qsTr("Clear log")
        destructive: true
        onConfirmed: diagnosticsLog.clear()
    }
}
