// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Dialogs
Item {
    id: screen
    property int shown: 50
    property bool history: false
    property string message: ""
    property string exportId: ""
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Row { id: tabs; x: 14; y: 12; width: parent.width-28; spacing: 8
        OutlineButton { width: (parent.width-8)/2; text: qsTr("Recordings"); labelHorizontalPadding: 8; textColor: !screen.history?Theme.cyan:Theme.textSecondary; onClicked: screen.history=false }
        OutlineButton { width: (parent.width-8)/2; text: qsTr("Call history"); labelHorizontalPadding: 8; textColor: screen.history?Theme.cyan:Theme.textSecondary; onClicked: screen.history=true }
    }
    HistoryScreen { anchors.top: tabs.bottom; anchors.bottom: parent.bottom; width: parent.width; visible: screen.history }
    PlexFlickable { id: scroll; x: 14; width: parent.width-28; anchors.top: tabs.bottom; anchors.topMargin: 12; anchors.bottom: parent.bottom; contentHeight: body.height+24; visible: !screen.history; clip: true
        Column { id: body; width: scroll.width; spacing: 12
            Text { width: parent.width; wrapMode: Text.Wrap; color: Theme.textPrimary; font.family: Theme.sans; font.pixelSize: Theme.fontSize(21); text: qsTr("Your calls") }
            OutlineButton { width: parent.width; text: callLibrary.recording?qsTr("Recording enabled · next session"):qsTr("Enable per-call recording"); onClicked: callLibrary.recording=!callLibrary.recording }
            Text { width: parent.width; wrapMode: Text.Wrap; color: Theme.textSecondary; font.family: Theme.sans; font.pixelSize: Theme.fontSize(13); text: qsTr("The setting applies when a receiver starts. Favorites are protected from automatic cleanup. Search by talkgroup, source, name, date or frequency; enter * for favorites.") }
            PlexInput { width: parent.width; label: qsTr("Search recordings"); onTextChanged: callLibrary.query=text }
            PlexComboBox { width: parent.width; model: [qsTr("Keep 7 days"),qsTr("Keep 30 days"),qsTr("Keep 90 days"),qsTr("Keep 1 year")]; currentIndex: [7,30,90,365].indexOf(callLibrary.retentionDays); onActivated: callLibrary.retentionDays=[7,30,90,365][currentIndex] }
            Text { width: parent.width; wrapMode: Text.Wrap; color: Theme.cyan; font.family: Theme.sans; font.pixelSize: Theme.fontSize(14); text: screen.message; visible: text.length>0 }
            Repeater { model: callLibrary.calls.slice(0,screen.shown)
                Rectangle { required property var modelData; width: parent.width; height: card.height+28; radius: 14; color: Theme.panel; border.color: Theme.panelBorder
                    Column { id: card; x: 14; y: 14; width: parent.width-28; spacing: 10
                        Text { width: parent.width; wrapMode: Text.Wrap; color: Theme.textPrimary; font.family: Theme.sans; font.pixelSize: Theme.fontSize(17); text: (modelData.favorite?"★ ":"")+(modelData.talkgroup_tag || modelData.short_name || qsTr("Call"))+" · "+modelData.talkgroup }
                        Text { width: parent.width; wrapMode: Text.Wrap; color: Theme.textSecondary; font.family: Theme.sans; font.pixelSize: Theme.fontSize(13); text: modelData.when+" · "+modelData.duration+" s\n"+qsTr("Source %1 · %2 MHz").arg(modelData.source||"—").arg(Number(modelData.freq/1e6).toFixed(6)) }
                        OutlineButton { width: parent.width; text: qsTr("Play"); onClicked: screen.message=callLibrary.play(modelData.id) }
                        OutlineButton { width: parent.width; text: modelData.favorite?qsTr("Remove favorite"):qsTr("Favorite"); onClicked: callLibrary.favorite(modelData.id,!modelData.favorite) }
                        OutlineButton { width: parent.width; text: qsTr("Export audio and metadata"); onClicked: { screen.exportId=modelData.id; exportFolder.open(); } }
                    }
                }
            }
            OutlineButton { width: parent.width; visible: callLibrary.calls.length>screen.shown; text: qsTr("Show more calls"); onClicked: screen.shown+=50 }
            Text { width: parent.width; wrapMode: Text.Wrap; color: Theme.textSecondary; font.family: Theme.sans; font.pixelSize: Theme.fontSize(14); text: qsTr("No completed recordings match. Start reception with recording enabled."); visible: callLibrary.calls.length===0 }
        }
    }
    FolderDialog { id: exportFolder; title: qsTr("Export call"); onAccepted: screen.message=callLibrary.exportCall(screen.exportId,selectedFolder.toString()) || qsTr("Call exported") }
}
