// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtTest
import "../../upstream/dsd-neo/src/ui/qt/qml" as Ui

Item {
    id: root
    width: 390
    height: 900
    Ui.RadioReferenceScreen { id: screen; anchors.fill: parent }
    TestCase {
        name: "XeraXRadioReference"
        when: windowShown
        function init() {
            failOnWarning(/.*/);
            radioReference.reset();
            screen.reset();
            root.width = 390;
        }
        function sites(distances) {
            return distances.map(function(distance, i) {
                return {descr: "Test site " + i, siteNumber: i + 1, indioDistanceMi: distance,
                    freqCount: 1, controlFreqMhz: "852.5", freqMhz: "852.5", colorCode: "",
                    simulcast: false};
            });
        }
        function test_keyed_login_and_county_shortcut() {
            compare(screen.offersAppKey, false);
            var button = findChild(screen, "radioReferenceRiverside");
            verify(button.visible);
            button.activate();
            compare(radioReference.countyRequest, 215);
            compare(radioReference.requestCount, 1);
            compare(screen.browseStid, 6);
            compare(screen.browseCountyName, "Riverside County");
            compare(screen.showIndioDistances, true);
            radioReference.busy = true;
            screen.findRiverside();
            compare(radioReference.requestCount, 1);
            radioReference.busy = false;
            radioReference.credentialsReady = false;
            screen.findRiverside();
            compare(radioReference.requestCount, 1);
        }
        function test_radius_bounds_unknowns_and_original_indexes() {
            radioReference.sites = sites([0, 49.9999, 50, 50.0001, -1, undefined, NaN, Infinity, "1"]);
            screen.siteSearch = "unrelated filter";
            screen.selectedSites = [3];
            screen.selectIndioSites();
            compare(screen.eachSite, true);
            compare(JSON.stringify(screen.selectedSites), "[0,1,2]");
            compare(screen.siteSearch, "");
            verify(screen.notice.indexOf("5 without usable coordinates") >= 0);
            // Manual correction stays possible; no permanent geographic filter.
            screen.toggleSite(3);
            compare(JSON.stringify(screen.selectedSites), "[0,1,2,3]");
            radioReference.busy = true;
            screen.selectIndioSites();
            compare(JSON.stringify(screen.selectedSites), "[0,1,2,3]");
        }
        function test_conventional_and_empty_selection() {
            radioReference.trunked = false;
            radioReference.conventional = true;
            radioReference.sites = sites([51, -1]);
            screen.selectIndioSites();
            compare(screen.selectedSites.length, 0);
            compare(screen.eachSite, false);
            radioReference.sites = sites([5, 60, 10]);
            screen.selectIndioSites();
            compare(JSON.stringify(screen.selectedSites), "[0,2]");
            radioReference.conventional = false;
            screen.selectedSites = [1];
            screen.selectIndioSites();
            compare(JSON.stringify(screen.selectedSites), "[1]");
        }
        function test_compact_layout() {
            [320, 390, 480].forEach(function(width) {
                root.width = width;
                var button = findChild(screen, "radioReferenceRiverside");
                verify(button.width <= width && button.width > 200);
                verify(button.height >= 48);
            });
            root.width = 390;
            if (previewDirectory.length)
                grabImage(root).save(previewDirectory + "/preview-radioreference.png");
            radioReference.systemDetails = {sid: 1234, name: "Test system", typeDescr: "Project 25", flavorDescr: "Phase II"};
            radioReference.sites = sites([5.7, 34.0, 65.0, -1]);
            screen.selectIndioSites();
            wait(30);
            if (previewDirectory.length)
                grabImage(root).save(previewDirectory + "/preview-radioreference-sites.png");
        }
    }
}
