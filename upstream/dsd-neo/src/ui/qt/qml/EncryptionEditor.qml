// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick

// Shared draft editor. QString/QML copies cannot promise secure erasure.
// Only the TextInput holds/displays key material; labels contain shapes only.
Column {
    id: editor
    property string protocol: "mixed"
    readonly property var allowedTypes: protocol === "m17" ? ["", "m17Scrambler", "m17Aes"] : protocol === "dpmr" ? ["", "scrambler"] : protocol === "dstar" || protocol === "ysf" ? [""] : protocol === "p25" ? ["", "hex", "rc4"] : protocol === "dmr" ? ["", "basic", "hex", "rc4"] : protocol === "nxdn" ? ["", "hex", "rc4", "scrambler"] : ["", "basic", "hex", "rc4", "scrambler", "m17Scrambler", "m17Aes"]
    readonly property bool privacySupported: protocol === "dmr" || protocol === "nxdn" || protocol === "mixed"
    readonly property bool fallbackSupported: protocol === "dmr" || protocol === "mixed"
    readonly property string capabilityError: allowedTypes.indexOf(keyType) < 0 ? qsTr("Choose a key format supported by this protocol, or keep this draft and return to its previous decode mode.") : protocol === "p25" && keyType === "hex" && normalizedKey.length === 10 ? qsTr("P25 AES needs 32 or 64 hex digits.") : protocol === "nxdn" && keyType === "hex" && normalizedKey.length > 0 && normalizedKey.length !== 64 ? qsTr("NXDN AES needs 64 hex digits.") : ""
    readonly property string normalizedKey: keyValue.replace(/\s/g, "").replace(/^0x/i, "")
    property string keyType: ""
    property alias keyValue: keyField.text
    property int forceMode: 0
    property bool liveMode: false
    property bool forceChanged: false
    property bool resetting: false
    property string currentForceSummary: ""
    onForceModeChanged: {
        if (liveMode && !resetting)
            forceChanged = true;
    }
    property string csvPath: ""
    property bool revealed: false
    property string configuredKeyType: ""
    property bool keyConfigured: false
    property string keyAction: "keep"
    readonly property bool keepingKey: keyConfigured && keyAction === "keep"
    readonly property bool clearingKey: keyConfigured && keyAction === "clear"
    readonly property string errorText: !keepingKey && !clearingKey && capabilityError.length ? capabilityError : keepingKey ? (csvPath.length > 0 ? qsTr("Choose either a direct key or a key CSV.") : sessionArgs.keyError("", "", "", liveMode && !forceChanged ? 0 : forceMode)) : sessionArgs.keyError(clearingKey ? "" : keyType, clearingKey ? "" : keyValue, csvPath, liveMode && !forceChanged ? 0 : forceMode)
    readonly property bool valid: errorText.length === 0
    spacing: 10

    function reset() {
        resetting = true;
        keyConfigured = false;
        configuredKeyType = "";
        keyAction = "keep";
        keyType = "";
        keyValue = "";
        forceMode = 0;
        revealed = false;
        forceChanged = false;
        resetting = false;
    }
    onKeyTypeChanged: revealed = false
    onKeyActionChanged: {
        if (keyConfigured && keyAction === "keep")
            keyType = configuredKeyType;
        keyValue = "";
        revealed = false;
    }

    MicroLabel {
        text: qsTr("Privacy / encryption key")
    }
    MicroLabel {
        objectName: "configuredKeyLabel"
        visible: editor.keyConfigured
        text: qsTr("Key configured")
    }
    Row {
        width: parent.width
        spacing: 8
        visible: editor.keyConfigured
        Repeater {
            model: [
                {
                    action: "keep",
                    label: qsTr("Keep")
                },
                {
                    action: "replace",
                    label: qsTr("Replace")
                },
                {
                    action: "clear",
                    label: qsTr("Clear")
                }
            ]
            OutlineButton {
                required property var modelData
                objectName: "encryptionAction_" + modelData.action
                width: (editor.width - 16) / 3
                text: modelData.label
                border.color: editor.keyAction === modelData.action ? Theme.cyan : Theme.controlBorder
                onClicked: editor.keyAction = modelData.action
            }
        }
    }
    Flow {
        visible: !editor.keyConfigured || editor.keyAction === "replace"
        width: parent.width
        spacing: 8
        Repeater {
            model: [
                {
                    kind: "",
                    label: editor.liveMode ? qsTr("Keep current material") : qsTr("None")
                },
                {
                    kind: "basic",
                    label: qsTr("Basic · 0–255")
                },
                {
                    kind: "hex",
                    label: qsTr("Hex / AES")
                },
                {
                    kind: "rc4",
                    label: editor.protocol === "p25" || editor.protocol === "nxdn" ? qsTr("RC4 / DES") : qsTr("Enhanced · RC4")
                },
                {
                    kind: "scrambler",
                    label: qsTr("Scrambler · 0–32767")
                },
                {
                    kind: "m17Scrambler",
                    label: qsTr("M17 scrambler")
                },
                {
                    kind: "m17Aes",
                    label: qsTr("M17 AES")
                }
            ].filter(function (type) {
                return editor.allowedTypes.indexOf(type.kind) >= 0;
            })
            OutlineButton {
                required property var modelData
                width: Math.min(editor.width, implicitWidth)
                text: modelData.label
                border.color: editor.keyType === modelData.kind ? Theme.cyan : Theme.controlBorder
                onClicked: {
                    editor.keyType = modelData.kind;
                    editor.keyValue = "";
                }
            }
        }
    }
    Row {
        width: parent.width
        spacing: 8
        visible: editor.keyType.length > 0 && !editor.keepingKey && !editor.clearingKey
        PlexTextField {
            id: keyField
            objectName: "encryptionKeyField"
            width: parent.width - eye.width - parent.spacing
            mono: true
            placeholderText: editor.keyType === "basic" ? qsTr("0–255 (decimal)") : editor.keyType === "scrambler" ? qsTr("0–32767 (decimal)") : qsTr("Key (hexadecimal)")
            input.echoMode: editor.revealed ? TextInput.Normal : TextInput.Password
            inputMethodHints: Qt.ImhHiddenText | Qt.ImhSensitiveData | Qt.ImhNoPredictiveText | ((editor.keyType === "basic" || editor.keyType === "scrambler") ? Qt.ImhDigitsOnly : Qt.ImhNone)
        }
        OutlineButton {
            id: eye
            objectName: "encryptionKeyEye"
            width: 82
            // Eye affordance plus a readable label; avoids relying on emoji fonts.
            Canvas {
                x: 5
                anchors.verticalCenter: parent.verticalCenter
                width: 14
                height: 10
                onPaint: {
                    var ctx = getContext("2d");
                    ctx.reset();
                    ctx.strokeStyle = Theme.textSecondary;
                    ctx.lineWidth = 1;
                    ctx.beginPath();
                    ctx.moveTo(0, 5);
                    ctx.quadraticCurveTo(7, -3, 14, 5);
                    ctx.quadraticCurveTo(7, 13, 0, 5);
                    ctx.stroke();
                    ctx.beginPath();
                    ctx.arc(7, 5, 2, 0, 2 * Math.PI);
                    ctx.stroke();
                }
            }
            text: editor.revealed ? qsTr("Hide") : qsTr("Show")
            onClicked: editor.revealed = !editor.revealed
        }
    }
    Text {
        objectName: "encryptionValidity"
        width: parent.width
        visible: text.length > 0
        text: editor.errorText
        wrapMode: Text.Wrap
        font.family: Theme.sans
        font.pixelSize: Theme.fontSize(13)
        color: Theme.textSecondary
    }
    Text {
        width: parent.width
        text: editor.keyType === "basic" ? qsTr("Enter the configured basic-privacy value. This is separate from the DMR color code (0–15).") : editor.keyType === "scrambler" ? qsTr("Enter the configured NXDN scrambler value. Radio programming commonly uses 1–32767; this decoder also accepts 0.") : editor.keyType === "rc4" ? qsTr("Enter the actual key in hex. DMR enhanced privacy commonly uses a 40-bit key (10 hex digits); a key ID or color code is not the key.") : editor.keyType === "hex" ? qsTr("Enter the configured manufacturer-specific privacy or AES key. Key formats depend on the selected protocol.") : qsTr("Clear voice needs no key. Encrypted voice needs the matching key; this app does not discover unknown keys.")
        wrapMode: Text.Wrap
        font.family: Theme.sans
        font.pixelSize: Theme.fontSize(13)
        color: Theme.textSecondary
    }
    ToggleRow {
        objectName: "forceKeyToggle"
        visible: editor.liveMode || editor.privacySupported || editor.forceMode !== 0
        title: editor.liveMode ? qsTr("Change identifier policy") : qsTr("Force key")
        subtitle: editor.liveMode && !editor.forceChanged ? qsTr("Keeping %1").arg(editor.currentForceSummary) : qsTr("Override signaled privacy identifiers")
        checked: editor.liveMode ? editor.forceChanged : editor.forceMode !== 0
        onToggled: function (on) {
            if (editor.liveMode) {
                editor.forceChanged = on;
                return;
            }
            editor.forceMode = on ? (editor.keyType === "rc4" && editor.fallbackSupported ? 2 : editor.privacySupported ? 1 : 0) : 0;
        }
    }
    Row {
        width: parent.width
        spacing: 8
        visible: editor.liveMode ? editor.forceChanged : editor.forceMode !== 0
        OutlineButton {
            visible: editor.liveMode
            width: (parent.width - 16) / 3
            text: qsTr("Normal")
            border.color: editor.forceMode === 0 ? Theme.cyan : Theme.controlBorder
            onClicked: editor.forceMode = 0
        }
        OutlineButton {
            width: editor.liveMode ? (parent.width - 16) / 3 : (parent.width - 8) / 2
            visible: editor.privacySupported
            text: qsTr("Privacy")
            border.color: editor.forceMode === 1 ? Theme.cyan : Theme.controlBorder
            onClicked: editor.forceMode = 1
        }
        OutlineButton {
            width: editor.liveMode ? (parent.width - 16) / 3 : (parent.width - 8) / 2
            visible: editor.fallbackSupported
            text: qsTr("RC4")
            border.color: editor.forceMode === 2 ? Theme.cyan : Theme.controlBorder
            onClicked: editor.forceMode = 2
        }
    }
}
