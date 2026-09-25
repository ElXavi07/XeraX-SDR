// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick

Rectangle {
    id: sidebar
    property int currentIndex: 0
    signal selected(int index)
    signal openAi
    color: Theme.panel
    Rectangle { anchors.right: parent.right; height: parent.height; width: 1; color: Theme.panelBorder }
    Row {
        x: 20; y: 28; spacing: 12
        LogoMark { width: 42; height: 42 }
        Column {
            anchors.verticalCenter: parent.verticalCenter; spacing: 3
            Text { text: "XeraX SDR"; color: Theme.textPrimary; font.family: Theme.sans; font.pixelSize: Theme.fontSize(19); font.bold: true }
            Text { text: qsTr("RADIO WORKSPACE"); color: Theme.textSubdued; font.family: Theme.mono; font.pixelSize: Theme.fontSize(9); font.letterSpacing: 1 }
        }
    }
    Column {
        x: 12; y: 112; width: parent.width - 24; spacing: 8
        Repeater {
            model: [qsTr("Listen"), qsTr("Scan"), qsTr("Calls"), qsTr("Tools")]
            Rectangle {
                id: entry
                required property int index
                required property string modelData
                objectName: "desktopNav" + index
                readonly property bool active: sidebar.currentIndex === [0,3,1,2][index]
                width: parent.width; height: Math.max(54, label.implicitHeight + 28); radius: 10
                color: active ? Qt.alpha(Theme.cyan, Theme.dark ? 0.12 : 0.08) : hover.hovered ? Qt.alpha(Theme.textPrimary, 0.04) : "transparent"
                border.color: active ? Qt.alpha(Theme.cyan, 0.25) : "transparent"
                activeFocusOnTab: enabled && Navigation.allows(sidebar)
                Accessible.role: Accessible.PageTab; Accessible.name: modelData; Accessible.selected: active
                Accessible.ignored: !visible || !Navigation.allows(sidebar)
                Accessible.onPressAction: choose()
                function choose() { if (enabled && Navigation.allows(sidebar)) sidebar.selected([0,3,1,2][index]); }
                Keys.onReturnPressed: choose()
                Keys.onEnterPressed: choose()
                Keys.onSpacePressed: choose()
                FocusFrame {}
                Rectangle { visible: entry.active; x: 0; width: 3; height: 22; radius: 1.5; anchors.verticalCenter: parent.verticalCenter; color: Theme.cyan }
                // Simple vector glyphs stay crisp at any Windows display scale.
                Canvas {
                    x: 19; width: 22; height: 22; anchors.verticalCenter: parent.verticalCenter
                    property color ink: entry.active ? Theme.cyan : Theme.textSecondary
                    onInkChanged: requestPaint()
                    onPaint: {
                        var c=getContext("2d"); c.reset(); c.strokeStyle=ink; c.lineWidth=1.7; c.lineCap="round"; c.lineJoin="round";
                        c.beginPath();
                        if (entry.index===0) { for(var i=0;i<5;i++){var h=[6,12,18,12,6][i];c.moveTo(3+i*4,11-h/2);c.lineTo(3+i*4,11+h/2);} }
                        else if(entry.index===1) {c.arc(10,10,7,0,Math.PI*2);c.moveTo(15,15);c.lineTo(21,21);c.moveTo(6,10);c.lineTo(14,10);c.moveTo(10,6);c.lineTo(10,14);}
                        else if(entry.index===2) {for(var j=0;j<3;j++){c.moveTo(3,5+j*6);c.lineTo(4,5+j*6);c.moveTo(8,5+j*6);c.lineTo(20,5+j*6);}}
                        else {for(var k=0;k<3;k++){c.moveTo(2,5+k*6);c.lineTo(20,5+k*6);var x=[7,15,9][k];c.moveTo(x,2+k*6);c.lineTo(x,8+k*6);}}
                        c.stroke();
                    }
                }
                Text { id: label; x: 55; width: parent.width-65; anchors.verticalCenter: parent.verticalCenter; text: entry.modelData; color: entry.active ? Theme.cyan : Theme.textSecondary; font.family: Theme.sans; font.pixelSize: Theme.fontSize(15); font.weight: entry.active ? Font.DemiBold : Font.Normal; wrapMode: Text.Wrap }
                HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
                TapHandler { onTapped: entry.choose() }
            }
        }
        OutlineButton { objectName: "desktopAiButton"; width: parent.width; text: qsTr("AI assistant"); onClicked: sidebar.openAi() }
    }
    Column {
        x: 24; width: parent.width-48; anchors.bottom: parent.bottom; anchors.bottomMargin: 26; spacing: 9
        Rectangle { width: parent.width; height: 1; color: Theme.divider }
        Text { width: parent.width; text: qsTr("Windows community preview"); color: Theme.textSecondary; font.family: Theme.sans; font.pixelSize: Theme.fontSize(12); wrapMode: Text.Wrap }
        Text { text: "4.3.2  /  RC2"; color: Theme.textSubdued; font.family: Theme.mono; font.pixelSize: Theme.fontSize(10) }
    }
}
