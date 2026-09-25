# XeraX SDR

<img src="assets/xerax-icon.svg" alt="XeraX SDR icon" width="96">

**Android SDR receiver, digital voice decoder and scanner, with English and Spanish controls.**

## 4.3.2-rc.3 — NXDN confirmation reliability

[RC3 prerelease and downloads](https://github.com/ElXavi07/XeraX-SDR/releases/tag/v4.3.2-rc.3) · [Release notes and verification](releases/4.3.2-rc.3/NOTES.md). Android **arm64-v8a / armeabi-v7a** and Windows **x64 installer / portable ZIP** are available.

RC3 integrates the measured correction that prevents rejected NXDN headers from joining two separate weak-confirmation observations. Confirmed calls retain their history, while rejected frames provide no new proof. Existing settings and upgrade identities are preserved. The experimental faster NXDN48 option stays **off by default**.

The correction passes current Windows/Linux regressions, including sanitizer checks; the prior source fails the new regression. Packaged Windows software checks and both APKs' static/signing checks pass. Physical radio/phone, human listening and installer execution remain pending. This is a reliability correction, with no new RF sensitivity or audio-speed claim. [Integration evidence](docs/research/RC3-INTEGRATION-2026-09-25.md).

## 4.3.2-rc.2 — optional earlier NXDN48 detection

[RC2 prerelease](https://github.com/ElXavi07/XeraX-SDR/releases/tag/v4.3.2-rc.2) · [Release notes and limits](releases/4.3.2-rc.2/NOTES.md). Packages cover Android **arm64-v8a / armeabi-v7a** and Windows **x64 installer / portable ZIP**.

Open **Tools** to reach Settings, then **Decoding · next start → Faster NXDN48 detection (experimental)**. While listening, open **Session options → Settings**. The option is **off by default**; changes apply when you stop and start listening again. It tries the first canonical positive NXDN48 waveform sync while preserving frame/CRC validation. Diagnostic I/Q replay and the built-in lab use their own trial settings.

The preceding [synthetic component experiment](docs/research/NXDN-FIRST-SYNC-2026-09-25.md) recovered the first valid control frame about **80 ms earlier in 120 positive cases**, with no false current-frame proof in **36 controls**. This does not establish faster audio, lower CPU use, or better device reception. Physical phone/receiver and listening tests remain pending. Earlier releases remain available below.

**Windows preview available:** [installer and portable download](https://github.com/ElXavi07/XeraX-SDR/releases/tag/v4.3.1) · [Windows setup and feature limits](docs/WINDOWS.md). Native Windows 10/11 x64, with core reception, decoding, scanning and desktop audio. Android features below do not all apply to this preview.

**New desktop interface:** branded sidebar and Windows icon, direct range-scanner setup, visible scrollbars, and optional OpenAI / DeepSeek reception investigations. [Screenshots](docs/WINDOWS-SCREENSHOTS.md) · [Current validation](docs/RECEIVER-QUALITY-4.3.1.md)

**Long-term receiver engineering:** [2026 platform comparison](docs/research/PLATFORM-COMPARISON-2026.md) · [Measured roadmap](docs/research/ENGINEERING-ROADMAP.md) · [Benchmark framework](benchmarks/README.md) · [Initial results and limits](docs/research/INITIAL-RESULTS.md) · [Recovery stress test and retained failures](docs/research/NXDN-RECOVERY-2026-09-25.md) · [Finite-input and voice observation results](docs/research/NXDN-OBSERVATION-V2-2026-09-25.md) · [Boundary prediction: failed retention](docs/research/NXDN-BOUNDARY-V1-2026-09-25.md). Research and experiments do not imply new capabilities in the downloadable release.

![XeraX SDR Windows listening desk](assets/screenshots/windows/listening-en.png)

**New NXDN research foundation:** [independent voice-word validation](docs/research/NXDN-VOICE-WORDS-V1-2026-09-25.md) agrees on 8,266 known channel words and passes 27,044 registered hard/soft FEC checks. Protected single-bit errors are corrected; deliberately changed unprotected bits remain changed as expected. This supplies known content for future recovery tests and does not change the downloadable APK/Windows packages.

[Download 4.3.1](https://github.com/ElXavi07/XeraX-SDR/releases/tag/v4.3.1) · [Español](README.es.md) · [Getting started](docs/QUICKSTART.md) · [Complete features](docs/FEATURES.md) · [Issues](https://github.com/ElXavi07/XeraX-SDR/issues)

XeraX combines analog listening, DMR, NXDN and P25 decoding, spectrum tuning, range scanning, recordings, receiver diagnostics and optional AI investigations. Reception and decoding run on the phone using a connected SDR or a supported network source.

**4.3.1 is a community testing release.** It improves decoder CPU efficiency and reception/audio diagnostics, with a local reception report and updated Spanish messages. See the [measured changes and limits](docs/RECEIVER-QUALITY-4.3.1.md). Physical phone/receiver acceptance remains pending.

## Download

Requires **Android 10+** and a compatible receiver/input. A phone alone cannot receive these SDR signals.

| Package | Use it for |
|---|---|
| [ARM64 APK](https://github.com/ElXavi07/XeraX-SDR/releases/download/v4.3.1/XeraX-SDR-4.3.1-arm64.apk) | Galaxy S25, Pixel 9 Pro and other 64-bit ARM Android runtimes |
| [ARMv7 APK](https://github.com/ElXavi07/XeraX-SDR/releases/download/v4.3.1/XeraX-SDR-4.3.1-armeabi-v7a.apk) | 32-bit ARM Android runtimes; still requires Android 10+ |
| [Matching source](https://github.com/ElXavi07/XeraX-SDR/releases/download/v4.3.1/XeraX-SDR-4.3.1-source.zip) | Complete patched engine, build scripts, tests and original release documentation |

Install the package appropriate to your Android runtime. Existing official XeraX installations can update using the same package/signing identity. Builds signed by someone else may require a separate installation. Release assets include SHA-256 checksums and a verification report.

## Included features

- **Analog and digital:** NFM two-way voice, AM, broadcast FM mono, NXDN48/96, DMR Tier II, P25 Phase 1/2 and additional inherited digital modes in the [protocol matrix](docs/PROTOCOLS.md).
- **Range scanning:** enter a range, including 440–450 / 440–460 MHz presets; choose spacing, mode and speed; Hold, Skip, Avoid, resume and save discoveries.
- **Scan lists and trunking:** mixed analog/digital lists, priority rotation, talkgroups, channel maps, aliases and supported configured trunked systems.
- **Spectrum:** waterfall, peak selection, fine swipe tuning, channel steps, zoom, gain and automatic/manual PPM.
- **Audio:** phone speaker/output selection, test tones, actual PCM diagnostics, replay, call recordings and WAV export.
- **Receiver tools:** USB diagnostics, measurements, bounded gain/site trials, I/Q capture/comparison, experimental nearby receivers and two-dongle P25.
- **RadioReference:** account-based conventional/trunked imports, site selection and nearby browsing. Account entitlements apply; no shared user account is included.
- **Optional AI:** your OpenAI or DeepSeek key, models fetched from the provider and controlled local measurement tools. Disabled by default; model inference uses the provider's internet service.
- **Bilingual interface:** English/Spanish selection and 981 catalog translations checked in this release. Some inherited technical text and database labels retain their original language.

See the [complete feature guide](docs/FEATURES.md) for privacy handling, experimental features and limits, and the [scanner guide](docs/RANGE-SCANNER-4.3.0.md) for operating controls.

## Receivers

| Hardware/source | Included path | Status |
|---|---|---|
| RTL-SDR Blog V3, V4, V4 Lite and supported RTL2832U dongles | Android USB OTG or compatible RTL-TCP | Driver included; tuner limits and USB power apply |
| Airspy R2 / Mini | Android USB OTG, Airspy source | Backend included; hardware acceptance pending |
| HackRF One | Android USB OTG, receive only | Experimental; current app range approximately 1 MHz–2 GHz |
| RTL-TCP | Compatible server on another host | Raw I/Q streamed to the phone; appropriate server driver required |
| Supported file / PCM inputs | Local replay or TCP/UDP audio source | Format and mode must match the engine |

This is an implementation matrix, not certification of every receiver/phone pair. Direct SDRplay, LimeSDR, Airspy HF+ and general SoapySDR support are not included. [Receiver guide](docs/RECEIVERS-4.1.2.md) · [Wi-Fi setup](docs/WIFI-RECEIVER-SETUP.md)

## First session

1. Install the APK and connect a supported USB SDR with an OTG data adapter, or configure RTL-TCP on your local network.
2. Open **Explore**, choose the source, frequency and mode. Use **Analog FM (NFM)** for narrowband analog two-way radio.
3. Grant USB access, start reception, select **Phone speaker** and raise media volume. **Check audio → Test sound** tests playback independently of traffic.
4. For a band search, enable **Scan a frequency range** in Explore. Start with **Balanced** and select the known protocol when possible.

Control/signaling channels can be active without voice. “Waiting for audio” alone does not establish a speaker fault. [Full setup and troubleshooting](docs/QUICKSTART.md)

## Source and community

The complete patched engine is browsable in [upstream/dsd-neo](upstream/dsd-neo). [UPSTREAM.json](UPSTREAM.json) pins its original revision; [patches/xerax.patch](patches/xerax.patch) records the original XeraX patch baseline. Subsequent changes are tracked in Git; the complete vendored source is authoritative. The release source ZIP freezes the matching 4.3.1 source and documentation.

[Build on Windows](docs/BUILD.md) · [Contribute and report hardware results](CONTRIBUTING.md) · [Phone acceptance](docs/PHONE-ACCEPTANCE.md) · [Privacy](upstream/dsd-neo/PRIVACY_POLICY.md)

This is an independent derivative of [DSD-neo](https://github.com/arancormonk/dsd-neo), not an official upstream release. Digital implementations and the vocoder come from upstream and its dependencies; XeraX extends the Android interface, receiver controls, analog paths, scanning, imports and diagnostics. No measured superiority over an SDS100 or another decoder is claimed.

Distributed under **GPL-3.0-or-later**, with retained third-party notices. See [LICENSE](LICENSE), [COPYRIGHT](upstream/dsd-neo/COPYRIGHT) and [third-party attribution](upstream/dsd-neo/THIRD_PARTY.md).
