// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick

Item {
    id: page
    signal closed
    property int countyId: 215
    property var selected: ({})
    property string query: ""
    property string notice: ""
    property string categoryName: ""
    property bool nearby: true
    readonly property var modeIds: ["", "nfm", "p25", "dmr", "nxdn48", "nxdn", "am", "wfm"]
    readonly property var frequencies: radioReference.conventionalFrequencies || []
    component Label: Text {
        width: parent.width; wrapMode: Text.Wrap; textFormat: Text.PlainText
        font.family: Theme.sans; font.pixelSize: Theme.fontSize(14); color: Theme.textPrimary
    }
    function reload() { selected = {}; radioReference.loadConventional(0, countyId); }
    function visibleFrequency(row) {
        return (row.name + " " + row.description + " " + row.tags + " " + row.modeName + " " + row.freqMhz).toLowerCase().indexOf(query.toLowerCase()) >= 0;
    }
    function saveChannels() {
        var count = 0;
        for (var i=0; i<frequencies.length; i++) {
            if (!selected[i]) continue;
            var r=frequencies[i], mode=modeIds[overrideMode.currentIndex] || r.protocol;
            var flags={nfm:"-fA", am:"-fU", wfm:"-fW", p25:"-ft",dmr:"-fs",nxdn48:"-fi",nxdn:"-fn"};
            if (!flags[mode]) { notice=qsTr("Choose a receive mode before saving unknown modes."); return; }
        }
        for (var j=0; j<frequencies.length; j++) {
            if (!selected[j]) continue;
            var channel=frequencies[j], receive=modeIds[overrideMode.currentIndex] || channel.protocol;
            if (!savedSystems.add({name:channel.name || channel.description, sourceType:source.currentIndex===1?"airspy":"usb",
                freqMhz:channel.freqMhz,decodeFlag:flags[receive],trunking:false,gainDb:-1})) {
                notice=qsTr("Saved %1 channels before a storage error.").arg(count); return;
            }
            count++;
        }
        notice=qsTr("Saved %1 individual channels. AM and WFM use standalone reception.").arg(count);
    }
    function importList() {
        var entries = [], seen = {};
        for (var i = 0; i < frequencies.length; i++) {
            if (!selected[i]) continue;
            var r = frequencies[i], mode = modeIds[overrideMode.currentIndex] || r.protocol;
            if (!mode) { notice = qsTr("Choose a receive mode for channels whose bandwidth or mode is unspecified."); return; }
            if (!r.freqMhz || Number(r.freqMhz) <= 0) continue;
            var key = mode + ":" + r.freqMhz;
            if (seen[key]) continue;
            seen[key] = true;
            entries.push({uid: scanLists.newEntryId(), kind: "freq", protocol: mode, freqMhz: r.freqMhz,
                name: r.name || r.description, enabled: true, dwellMs: 0, holdMs: 0, gainDb: -1});
        }
        if (!entries.length) { notice = qsTr("Select at least one frequency."); return; }
        var list = scanLists.newDraft();
        list.name = listName.text.trim() || categoryName || qsTr("Riverside conventional");
        list.sourceType = source.currentIndex === 1 ? "airspy" : "usb";
        list.entries = entries; list.isDraft = false;
        var check = scanListStarter.validate(list);
        if (!check.ok) { notice = check.error; return; }
        notice = scanLists.add(list) ? qsTr("Saved %1 unique channels to a scan list. Open it from Home to listen.").arg(entries.length) : qsTr("Could not save the scan list.");
    }
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Row {
        id: header; x: 18; y: 12; height: 46; spacing: 12
        IconButton { icon: "back"; onClicked: page.closed() }
        Label { width: page.width - 95; text: qsTr("Conventional channels"); font.pixelSize: Theme.fontSize(21) }
    }
    PlexFlickable {
        anchors.top: header.bottom; anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        clip: true; contentHeight: content.height + 32
        Column {
            id: content; x: 18; width: parent.width - 36; spacing: 10
            Label { text: qsTr("Browse county services and agencies, then open a category. The 50-mile filter uses category coverage centers around Indio; unknown locations remain available.") }
            Label { text: radioReference.errorText || (radioReference.busy ? radioReference.statusText : page.notice); color: Theme.cyan }
            Flow {
                width: parent.width; spacing: 6
                OutlineButton { text: qsTr("Riverside County"); enabled: !radioReference.busy; onClicked: { page.countyId = 215; page.reload(); } }
                OutlineButton { text: qsTr("Selected county"); enabled: !radioReference.busy; onClicked: page.reload() }
                OutlineButton { text: qsTr("Cancel download"); visible: radioReference.busy; onClicked: radioReference.cancel() }
            }
            PlexInput { width: parent.width; placeholderText: qsTr("Filter service, agency, name, mode or frequency"); onTextChanged: page.query = text }
            PlexCheckBox { width: parent.width; text: qsTr("Within 50 mi of Indio, including unknown locations"); checked: page.nearby; onToggled: page.nearby = checked }
            Repeater {
                model: radioReference.conventionalAgencies || []
                delegate: OutlineButton {
                    required property var modelData
                    width: content.width; text: modelData.name
                    visible: modelData.name.toLowerCase().indexOf(page.query.toLowerCase()) >= 0
                    enabled: !radioReference.busy
                    onClicked: { page.selected = {}; page.categoryName = modelData.name; radioReference.loadConventional(1, modelData.id); }
                }
            }
            Repeater {
                model: radioReference.conventionalCategories || []
                delegate: OutlineButton {
                    required property var modelData
                    width: content.width
                    text: modelData.name + (modelData.distanceMi >= 0 ? " · " + modelData.distanceMi.toFixed(1) + " mi" : qsTr(" · location unknown"))
                    visible: (!page.nearby || modelData.distanceMi < 0 || modelData.distanceMi <= 50)
                        && modelData.name.toLowerCase().indexOf(page.query.toLowerCase()) >= 0
                    enabled: !radioReference.busy
                    onClicked: { page.selected = {}; page.categoryName = modelData.name; radioReference.loadConventional(2, modelData.id); }
                }
            }
            Label { visible: page.frequencies.length > 0; text: qsTr("%1 frequency records · %2").arg(page.frequencies.length).arg(page.categoryName); font.bold: true }
            Flow {
                visible: page.frequencies.length > 0; width: parent.width; spacing: 6
                OutlineButton { text: qsTr("Select visible unencrypted"); onClicked: {
                    var next = {}; for (var i = 0; i < page.frequencies.length; i++)
                        if (page.visibleFrequency(page.frequencies[i]) && page.frequencies[i].encrypted === 0) next[i] = true;
                    page.selected = next;
                } }
                OutlineButton { text: qsTr("Clear selection"); onClicked: page.selected = ({}) }
            }
            Repeater {
                model: page.frequencies
                delegate: Column {
                    required property var modelData; required property int index
                    width: content.width; visible: page.visibleFrequency(modelData)
                    PlexCheckBox {
                        width: parent.width; text: modelData.freqMhz + " MHz · " + (modelData.name || modelData.description)
                        checked: !!page.selected[index]
                        onToggled: { var copy = Object.assign({}, page.selected); copy[index] = checked; page.selected = copy; }
                    }
                    Label { text: modelData.modeName + " · " + modelData.description + " · " + modelData.tags
                        + (modelData.tone ? " · Tone " + modelData.tone : "")
                        + (modelData.colorCode ? " · CC " + modelData.colorCode : "")
                        + (modelData.encrypted ? qsTr(" · encryption listed") : "") }
                }
            }
            Column {
                visible: page.frequencies.length > 0; width: parent.width; spacing: 10
                Label { text: qsTr("Database tone, color code and talkgroup information is shown for reference. The decoder reads digital identifiers from the received signal. Generic NXDN records need a bandwidth choice.") }
                PlexComboBox { id: overrideMode; width: parent.width; model: [qsTr("Use database receive mode"), "Analog NFM", "P25", "DMR", "NXDN48", "NXDN96", "AM", "WFM"] }
                PlexInput { id: listName; width: parent.width; placeholderText: qsTr("New scan-list name") }
                PlexComboBox { id: source; width: parent.width; model: [qsTr("USB RTL-SDR / HackRF"), "Airspy USB"] }
                OutlineButton { width: parent.width; text: qsTr("Save selection as individual channels"); enabled: !radioReference.busy; onClicked: page.saveChannels() }
                OutlineButton { width: parent.width; text: qsTr("Create scan list from selection"); enabled: !radioReference.busy; onClicked: page.importList() }
            }
        }
    }
}
