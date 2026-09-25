// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtTest
import "../../upstream/dsd-neo/src/ui/qt/qml" as Ui
Item {
    id: fixture; width: 840; height: 740
    Ui.DesktopSidebar { id: sidebar; width: 220; height: parent.height; onSelected: function(index) { currentIndex=index; } }
    Item { id: modalSurface }
    SignalSpy { id: selected; target: sidebar; signalName: "selected" }
    TestCase {
        name: "DesktopNavigation"; when: windowShown
        function init() { failOnWarning(/.*/); Ui.Navigation.rootSurfaces=[sidebar]; Ui.Navigation.layers=[]; Ui.Navigation.modals=[]; sidebar.currentIndex=0; selected.clear(); }
        function cleanup() { Ui.Navigation.rootSurfaces=[]; Ui.Navigation.layers=[]; Ui.Navigation.modals=[]; }
        function test_mouse_and_keyboard_routes() {
            var scan=findChild(sidebar,"desktopNav1"); mouseClick(scan,70,20); compare(sidebar.currentIndex,3);
            var calls=findChild(sidebar,"desktopNav2"); calls.forceActiveFocus(); keyClick(Qt.Key_Return); compare(sidebar.currentIndex,1);
            var tools=findChild(sidebar,"desktopNav3"); tools.forceActiveFocus(); keyClick(Qt.Key_Space); compare(sidebar.currentIndex,2); compare(selected.count,3);
        }
        function test_modal_blocks_background_navigation() {
            Ui.Navigation.rootSurfaces=[modalSurface];
            findChild(sidebar,"desktopNav1").choose(); compare(selected.count,0); compare(sidebar.currentIndex,0);
        }
    }
}
