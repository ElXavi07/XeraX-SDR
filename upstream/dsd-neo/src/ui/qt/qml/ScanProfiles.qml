// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick

Column {
    id: panel
    property var settings: ({})
    signal chosen(var values)
    spacing: 8

    readonly property var profiles: [
        {label: qsTr("Balanced"), defaultDwellMs: 3000, defaultHoldMs: 1200, maxVisitMs: 0, voiceOnly: false,
         detail: qsTr("3 s idle dwell, 1.2 s activity hold, no visit limit. A starting point for mixed lists.")},
        {label: qsTr("Patrol"), defaultDwellMs: 1000, defaultHoldMs: 800, maxVisitMs: 15000, voiceOnly: true,
         detail: qsTr("1 s idle dwell, voice-only hold, 15 s visit limit. Checks more often, but can miss short calls or cut a busy call short.")},
        {label: qsTr("Patient"), defaultDwellMs: 5000, defaultHoldMs: 2000, maxVisitMs: 0, voiceOnly: false,
         detail: qsTr("5 s idle dwell, 2 s activity hold, no visit limit. More acquisition time; other channels are checked less often.")}
    ]
    readonly property int selectedIndex: {
        for (var i = 0; i < profiles.length; ++i) {
            var p = profiles[i];
            if (Number(settings.defaultDwellMs) === p.defaultDwellMs
                && Number(settings.defaultHoldMs) === p.defaultHoldMs
                && Number(settings.maxVisitMs) === p.maxVisitMs
                && settings.voiceOnly === p.voiceOnly)
                return i;
        }
        return -1;
    }
    function choose(index) {
        if (index < 0 || index >= profiles.length)
            return;
        var p = profiles[index];
        chosen({defaultDwellMs: p.defaultDwellMs, defaultHoldMs: p.defaultHoldMs,
                   maxVisitMs: p.maxVisitMs, voiceOnly: p.voiceOnly});
    }
    MicroLabel { text: qsTr("Scan timing presets") }
    Flow {
        width: parent.width
        spacing: 8
        Repeater {
            model: panel.profiles
            OutlineButton {
                required property var modelData
                required property int index
                objectName: "scanPreset" + index
                text: modelData.label
                textColor: panel.selectedIndex === index ? Theme.cyan : Theme.buttonSecondaryText
                onClicked: panel.choose(index)
            }
        }
    }
    Text {
        objectName: "scanPresetDescription"
        width: parent.width
        text: panel.selectedIndex < 0 ? qsTr("Custom timing. Choose a preset or edit timing under Advanced.")
                                    : panel.profiles[panel.selectedIndex].detail
        color: Theme.textSecondary
        font.family: Theme.sans
        font.pixelSize: Theme.fontSize(13)
        wrapMode: Text.Wrap
    }
    Text {
        width: parent.width
        text: qsTr("Presets change list defaults only. Per-target overrides stay in effect. One receiver checks one frequency at a time.")
        color: Theme.textSubdued
        font.family: Theme.sans
        font.pixelSize: Theme.fontSize(12)
        wrapMode: Text.Wrap
    }
}
