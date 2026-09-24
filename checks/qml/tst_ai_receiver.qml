// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtTest
import "../../upstream/dsd-neo/src/ui/qt/qml" as Ui
Item {
    id: fixture; width:390; height:900
    Ui.AiReceiverScreen { id: screen; anchors.fill:parent }
    TestCase {
        name:"AiReceiver"; when:windowShown
        function init() { failOnWarning(/.*/); fixture.width=390; appLanguage.language="en"; Ui.Theme.fontScale=1; screen.tab=0; aiReceiver.enabled=false; aiReceiver.clearConversation(); }
        function cleanup() { appLanguage.language="en"; Ui.Theme.resetFontScale(); aiReceiver.enabled=false; }
        function test_optional_off_and_no_model() {
            verify(!findChild(screen,"aiEnable").checked);
            verify(!findChild(screen,"aiConnect").enabled);
            verify(!findChild(screen,"aiCheck").enabled);
            screen.tab=1; verify(!findChild(screen,"aiAsk").enabled);
            verify(!findChild(screen,"aiExperiments").checked);
        }
        function test_key_input_is_masked() {
            var input=findChild(screen,"aiKey"); compare(input.echoMode,TextInput.Password);
            aiReceiver.enabled=true; input.text="not-a-real-provider-key";
            verify(findChild(screen,"aiConnect").enabled); input.text="";
        }
        function test_narrow_spanish_layout() {
            fixture.width=320; appLanguage.language="es"; Ui.Theme.fontScale=1.3;
            tryCompare(findChild(screen,"aiEnable"),"text","Activar IA opcional");
            for(var p=0;p<2;p++) {
                screen.tab=p; var scroll=findChild(screen,"aiScroll"); scroll.contentY=0; wait(80);
                verify(scroll.contentHeight>scroll.height);
                var positions=[0,Math.max(0,scroll.contentHeight-scroll.height)];
                for(var k=0;k<positions.length;k++) {
                    scroll.contentY=positions[k]; wait(40);
                    if(previewDirectory.length) grabImage(screen).save(previewDirectory+"/ai-es-320-"+p+"-"+k+".png");
                }
            }
            verify(findChild(screen,"aiAsk").width>=48); verify(findChild(screen,"aiAsk").height>=48);
        }
    }
}
