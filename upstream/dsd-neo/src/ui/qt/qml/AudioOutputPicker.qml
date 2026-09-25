// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick

Column {
    id: picker
    property var routing: ({})
    property string reportedRoute: ""
    property string errorText: ""
    property var health: ({})
    property bool diagnosticsAvailable: false
    signal outputSelected(string key)
    signal restoreRequested
    signal testRequested
    readonly property var choices: routing && routing.choices ? routing.choices : []
    readonly property bool routeMismatch: routing && routing.requestedId > 0 && routing.actualId > 0 && routing.requestedId !== routing.actualId
    spacing: 8

    Text {
        width: parent.width
        text: qsTr("Audio output")
        color: Theme.textPrimary
        font.family: Theme.sans
        font.pixelSize: Theme.fontSize(14)
        font.weight: Font.DemiBold
    }
    PlexComboBox {
        id: selector
        objectName: "audioOutputSelector"
        width: parent.width
        visible: picker.choices.length > 0
        model: picker.choices
        textRole: "label"
        currentIndex: {
            for (var i = 0; i < picker.choices.length; ++i)
                if (picker.choices[i].key === picker.routing.selected) return i;
            return -1;
        }
        onActivated: function(index) {
            if (index >= 0 && index < picker.choices.length) {
                picker.errorText = "";
                picker.outputSelected(picker.choices[index].key);
            }
        }
    }
    OutlineButton {
        objectName: "usePhoneSpeaker"
        width: parent.width
        text: qsTr("Use phone speaker")
        visible: picker.choices.some(function(choice) { return choice.key === "speaker"; })
        onClicked: { picker.errorText = ""; picker.outputSelected("speaker"); }
    }
    Text {
        objectName: "audioOutputReported"
        width: parent.width
        text: qsTr("Reported output: %1").arg(picker.reportedRoute || qsTr("No active output"))
        color: picker.routeMismatch ? Theme.magenta : Theme.textSecondary
        font.family: Theme.sans
        font.pixelSize: Theme.fontSize(12)
        wrapMode: Text.Wrap
    }
    Column {
        width: parent.width
        visible: picker.diagnosticsAvailable
        spacing: 8
        Text {
            objectName: "audioFlowStatus"
            width: parent.width
            text: picker.health.testingAudio ? qsTr("Playing test tones")
                : picker.health.focusLost ? qsTr("Audio paused by another app")
                : picker.health.replaying ? qsTr("Replay is playing")
                : picker.health.workerAudio ? qsTr("Listening to an extra receiver")
                : picker.health.audioSuppressed ? qsTr("Live speaker output is paused")
                : picker.health.mediaVolume === 0 ? qsTr("Media volume is zero")
                : picker.health.audioPcmArriving && !picker.health.audioNonzero ? qsTr("The decoder is producing silence")
                : picker.health.audioOutputMoving ? (picker.health.desktop ? qsTr("Windows is accepting audio") : qsTr("Android is accepting audio"))
                : picker.health.audioPcmArriving ? (picker.health.desktop ? qsTr("Audio is decoded; waiting for Windows output") : qsTr("Audio is decoded; waiting for Android output"))
                : qsTr("No decoded audio is arriving")
            color: Theme.textSecondary
            font.pixelSize: Theme.fontSize(12)
            wrapMode: Text.Wrap
        }
        OutlineButton {
            objectName: "restoreSpeakerAudio"
            width: parent.width
            text: picker.health.desktop ? qsTr("Stop replay and return to live audio") : qsTr("Restore speaker audio")
            enabled: !picker.health.testingAudio
            onClicked: picker.restoreRequested()
        }
        OutlineButton {
            objectName: "testAudioOutput"
            width: parent.width
            text: qsTr("Test sound")
            enabled: !picker.health.testingAudio && !(picker.health.desktop && picker.health.receiverActive)
            onClicked: picker.testRequested()
        }
        Text {
            width: parent.width
            text: picker.health.audioTestStatus || qsTr("Two short tones test the selected output without a radio signal. Use media volume for loudness.")
            color: Theme.textSecondary
            font.pixelSize: Theme.fontSize(12)
            wrapMode: Text.Wrap
        }
    }
    Text {
        width: parent.width
        visible: picker.choices.length > 0 && !picker.health.desktop
        text: picker.routeMismatch
            ? qsTr("Requested output differs. It applies when audio resumes; Android may decline a route. Check the reported output while listening.")
            : qsTr("Changes apply with the next audio. Use media volume for loudness. Disconnected outputs fall back to the phone speaker.")
        color: Theme.textSecondary
        font.family: Theme.sans
        font.pixelSize: Theme.fontSize(12)
        wrapMode: Text.Wrap
    }
    Text {
        objectName: "audioOutputError"
        width: parent.width
        text: picker.errorText || (picker.routing ? picker.routing.note || "" : "")
        visible: text.length > 0
        color: Theme.magenta
        font.family: Theme.sans
        font.pixelSize: Theme.fontSize(12)
        wrapMode: Text.Wrap
    }
}
