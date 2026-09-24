# XeraX SDR 2.0.0 testing release

Install the signed ARM64 APK over the existing XeraX app to retain your data. The application ID and signing identity are unchanged. This release is built for the Galaxy S25 and Pixel 9 Pro architecture; neither phone was attached for this build.

## Listening and scanning

- Explore now offers NFM two-way voice, AM aviation, broadcast FM **mono**, and digital decoding. AM and WFM require restarting reception when switching modes. WFM requests a 240 kHz RF processing bandwidth and 48 kHz audio; there is no stereo or RDS decoder in this release.
- Manual scan lists can mix NFM, P25, DMR, NXDN48 and NXDN96. Both analog and digital audio sinks are opened for those lists. NFM activity above squelch extends the hold even when audio is muted.
- Each manual entry has a Priority checkbox. Priority and ordinary groups alternate using separate rotation positions; avoided/cooling targets are skipped. A single dongle must leave one frequency to check another.
- The advanced **Finish active calls** checkbox removes the maximum visit limit. Dwell and activity hold still apply. A configured visit limit or Next can interrupt a call; manual Hold takes precedence.
- Analog spectrum Sweep stops on measured channel energy 10 dB above the surrounding-bin median, rather than waiting for digital sync. A center-bin spike alone does not qualify. Listen and use the existing Save action to keep a discovery; this is not an automatic protocol classifier.
- CTCSS and common DCS identification appears in Settings → Receiver tools. It needs stable, unsquelched NFM. CTCSS requires two confident one-second observations; DCS requires four exact repeated codewords. DCS normal/inverted equivalent labels can both be shown. This identifies signaling and does not gate the speaker by a chosen tone.

## RadioReference

Open RadioReference → **Conventional channels**. Browse Riverside County or the selected county, choose an agency/service category, and select frequencies. Create a mixed NFM/digital scan list or save individual channels. AM/WFM selections are saved as individual channels, not mixed scan entries. Generic NXDN records require choosing 48 or 96.

The app calls `getCountyInfo`, `getAgencyInfo`, `getSubcatFreqs`, and `getMode`, in addition to the existing trunked-system operations. It shows receive mode, tone, color code and tags. Database metadata is a reference; received identifiers come from the decoder. The 50-mile filter uses category coverage centers around Indio and includes unknown positions. It does not claim every imported frequency is receivable within that radius. App-key approval does not replace a Premium account login.

## Receiver tools

- **Replay:** bounded 60-second received-audio buffer; play the last 30/60 seconds after stopping live reception, or export a 48 kHz mono WAV while listening. Buffer includes audio sent to the output; skipped silent intervals are not reconstructed. Digital slots are mixed into mono. Replay requests the selected output route and Android audio focus.
- **Gain comparison:** RTL-SDR only; five gains, two seconds settling plus ten seconds measuring each. Shows SNR, ADC clipping, and control-frame success when enough frames exist. Restores the old gain; you choose a candidate. Changing traffic can bias a comparison, and this cannot manufacture sensitivity.
- **Profiles:** named gain/PPM/bandwidth/bias-tee defaults for a dongle/antenna/band. They apply to the next session, without automatic USB serial matching. Airspy retains its existing dedicated controls.
- **Site plot:** offline north-up saved-site positions within 50 miles of Indio. Gray means avoided; green means a digital call was observed while tuned to a matching site frequency. These observations are made while the Qt UI is alive. Coordinates may represent coverage centers; there are no downloaded street-map tiles.
- **Backup:** appends restored systems/lists with new IDs and relocated CSV companions. It excludes account details, direct radio keys, argument overrides and recordings. Simple imported target CSVs become editable lists; target CSVs with scoped options require a separate CSV export. Existing records are retained. Audio-route selection and alert rules remain per-device. The file is local JSON, not an encrypted cloud backup.
- **Alerts:** `tg:1234, rid:5678` rules, up to 64 IDs, matched across systems. Local Android notifications require permission and are limited to one alert per matching identity set per 30 seconds. Short calls between the service polls may be missed.
- **Phone health:** battery percentage, saver state and Android thermal status. Saver or moderate thermal pressure slows spectrum/waterfall UI refresh to 500 ms; demodulator quality settings are not reduced.
- **Notification:** Hold/resume, Next, mute/unmute, Speaker and Stop, using expanded media-style controls. Android/OEM lock-screen presentation still requires physical-device acceptance.

## Validation limits

Automated checks cover selected decoder primitives, real configuration/CSV/parser code, synthetic AM/NFM/WFM waveforms, tone signals/noise, audio replay, backup restoration and QML interactions. They do **not** prove complete RF-to-speaker operation, weak-signal performance, USB recovery or background survival on either phone. The signed package is statically checked for ARM64 dependency closure and 16 KB alignment. Live RadioReference login/import remains a device check.

Current digital coverage is in [PROTOCOLS.md](PROTOCOLS.md). This release does not add unknown-key recovery, guarantee decoding of encrypted channels, or introduce new untested digital protocol families.

## Recording regressions

The source includes upstream `tools/replay_ab.sh` and `tools/replay_ab_report.py`, plus a Windows-friendly `scripts/replay_regression.py`. Record real I/Q with its DSD-neo sidecar, then compare compatible desktop decoder executables, for example:

```powershell
python scripts/replay_regression.py --capture C:/captures/dmr.iq.json --mode=-fs --repeats 12 --out build/replay-dmr C:/decoder-before.exe C:/decoder-after.exe
python upstream/dsd-neo/tools/replay_ab_report.py build/replay-dmr/summary.tsv
```

Runs rotate order to reduce time/order bias; failed or timed-out runs are excluded from quality estimates. Compare decoded frame counts as well as errors per frame. No real local RF capture was available for this release, so no over-the-air improvement percentage is reported. Analog modes need audible/WAV evaluation; digital log counters do not score analog quality.

## Sources

- [RadioReference official API documentation](https://support.radioreference.com/hc/en-us/articles/18844460198932-Database-Web-Service-API) and [WSDL](https://api.radioreference.com/soap2/?wsdl&v=latest).
- [Android audio focus](https://developer.android.com/media/optimize/audio-focus), [foreground media services](https://developer.android.com/develop/background-work/services/fgs/service-types), [thermal API](https://developer.android.com/games/optimize/adpf/thermal).
- [GNU Radio quadrature demodulator](https://www.gnuradio.org/doc/doxygen/classgr_1_1analog_1_1quadrature__demod__cf.html).
- DCS parity matrix/code set derived under GPL-3.0-or-later from [SDRangel Golay code](https://github.com/f4exb/sdrangel/blob/master/sdrbase/util/golay2312.cpp) and [DCS code mapping](https://github.com/f4exb/sdrangel/blob/master/sdrbase/dsp/dcscodes.cpp), copyright 2021 Edouard Griffiths, F4EXB. The streaming detector is new and tested with synthetic waveforms.
