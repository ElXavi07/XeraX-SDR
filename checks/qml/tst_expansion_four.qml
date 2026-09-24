// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtTest
import "../../upstream/dsd-neo/src/ui/qt/qml" as Ui
Item {
    id: fixture; width:390; height:900
    property var callHistory: QtObject { property int count:0; property var systemLabels:[]; property string sessionUid:""; function clearAll() {} }
    property var historyView: ListModel { property string filterText:""; property string filterSystem:""; property int filterKind:0; signal filterChanged }
    Ui.ExpansionScreen { id: expansion; anchors.fill:parent }
    Ui.CallsScreen { id: calls; anchors.fill:parent; visible:false }
    TestCase {
        name:"ExpansionFour"; when:windowShown
        function init() { failOnWarning(/.*/); fixture.width=390; appLanguage.language="en"; expansion.visible=true; calls.visible=false; expansion.page=0; Ui.Theme.fontScale=1; }
        function cleanup() { appLanguage.language="en"; Ui.Theme.resetFontScale(); }
        function test_language_switch() {
            compare(findChild(expansion,"expansionTab0").text,"Receivers");
            appLanguage.language="es";
            tryCompare(findChild(expansion,"expansionTab0"),"text","Receptores");
            compare(findChild(expansion,"startExtraOne").text,"Iniciar receptor 2");
            compare(findChild(expansion,"siteCaptureToggle").text,"Iniciar modo de cuatro canales");
        }
        function test_narrow_spanish_all_pages() {
            fixture.width=320; appLanguage.language="es"; Ui.Theme.fontScale=1.3;
            for(var p=0;p<6;p++) {
                expansion.page=p; wait(60);
                var tab=findChild(expansion,"expansionTab"+p);
                verify(tab.width>=48); verify(tab.height>=48);
                verify(tab.mapToItem(expansion,0,0).x+tab.width<=320);
                if(previewDirectory.length) grabImage(expansion).save(previewDirectory+"/expansion-es-320-"+p+".png");
            }
        }
        function test_calls_navigation_and_preview() {
            expansion.visible=false; calls.visible=true; calls.history=true; wait(30); calls.history=false;
            fixture.width=320; appLanguage.language="es"; Ui.Theme.fontScale=1.3; wait(60);
            if(previewDirectory.length) grabImage(calls).save(previewDirectory+"/calls-es-320.png");
        }
        function test_tools_guard_invalid_sources() {
            verify(receiverExpansion.startSiteCapture("451.100,451.850,451.950,452.125").length>0);
            verify(receiverExpansion.startChannel(0,NaN,"-f1","").length>0);
            verify(receiverExpansion.startChannel(0,155,"invalid","").length>0);
            verify(receiverExpansion.startSurvey(155,154,12.5,3).length>0);
            verify(receiverExpansion.startDual("").length>0);
            verify(receiverExpansion.startReceptionSample("A").length>0);
            verify(!receiverExpansion.setTwoTone(600,600,1000,1000));
        }
        function test_ras_control_updates_and_translates() {
            expansion.page=5; appLanguage.language="es";
            receiverExpansion.setRasReception(false);
            compare(findChild(expansion,"rasReception").text,"Activar recepción DMR RAS");
            receiverExpansion.setRasReception(true);
            compare(findChild(expansion,"rasReception").text,"Desactivar recepción DMR RAS");
            receiverExpansion.setRasReception(false);
        }
        function test_nxdn_search_control_and_translation() {
            expansion.page=5; receiverExpansion.setNxdnSearch(false);
            compare(findChild(expansion,"nxdnSearchToggle").text,"Start NXDN search");
            receiverExpansion.setNxdnSearch(true);
            compare(findChild(expansion,"nxdnSearchToggle").text,"Stop NXDN search");
            appLanguage.language="es";
            tryCompare(findChild(expansion,"nxdnSearchToggle"),"text","Detener búsqueda NXDN");
            receiverExpansion.setNxdnSearch(false);
        }
    }
}
