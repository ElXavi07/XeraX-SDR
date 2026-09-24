# XeraX SDR expansion work

User authorized building the previously discussed additions. Implemented in 2.0.0 within the limits documented in UPGRADES-2.0.md. Checked items mean implementation and the available build/host checks, not physical-device acceptance. Preserve the verified 1.4.0 APK until a successor passes its checks. No subagents, per user preference.

- [x] Mixed NFM and digital scan lists, including analog/digital sink setup and activity holds
- [x] Conventional RadioReference frequencies with agency/service selection
- [x] Energy-based signal discoveries alongside digital frame sync
- [x] Analog CTCSS/DCS identification and AM/WFM reception
- [x] Audio/device recovery diagnostics and screen-off validation workflow
- [x] Rolling received-audio replay and WAV clip export
- [x] Priority scanning with call-completion policy
- [x] Measured gain comparison and saved receiver profiles
- [x] Local site map with distance and reception status
- [x] Portable backup/restore of lists, labels and receiver preferences
- [x] Notification/lock-screen Hold, Next, Mute and Speaker actions
- [x] Local talkgroup/radio-ID alerts
- [x] Thermal/battery-aware visualization updates
- [x] Recording-based decoder regression workflow
- [x] Tests, documentation, signed APK and matching source archive

Hardware acceptance needs an attached receiver and an actual S25 or Pixel 9 Pro; synthetic fixtures and desktop tests do not establish over-the-air performance. Gain is judged by reception evidence, not simply set to maximum. Database access does not supply encryption keys.

Scope limits: replay playback needs live reception stopped; WFM is mono; AM/WFM are standalone; scoped-option CSV lists need separate exports; the site display is an offline position plot; gain comparison is RTL-only; thermal adaptation changes UI refresh. Recording regression tools are included, but no real RF capture was supplied. Physical checks remain open in PHONE-ACCEPTANCE.md.
