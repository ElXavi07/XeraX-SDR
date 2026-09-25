// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Controls

Flickable {
    id: viewport
    readonly property bool desktopScrolling: typeof decoderHost !== "undefined" && decoderHost.desktopBuild === true
    boundsBehavior: desktopScrolling ? Flickable.StopAtBounds : Flickable.DragAndOvershootBounds
    ScrollBar.vertical: ScrollBar {
        policy: viewport.desktopScrolling ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff
        activeFocusOnTab: false
        minimumSize: 0.08
        contentItem: Rectangle {
            implicitWidth: 6; implicitHeight: 32; radius: 3
            color: parent.pressed ? Theme.cyan : Qt.alpha(Theme.textSecondary, parent.active ? 0.6 : 0.25)
        }
    }
    property string accessibleName: qsTr("Scrollable content")
    Accessible.role: Accessible.Pane
    Accessible.name: accessibleName
    Accessible.focusable: false
    readonly property bool navigationAllowed: Navigation.allows(viewport)
    Accessible.ignored: !visible || !navigationAllowed
    function scrollPage(direction) {
        if (!enabled || !Navigation.allows(viewport))
            return;
        contentY = Math.max(0, Math.min(contentHeight - height, contentY + direction * Math.max(48, height * 0.8)));
    }
    Accessible.onScrollDownAction: scrollPage(1)
    Accessible.onScrollUpAction: scrollPage(-1)
    Accessible.onNextPageAction: scrollPage(1)
    Accessible.onPreviousPageAction: scrollPage(-1)
}
