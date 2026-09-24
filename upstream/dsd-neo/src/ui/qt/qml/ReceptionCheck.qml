// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import "ReceptionAdvice.js" as Advice

Column {
    id: panel
    property var receiver: null
    property bool sessionRunning: false
    property bool analogMode: false
    property bool expanded: false
    property string actionError: ""
    signal disableSquelch
    readonly property var assessment: Advice.assess(receiver, sessionRunning, analogMode)
    readonly property string statusCode: assessment.code
    spacing: 10

    OutlineButton {
        objectName: "receptionCheckToggle"
        width: parent.width
        text: panel.expanded ? qsTr("Reception check −") : qsTr("Reception check +")
        onClicked: panel.expanded = !panel.expanded
    }
    Column {
        width: parent.width
        visible: panel.expanded
        spacing: 8
        Text {
            objectName: "receptionCheckTitle"
            width: parent.width
            text: panel.assessment.title
            color: Theme.textPrimary
            font.family: Theme.sans
            font.pixelSize: Theme.fontSize(15)
            font.weight: Font.DemiBold
            wrapMode: Text.Wrap
        }
        Text {
            objectName: "receptionCheckMeasurements"
            width: parent.width
            text: Advice.measurements(panel.receiver, panel.sessionRunning)
            visible: text.length > 0
            color: Theme.cyan
            font.family: Theme.mono
            font.pixelSize: Theme.fontSize(12)
            wrapMode: Text.Wrap
        }
        Text {
            objectName: "receptionCheckDetail"
            width: parent.width
            text: panel.assessment.detail
            color: Theme.textSecondary
            font.family: Theme.sans
            font.pixelSize: Theme.fontSize(13)
            wrapMode: Text.Wrap
        }
        OutlineButton {
            objectName: "receptionCheckSquelchOff"
            width: parent.width
            text: qsTr("Turn squelch off")
            visible: panel.assessment.canDisableSquelch
            onClicked: panel.disableSquelch()
        }
        Text {
            width: parent.width
            text: panel.actionError
            visible: text.length > 0
            color: Theme.alert
            font.family: Theme.sans
            font.pixelSize: Theme.fontSize(13)
            wrapMode: Text.Wrap
        }
    }
}
