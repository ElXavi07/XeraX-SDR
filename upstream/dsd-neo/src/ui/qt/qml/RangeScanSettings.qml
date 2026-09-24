// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick

Column {
    id: form
    spacing: 10
    property var initial: rangeScanner.settings
    property bool advanced: false
    readonly property var stepValues: [5,6.25,10,12.5,15,20,25,50,100]
    readonly property var flags: ["-fa","-fA","-fU","-fs","-f1","-f2","-fi","-fn"]
    readonly property var settings: ({firstMhz:first.text.trim().replace(",","."),lastMhz:last.text.trim().replace(",","."),stepKhz:stepValues[step.currentIndex],
        decodeFlag:flags[mode.currentIndex],speed:speed.currentIndex,thresholdDb:Number(threshold.text),tailMs:Number(tail.text),maxVisitMs:Number(limit.text)*1000})
    readonly property string error: rangeScanner.validate(settings)
    function reset(s) {
        first.text=String(s.firstMhz);last.text=String(s.lastMhz);step.currentIndex=Math.max(0,stepValues.indexOf(Number(s.stepKhz)));
        mode.currentIndex=Math.max(0,flags.indexOf(s.decodeFlag));speed.currentIndex=s.speed;
        threshold.text=String(s.thresholdDb);tail.text=String(s.tailMs);limit.text=String(Number(s.maxVisitMs)/1000);
    }
    Component.onCompleted: reset(initial)
    component Label: Text { width: parent.width; wrapMode: Text.Wrap; textFormat: Text.PlainText
        color: Theme.textSecondary; font.family: Theme.sans; font.pixelSize: Theme.fontSize(14) }
    Label { text: qsTr("Start frequency (MHz)") }
    PlexInput { id:first;objectName:"rangeFirst";width:parent.width;inputMethodHints:Qt.ImhFormattedNumbersOnly;maximumLength:14 }
    Label { text: qsTr("End frequency (MHz)") }
    PlexInput { id:last;objectName:"rangeLast";width:parent.width;inputMethodHints:Qt.ImhFormattedNumbersOnly;maximumLength:14 }
    Flow { width:parent.width;spacing:8
        OutlineButton { text:"440–450 MHz";onClicked:{first.text="440.000000";last.text="450.000000";} }
        OutlineButton { text:"440–460 MHz";onClicked:{first.text="440.000000";last.text="460.000000";} }
    }
    Label { text:qsTr("Channel spacing") }
    PlexComboBox { id:step;objectName:"rangeStep";width:parent.width;model:form.stepValues.map(function(n){return n+" kHz";}) }
    Label { text:qsTr("Listening mode") }
    PlexComboBox { id:mode;objectName:"rangeMode";width:parent.width
        model:[qsTr("Auto digital"),qsTr("Analog FM (NFM)"),qsTr("AM aviation"),"DMR","P25 Phase 1","P25 Phase 2","NXDN48","NXDN96"] }
    Label { text:mode.currentIndex===0 ? qsTr("Auto digital searches supported digital protocols. Choose NFM for analog two-way voice; a specific digital mode can acquire sooner.")
        : qsTr("This scans individual frequencies. Trunked calls still need a configured system; P25 Phase 2 also needs the correct system parameters.") }
    Label { text:qsTr("Scan speed") }
    PlexComboBox { id:speed;objectName:"rangeSpeed";width:parent.width;model:[qsTr("Fast"),qsTr("Balanced"),qsTr("Thorough")] }
    Label { text:qsTr("Empty spectrum is swept in blocks. Signals receive extra decoding time. Fast scans can miss short or weak transmissions.") }
    OutlineButton { width:parent.width;text:form.advanced?qsTr("Hide scan adjustments"):qsTr("Adjust signal threshold and timing");onClicked:form.advanced=!form.advanced }
    Column { width:parent.width;spacing:10;visible:form.advanced
        Label { text:qsTr("Signal above nearby noise (6–30 dB)") }
        PlexInput { id:threshold;objectName:"rangeThreshold";width:parent.width;inputMethodHints:Qt.ImhDigitsOnly;maximumLength:2 }
        Label { text:qsTr("Resume delay after activity (300–5000 ms)") }
        PlexInput { id:tail;objectName:"rangeTail";width:parent.width;inputMethodHints:Qt.ImhDigitsOnly;maximumLength:4 }
        Label { text:qsTr("Maximum listening time (5–120 seconds; 0 unlimited)") }
        PlexInput { id:limit;objectName:"rangeLimit";width:parent.width;inputMethodHints:Qt.ImhDigitsOnly;maximumLength:3 }
        Label { text:qsTr("Lower thresholds find weaker signals and more noise. Maximum listening time moves past continuous carriers; Hold overrides it.") }
    }
    Label { objectName:"rangeValidation";visible:form.error.length>0;text:form.error;color:Theme.cyan }
}
