// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Controls
import QtQuick.Window

Item {
    id: screen
    signal closed
    property int tab: 0
    property int selectedCapture: -1
    function revealInput() { if (screen.Window.window) Theme.revealFocus(scroll, body, screen.Window.window.activeFocusItem); }
    onVisibleChanged: {
        if (visible) aiReceiver.refreshLocal();
        else { apiKey.text = ""; experiments.checked = false; }
    }
    NavigationLayer { active: screen.visible; surface: screen; onLeave: screen.closed() }
    Connections { target: screen.Window.window; function onActiveFocusItemChanged() { Qt.callLater(screen.revealInput); } }
    component Label: Text {
        width: parent.width; textFormat: Text.PlainText; wrapMode: Text.Wrap
        color: Theme.textSecondary; font.family: Theme.sans; font.pixelSize: Theme.fontSize(14)
    }
    component Heading: Label { color: Theme.textPrimary; font.pixelSize: Theme.fontSize(18); font.bold: true }
    component Action: OutlineButton { width: parent.width }
    component Card: Rectangle {
        default property alias contents: column.data
        width: parent.width; height: column.height + 28; radius: 14; color: Theme.panel; border.color: Theme.panelBorder
        Column { id: column; x: 14; y: 14; width: parent.width - 28; spacing: 12 }
    }
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Row {
        id: header; x: 14; y: 12; width: parent.width - 28; spacing: 10
        IconButton { icon: "back"; onClicked: screen.closed() }
        Label { width: parent.width - 58; text: qsTr("AI receiver"); color: Theme.textPrimary; font.pixelSize: Theme.fontSize(23); font.bold: true }
    }
    Row {
        id: tabs; x: 14; width: parent.width - 28; anchors.top: header.bottom; anchors.topMargin: 12; spacing: 8
        OutlineButton { width: (parent.width - 8) / 2; text: qsTr("Connect"); textColor: screen.tab === 0 ? Theme.cyan : Theme.textSecondary; onClicked: { screen.tab=0; scroll.contentY=0; } }
        OutlineButton { width: (parent.width - 8) / 2; text: qsTr("Investigate"); textColor: screen.tab === 1 ? Theme.cyan : Theme.textSecondary; onClicked: { screen.tab=1; scroll.contentY=0; } }
    }
    PlexFlickable {
        id: scroll; objectName: "aiScroll"
        x: 14; width: parent.width - 28; anchors.top: tabs.bottom; anchors.topMargin: 12; anchors.bottom: parent.bottom
        anchors.bottomMargin: Math.max(0, screen.height - Theme.keyboardTop(screen)); clip: true; contentHeight: body.height+24
        onHeightChanged: Qt.callLater(screen.revealInput)
        Column {
            id: body; width: scroll.width; spacing: 12
            Card {
                PlexToggle { objectName: "aiEnable"; width: parent.width; text: qsTr("Enable optional AI"); checked: aiReceiver.enabled; onToggled: aiReceiver.enabled=checked }
                Label { text: qsTr("Radio decoding and experiments run on this phone. AI uses the selected provider over the internet and may incur API charges.") }
                Label { text: qsTr("Starting an investigation sends your question, frequency and receiver measurements. Audio, I/Q recordings, radio keys, GPS and account details are not uploaded.") }
            }
            Label { objectName: "aiStatus"; text: { var lang=appLanguage.language; return appLanguage.text(aiReceiver.status); } color: Theme.cyan }
            Action { objectName: "aiCancel"; text: qsTr("Stop AI run"); visible: aiReceiver.busy; onClicked: aiReceiver.cancel() }
            Column {
                width: parent.width; spacing: 12; visible: screen.tab === 0
                Card {
                    Heading { text: qsTr("Provider and model") }
                    PlexComboBox {
                        objectName: "aiProvider"; width: parent.width; model: ["OpenAI", "DeepSeek"]
                        currentIndex: aiReceiver.provider === "openai" ? 0 : 1
                        enabled: aiReceiver.enabled && !aiReceiver.busy
                        onActivated: { apiKey.text=""; aiReceiver.provider=currentIndex === 0 ? "openai" : "deepseek"; }
                    }
                    PlexInput {
                        id: apiKey; objectName: "aiKey"; width: parent.width; placeholderText: qsTr("Your provider API key")
                        echoMode: TextInput.Password; inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText | Qt.ImhNoAutoUppercase
                        maximumLength: 4096; enabled: aiReceiver.enabled && !aiReceiver.busy
                    }
                    Action { objectName: "aiConnect"; text: qsTr("Connect and load models"); enabled: aiReceiver.enabled && !aiReceiver.busy && apiKey.text.trim().length>0
                        onClicked: { aiReceiver.connectKey(apiKey.text); apiKey.text=""; Qt.inputMethod.hide(); } }
                    Label { text: aiReceiver.hasKey ? qsTr("A key is available for this provider. Saved keys use Android Keystore encryption.") : qsTr("Each user supplies their own API key. RadioReference keys cannot be used here.") }
                    Action { text: qsTr("Refresh available models"); enabled: aiReceiver.enabled && aiReceiver.hasKey && !aiReceiver.busy; onClicked: aiReceiver.refreshModels() }
                    PlexComboBox {
                        id: models; objectName: "aiModel"; width: parent.width; model: aiReceiver.models
                        currentIndex: aiReceiver.models.indexOf(aiReceiver.model)
                        displayText: currentIndex<0 ? qsTr("Select a model") : currentText
                        enabled: aiReceiver.enabled && !aiReceiver.busy && count>0
                        onActivated: aiReceiver.model=currentText
                    }
                    Label { text: qsTr("Models come directly from your provider. Some models do not support receiver tools; check the selected model before use.") }
                    Action { objectName: "aiCheck"; text: qsTr("Check model (uses API)"); enabled: aiReceiver.enabled && !aiReceiver.busy && models.currentIndex>=0; onClicked: aiReceiver.checkModel() }
                    Action { text: qsTr("Forget this provider key"); enabled: aiReceiver.hasKey && !aiReceiver.busy; onClicked: { apiKey.text=""; aiReceiver.forgetKey(); } }
                }
                Card {
                    Heading { text: qsTr("Usage controls") }
                    Label { text: qsTr("Requests today: %1 · reported tokens: %2").arg(aiReceiver.requestsToday).arg(aiReceiver.tokensToday) }
                    Label { text: qsTr("Daily request limit") }
                    SpinBox { objectName: "aiLimit"; width: parent.width; from: 1; to: 200; value: aiReceiver.dailyLimit; onValueModified: aiReceiver.dailyLimit=value }
                    Label { text: qsTr("One investigation uses up to five API requests. Model checks count too. This limit is per phone and is not a currency budget. Provider billing is separate.") }
                }
            }
            Column {
                width: parent.width; spacing: 12; visible: screen.tab === 1
                Card {
                    Heading { text: qsTr("Investigate reception") }
                    Label { text: qsTr("The AI can inspect diagnostics, measure a fixed channel, run a gain comparison and compare a selected saved I/Q capture. New RF neural models are not included.") }
                    TextArea {
                        id: question; objectName: "aiQuestion"; width: parent.width; wrapMode: TextEdit.Wrap; selectByMouse: true
                        text: qsTr("Investigate reception using the available measurements. Try the permitted local tools and explain what improved or what remains uncertain.")
                        color: Theme.textPrimary; font.family: Theme.sans; font.pixelSize: Theme.fontSize(15)
                        background: Rectangle { color: Theme.bg; radius: 8; border.color: Theme.panelBorder }
                    }
                    PlexToggle { id: experiments; objectName: "aiExperiments"; width: parent.width; text: qsTr("Allow local experiments for this run"); enabled: !aiReceiver.busy }
                    Label { text: qsTr("Experiments may change gain or use a spare decoder worker. Worse gain results restore the original. Active calls, scanning, thermal limits and other workers can prevent a trial.") }
                    PlexComboBox {
                        id: capture; objectName: "aiCapture"; width: parent.width; enabled: !aiReceiver.busy
                        model: [qsTr("No capture selected")].concat(aiReceiver.captures.map(function(c) { return c.label; }))
                        currentIndex: screen.selectedCapture+1
                        onActivated: screen.selectedCapture=currentIndex-1
                    }
                    Label { text: qsTr("Saved captures are listed in the same order as Receiver tools → Clips. Only the selected capture can be tested; its samples stay on the phone.") }
                    Action { objectName: "aiAsk"; text: qsTr("Start investigation"); enabled: aiReceiver.enabled && aiReceiver.verified && !aiReceiver.busy && question.text.trim().length>0 && question.text.length<=2000
                        onClicked: { aiReceiver.ask(question.text,experiments.checked,screen.selectedCapture); Qt.inputMethod.hide(); } }
                }
                Card {
                    visible: aiReceiver.events.length>0 || aiReceiver.answer.length>0
                    Heading { text: qsTr("Evidence and result") }
                    Repeater { model: aiReceiver.events; Label { required property string modelData; text: "• " + modelData } }
                    Label { objectName: "aiAnswer"; text: aiReceiver.answer; color: Theme.textPrimary; visible: text.length>0 }
                    Label { text: qsTr("AI conclusions can be wrong. Compare them with the measured results; improvement is not guaranteed.") }
                    Action { text: qsTr("Clear conversation"); enabled: !aiReceiver.busy; onClicked: aiReceiver.clearConversation() }
                }
            }
        }
    }
}
