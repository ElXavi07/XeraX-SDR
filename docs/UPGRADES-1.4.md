# XeraX SDR 1.4.0: RadioReference and Indio site selection

The supplied APK includes the approved XeraX RadioReference application key. The app no longer asks you to paste a key. Install it over 1.3.0 to retain saved systems and preferences; do not uninstall first.

## Sign in and import

1. Open Home, add a system, and choose **RadioReference**.
2. Enter your RadioReference username and password inside the app, then tap **Check account**. Your account needs an active Premium subscription. Browser sign-in does not sign the Android app in.
3. Tap **Indio / Coachella Valley · Riverside County**. This loads the county's system list, not an automatic radius search of every frequency.
4. Open a supported system and tap **Select sites within 50 mi of Indio**. For trunked systems this enables a separate saved system per selected site.
5. Review the selected sites, listening policy and import preview, then import. Choose your RTL-SDR source and finish saving in the setup wizard.
6. Start a saved site from Home, or add saved systems to a scan list. The app's audio-output picker remains available for the phone speaker or other outputs.

The password is kept only for the current app session. Username persists. A build with an included application key ignores any old stored key override.

## Local systems to try

Use the system-ID search if a system is not in the county result list. Each system is fetched when requested; this update does not automatically download the whole county or install the earlier CSV pack.

| System | RadioReference ID |
|---|---:|
| [Coachella Valley Water District](https://www.radioreference.com/db/sid/7813) | 7813 |
| [Imperial Irrigation District](https://www.radioreference.com/db/sid/10727) | 10727 |
| [Desert Sands Unified School District](https://www.radioreference.com/db/sid/13121) | 13121 |
| [Palm Springs Unified School District](https://www.radioreference.com/db/sid/13122) | 13122 |
| [Agua Caliente, Palm Springs](https://www.radioreference.com/db/sid/12338) | 12338 |
| [Agua Caliente, Rancho Mirage](https://www.radioreference.com/db/sid/12603) | 12603 |
| [Riverside PSEC](https://www.radioreference.com/db/sid/7001) | 7001 |

Choose systems you want to receive and are within your antenna's reception. PSEC contains encrypted local police/sheriff talkgroups; database access does not provide their audio or encryption keys.

## Meaning of the 50-mile selection

- Center: approximate central Indio, 33.7206, -116.2156. This is not a stored home address or a GPS fix.
- Inclusive great-circle radius of 50 miles, applied to sites in the currently loaded system.
- Uses the parser's validated location metadata. Missing, malformed and placeholder positions remain unselected; the screen reports the count. Other sites stay visible for manual selection.
- RadioReference positions may be coverage centers or inherited locations. The API metadata used here does not establish a surveyed tower position. Distance is a selection aid, not a reception prediction or an exhaustive nearby-transmitter search.
- This shortcut browses Riverside County. Other counties and statewide systems are still accessible through Browse or system ID.

The existing API importer handles supported trunked systems and conventional networked digital systems. A flat county list of analog frequencies is not imported by this workflow. The earlier personal Indio CSV pack remains useful for analog tuning and standalone digital channels.

## Verification boundary

The live HTTPS WSDL was reachable and inspected. Account validation, SOAP parsing and imports are exercised offline with captured replies and a dummy application key; the real key is checked in the built APK. A successful authenticated request using your account and reception on your phone still need to be checked in the installed app. No username/password is included in the APK or source archive.

Reference: [RadioReference API requirements](https://support.radioreference.com/hc/en-us/articles/18844460198932-Database-Web-Service-API), [SOAP API documentation](https://wiki.radioreference.com/index.php/RadioReference.com_Web_Service3.1).
