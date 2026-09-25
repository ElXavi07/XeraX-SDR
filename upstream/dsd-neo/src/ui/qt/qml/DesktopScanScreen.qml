// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick

Item {
    id: screen
    signal scanRange
    signal addScanList
    signal playScanList(int row)
    signal editScanList(int row)
    signal openLab
    PlexFlickable {
        anchors.fill: parent; clip: true; contentHeight: body.height+48
        Column {
            id: body; x: Math.max(24,(parent.width-850)/2); y: 24; width: parent.width-2*x; spacing: 22
            Text { text: qsTr("Frequency scanner"); color: Theme.textPrimary; font.family: Theme.sans; font.pixelSize: Theme.fontSize(28); font.bold: true; width: parent.width; wrapMode: Text.Wrap }
            Text { width: parent.width; text: qsTr("Search a band or revisit the channels you have saved."); color: Theme.textSecondary; font.family: Theme.sans; font.pixelSize: Theme.fontSize(15); wrapMode: Text.Wrap }
            UiPanel {
                width: parent.width; height: rangeBody.height+40; radius: 16
                Column {
                    id: rangeBody; x: 20; y: 20; width: parent.width-40; spacing: 16
                    MicroLabel { text: qsTr("FREQUENCY RANGE") }
                    Text { width: parent.width; text: qsTr("Start with a range. Stop on activity."); color: Theme.textPrimary; font.family: Theme.sans; font.pixelSize: Theme.fontSize(23); font.bold: true; wrapMode: Text.Wrap }
                    Text { width: parent.width; text: qsTr("Set your start and end frequencies, channel spacing and listening mode. Hold a signal, skip it, or save a discovery while scanning."); color: Theme.textSecondary; font.family: Theme.sans; font.pixelSize: Theme.fontSize(14); wrapMode: Text.Wrap }
                    GradientButton { objectName: "desktopStartRange"; width: parent.width; text: qsTr("Configure range scan"); onClicked: screen.scanRange() }
                }
            }
            Row {
                width: parent.width; spacing: 10
                Text { width: parent.width-addButton.width-10; anchors.verticalCenter: parent.verticalCenter; text: qsTr("Saved scan lists"); color: Theme.textPrimary; font.family: Theme.sans; font.pixelSize: Theme.fontSize(20); font.bold: true; wrapMode: Text.Wrap }
                OutlineButton { id: addButton; text: qsTr("Create list"); onClicked: screen.addScanList() }
            }
            Text { visible: scanLists.count===0; width: parent.width; text: qsTr("No scan lists yet. Create one to revisit your favorite channels in order."); color: Theme.textSecondary; font.family: Theme.sans; font.pixelSize: Theme.fontSize(14); wrapMode: Text.Wrap }
            Repeater {
                model: scanLists
                ScanListCard {
                    required property int index
                    required property string name
                    required property var entries
                    required property string targetSource
                    required property var targetsCsvPath
                    required isDraft
                    width: body.width; listName: name
                    entryCount: { var changed=importedFiles.count; if(targetSource!=="csv") return entries.length; var row=importedFiles.rowForPath(targetsCsvPath||""); return row>=0 ? importedFiles.get(row).accepted : 0; }
                    onPlay: screen.playScanList(index)
                    onEdit: screen.editScanList(index)
                }
            }
            OutlineButton { objectName: "desktopOpenLab"; width: parent.width; text: qsTr("Open band survey and receiver lab"); onClicked: screen.openLab() }
        }
    }
}
