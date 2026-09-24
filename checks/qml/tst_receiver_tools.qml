// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtTest
import "../../upstream/dsd-neo/src/ui/qt/qml" as Ui
Item {
    width:390;height:900
    Ui.ReceiverToolsScreen { id: tools; anchors.fill:parent }
    Ui.ConventionalBrowser { id: browser; anchors.fill:parent; visible:false }
    TestCase {
        name:"XeraXReceiverExpansion";when:windowShown
        function init() { failOnWarning(/.*/); commands.reset(); radioReference.reset(); tools.visible=true; browser.visible=false; }
        function test_tools_small_screen() {
            wait(50);verify(tools.width===390);compare(tools.page,0);
            if(previewDirectory.length) grabImage(tools).save(previewDirectory+"/receiver-tools.png");
        }
        function test_conventional_analog_import() {
            tools.visible=false;browser.visible=true;
            radioReference.conventionalFrequencies=[{id:1,name:"Synthetic NFM",description:"Test fixture",modeName:"FMN",protocol:"nfm",freqMhz:"155.250000",tone:"100.0",colorCode:"",tags:"Test",encrypted:0}];
            browser.selected={0:true};var before=scanLists.count;browser.importList();
            compare(scanLists.count,before+1);compare(scanLists.get(before).entries[0].protocol,"nfm");
            if(previewDirectory.length) grabImage(browser).save(previewDirectory+"/conventional-browser.png");
        }
        function test_conventional_unknown_needs_mode() {
            tools.visible=false;browser.visible=true;
            radioReference.conventionalFrequencies=[{id:2,name:"Unknown",description:"",modeName:"NXDN",protocol:"",freqMhz:"450.000000",tone:"",colorCode:"",tags:"",encrypted:0}];
            browser.selected={0:true};var before=scanLists.count;browser.importList();compare(scanLists.count,before);verify(browser.notice.length>0);
        }
    }
}
