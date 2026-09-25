// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick

Rectangle {
    id: card
    signal configure
    signal scan
    radius: 18; border.color: Qt.alpha(Theme.cyan, 0.22)
    height: body.height + 48
    gradient: Gradient {
        orientation: Gradient.Horizontal
        GradientStop { position: 0; color: Theme.dark ? "#122F35" : "#DDF3EF" }
        GradientStop { position: 1; color: Theme.dark ? "#142331" : "#E7EFFA" }
    }
    Image { anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 22; width: 115; height: 115; opacity: Theme.dark ? 0.16 : 0.07; source: "xerax-icon.svg" }
    Column {
        id: body; x: 24; y: 24; width: parent.width-48; spacing: 14
        Text { text: qsTr("TUNE IN. EXPLORE MORE."); color: Theme.cyan; font.family: Theme.mono; font.pixelSize: Theme.fontSize(10); font.letterSpacing: 1.3 }
        Text { width: parent.width; text: qsTr("Find your next signal."); color: Theme.textPrimary; font.family: Theme.sans; font.pixelSize: Theme.fontSize(30); font.bold: true; font.letterSpacing: -0.6; wrapMode: Text.Wrap }
        Text { width: parent.width; text: qsTr("Connect a receiver, choose a frequency, and listen. Your systems and discoveries stay within reach."); color: Theme.textSecondary; font.family: Theme.sans; font.pixelSize: Theme.fontSize(14); wrapMode: Text.Wrap; lineHeight: 1.2 }
        Flow {
            width: parent.width; spacing: 10
            GradientButton { objectName: "desktopConfigureReceiver"; width: parent.width<490 ? parent.width : (parent.width-10)/2; text: qsTr("Set up receiver"); onClicked: card.configure() }
            OutlineButton { objectName: "desktopScanFrequencies"; width: parent.width<490 ? parent.width : (parent.width-10)/2; text: qsTr("Scan frequencies"); onClicked: card.scan() }
        }
    }
}
