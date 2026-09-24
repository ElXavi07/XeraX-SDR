// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Window

Item {
    id:screen
    signal closed
    property string message:""
    readonly property var state:rangeScanner.status
    function revealInput(){if(screen.Window.window)Theme.revealFocus(scroll,body,screen.Window.window.activeFocusItem);}
    function phaseLabel(){
        switch(state.phase){
        case "starting":return qsTr("Starting receiver");case "tuning":return qsTr("Tuning and settling");
        case "sweeping":return qsTr("Sweeping for signals");case "acquiring":return qsTr("Trying to acquire signal");
        case "listening":return qsTr("Receiving activity");case "tail":return qsTr("Waiting before resuming");
        case "held":return qsTr("Held on this frequency");default:return qsTr("Ready to scan");}
    }
    NavigationLayer { active:screen.visible;surface:screen;onLeave:screen.closed() }
    Connections {target:screen.Window.window;function onActiveFocusItemChanged(){Qt.callLater(screen.revealInput);}}
    component Label: Text {width:parent.width;wrapMode:Text.Wrap;textFormat:Text.PlainText;font.family:Theme.sans;font.pixelSize:Theme.fontSize(14);color:Theme.textSecondary}
    component Action: OutlineButton {width:parent.width}
    Rectangle {anchors.fill:parent;color:Theme.bg}
    Row {id:header;x:14;y:12;width:parent.width-28;spacing:10
        IconButton {icon:"back";onClicked:screen.closed()}
        Label {width:parent.width-58;text:qsTr("Frequency range scanner");color:Theme.textPrimary;font.pixelSize:Theme.fontSize(22);font.bold:true}
    }
    PlexFlickable {
        id:scroll;objectName:"rangeScroll";x:14;width:parent.width-28;anchors.top:header.bottom;anchors.topMargin:14;anchors.bottom:parent.bottom
        anchors.bottomMargin:Math.max(0,screen.height-Theme.keyboardTop(screen));contentHeight:body.height+24;clip:true
        onHeightChanged:Qt.callLater(screen.revealInput)
        Column {id:body;width:scroll.width;spacing:12
            Label {objectName:"rangePhase";text:screen.phaseLabel();color:Theme.cyan;font.pixelSize:Theme.fontSize(20);font.bold:true}
            Label {visible:rangeScanner.active;text:qsTr("%1 MHz · pass %2").arg((Number(screen.state.frequency||0)/1e6).toFixed(6)).arg(screen.state.passes||1);font.family:Theme.mono}
            Label {visible:rangeScanner.active;text:qsTr("Surveyed %1 / %2 channel positions · %3 found · %4 avoided").arg(screen.state.checked||0).arg(screen.state.positions||0).arg(screen.state.hits||0).arg(screen.state.avoided||0)}
            Action {objectName:"rangeStop";visible:rangeScanner.active || !!screen.state.pending;text:qsTr("Stop range scan");onClicked:rangeScanner.stop()}
            Grid {width:parent.width;columns:2;spacing:8;visible:rangeScanner.active
                OutlineButton {width:(parent.width-8)/2;objectName:"rangeHold";text:screen.state.held?qsTr("Resume"):qsTr("Hold");enabled:!!screen.state.candidate;onClicked:rangeScanner.hold(!screen.state.held)}
                OutlineButton {width:(parent.width-8)/2;objectName:"rangeSkip";text:qsTr("Skip");enabled:!!screen.state.candidate;onClicked:rangeScanner.skip()}
                OutlineButton {width:(parent.width-8)/2;objectName:"rangeAvoid";text:qsTr("Avoid frequency");enabled:!!screen.state.candidate;onClicked:rangeScanner.avoid()}
                OutlineButton {width:(parent.width-8)/2;text:qsTr("Clear avoids");enabled:Number(screen.state.avoided)>0;onClicked:rangeScanner.clearAvoids()}
            }
            Label {visible:screen.message.length>0;text:screen.message;color:Theme.cyan}
            Label {text:{var lang=appLanguage.language;return appLanguage.text(screen.state.message||"");}visible:text.length>0}
            Column {width:parent.width;spacing:12;visible:!rangeScanner.active && !screen.state.pending
                RangeScanSettings {id:settings;width:parent.width}
                Action {objectName:"rangeStart";text:qsTr("Start range scan");enabled:settings.error.length===0 && decoderHost.running
                    onClicked:{screen.message=rangeScanner.start(settings.settings);Qt.inputMethod.hide();scroll.contentY=0;}}
                Label {visible:!decoderHost.running;text:qsTr("Open Explore, choose your radio and enable Scan a frequency range to start a new receiver session.")}
            }
            Label {visible:rangeScanner.active;text:qsTr("Scanning runs on this phone without AI or an API key. Source delays and signal activity affect sweep time. Close this page to see the receiver; scanning continues.")}
            Label {visible:rangeScanner.hits.length>0;text:qsTr("Found frequencies");font.bold:true;font.pixelSize:Theme.fontSize(18)}
            Repeater {model:rangeScanner.hits
                Rectangle {required property var modelData;required property int index
                    width:body.width;height:hitBody.height+24;color:Theme.panel;radius:12;border.color:Theme.panelBorder
                    Column {id:hitBody;x:12;y:12;width:parent.width-24;spacing:8
                        Label {text:(Number(modelData.frequency)/1e6).toFixed(6)+" MHz";color:Theme.textPrimary;font.family:Theme.mono;font.bold:true}
                        Label {text:(modelData.protocol||qsTr("Unconfirmed"))+" · "+Number(modelData.excessDb).toFixed(1)+" dB · "+modelData.lastSeen}
                        Label {text:modelData.voice?qsTr("Decoded voice activity observed"):modelData.protocol==="NFM"||modelData.protocol==="AM"?qsTr("Analog carrier observed; speech not classified"):modelData.protocol?qsTr("Digital sync observed; voice not confirmed"):qsTr("RF activity observed; protocol not confirmed")}
                        Action {text:modelData.saved?qsTr("Saved"):qsTr("Save frequency");enabled:!modelData.saved;onClicked:if(!rangeScanner.saveFrequency(Number(modelData.frequency)))screen.message=qsTr("Could not save this frequency.")}
                    }
                }
            }
        }
    }
}
