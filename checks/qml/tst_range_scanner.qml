// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtTest
import "../../upstream/dsd-neo/src/ui/qt/qml" as Ui
Item {
    id:fixture;width:390;height:900
    Ui.RangeScannerScreen {id:screen;anchors.fill:parent}
    Ui.ExploreSetupScreen {id:explore;anchors.fill:parent;visible:false}
    SignalSpy {id:rangeStarted;target:explore;signalName:"startRange"}
    SignalSpy {id:singleStarted;target:explore;signalName:"start"}
    TestCase {
        name:"RangeScanner";when:windowShown
        function init(){failOnWarning(/.*/);fixture.width=390;fixture.height=900;appLanguage.language="en";Ui.Theme.fontScale=1;
            screen.visible=true;explore.visible=false;explore.rangeMode=false;rangeScanner.stop();rangeStarted.clear();singleStarted.clear();}
        function cleanup(){appLanguage.language="en";Ui.Theme.resetFontScale();rangeScanner.stop();}
        function test_explore_range_routes_source_and_settings(){
            screen.visible=false;explore.visible=true;
            explore.reset("rtltcp","192.168.1.245",1234,"451.1","-fs");explore.rangeMode=true;
            findChild(explore,"rangeFirst").text="440.000000";findChild(explore,"rangeLast").text="460.000000";
            findChild(explore,"rangeStep").currentIndex=3;
            verify(explore.ready());compare(findChild(explore,"exploreStartButton").text,"Start range scan");
            explore.submit();compare(rangeStarted.count,1);compare(singleStarted.count,0);
            compare(rangeStarted.signalArguments[0][0],"rtltcp");compare(rangeStarted.signalArguments[0][1],"192.168.1.245");
            compare(rangeStarted.signalArguments[0][2],1234);compare(rangeStarted.signalArguments[0][3].lastMhz,"460.000000");
            compare(rangeStarted.signalArguments[0][3].stepKhz,12.5);
            explore.rangeMode=false;explore.submit();compare(singleStarted.count,1);
        }
        function test_invalid_and_reversed_range_blocks_start(){
            var first=findChild(screen,"rangeFirst"),last=findChild(screen,"rangeLast"),start=findChild(screen,"rangeStart");
            first.text="460";last.text="440";verify(!start.enabled);verify(findChild(screen,"rangeValidation").text.length>0);
            first.text="440";last.text="460";verify(start.enabled);
            first.text="bad";verify(!start.enabled);first.text="440";
            findChild(screen,"rangeThreshold").text="99";verify(!start.enabled);findChild(screen,"rangeThreshold").text="10";
            verify(start.enabled);
            first.text="440,000";last.text="450,000";verify(start.enabled);
            first.text="440";last.text="460";
        }
        function test_narrow_spanish_keyboard_layout(){
            fixture.width=320;appLanguage.language="es";Ui.Theme.fontScale=1.3;
            tryCompare(findChild(screen,"rangeStart"),"text","Iniciar escaneo de rango");
            var scroll=findChild(screen,"rangeScroll");verify(scroll.contentHeight>scroll.height);
            for(var name of ["rangeFirst","rangeLast","rangeStep","rangeMode","rangeStart"]){
                var item=findChild(screen,name);verify(item.width<=fixture.width-28);verify(item.height>=48);
            }
            scroll.contentY=0;wait(80);
            if(previewDirectory.length)grabImage(screen).save(previewDirectory+"/range-es-320-top.png");
            scroll.contentY=Math.max(0,scroll.contentHeight-scroll.height);wait(80);
            if(previewDirectory.length)grabImage(screen).save(previewDirectory+"/range-es-320-bottom.png");
        }
    }
}
