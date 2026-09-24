# Version 4.3.0 validation

The latest release records **33 host test groups, 80 QML cases and 878 Spanish translations**, both Android release builds/lint, APK signature and ABI/dependency verification, and source/native-code matching. See the [machine-readable report](../releases/4.3.0/verification.json) and [scanner guide](RANGE-SCANNER-4.3.0.md).

These are software/package checks. Physical phone/receiver acceptance, scan-speed measurements, intelligible real-radio speech, screen-off operation and live AI-provider calls remain pending. The older sections below describe their respective historical releases and are not a cumulative hardware result.

---

# Version 4.1.1 validation

The audio repair release passes **29 application host groups, 68 QML cases, 33 engine groups, five production RTL-TCP analog tests, and the Kotlin audio-focus regression**. The Android release and vital lint pass. The **655-entry Spanish catalog** passes coverage/placeholder checks. See [audio findings, measurements and test limits](AUDIO-4.1.1.md). Physical S25/Pixel speaker playback remains pending.

---

# Version 4.1.0 validation

All **28 application host groups**, **67 QML cases**, **30 full-I/Q regressions**, and the **atomic P25 voice-command test** pass. The **629-entry Spanish catalog** passes placeholder and receiver-screen coverage checks. The six receiver-lab pages render at 320 logical pixels with 130% text scale.

The production Phase 1 and both Phase 2 slot payload functions pass independent AES-128, AES-256 and DES reference vectors with two message indicators, multiple consecutive voice frames, wrong-key output and missing-key gating. Existing ADP and NXDN checks still pass. These tests do not assert intelligibility on real encrypted radio captures.

The app lab has **15 passing cases**, including a DMR RAS control fixture with the dedicated DMR-only switch and strict-mode rejection of the same fixture. RAS mode reports 65 suspected bursts and one rejected burst; strict mode reports zero suspected and 66 rejected. These counters are evidence about control/header handling, not decryption. Four additional DSP offset/filter comparisons complete. See [I/Q report](IQ-LAB-4.1.json).

The production multistage channel filter preserves expected P25 C4FM, P25 CQPSK, DMR, NXDN48 and NXDN96 evidence across **five full-chain replay cases**, using synthetic 1.536 MS/s capture and 192 kS/s worker input with the Fs/4 offset. Unit checks also cover anti-alias attenuation and block-boundary continuity. Native loopback sockets, Android IPC and USB throughput have not been exercised on a handset.

All **ten deterministic impaired-simulcast comparisons** finish. Equalizer and bypass tie in four paired cases; the heavy-noise sample yields 50 accepted / 0 rejected frames with equalization and 48/0 with bypass. This is one short waveform and one seed per condition. It does not justify a general reception superiority claim, and the equalizer remains off by default. See [benchmark report](RECEPTION-BENCHMARK-4.1.json).

The native voice-command test rejects scanner mode, applies Phase 1/2 modulation/network/slot context, mutes the other TDMA slot, restores Phase 1 audio selection and reports failure without a live tuner. It does not measure successful USB retuning or call-opening latency. The timed reception sampler tests correct counter differences, valid SNR averaging, duration, frequency changes and counter resets. The empty paired-radio comparison workflow reports pending.

The Android ARM64 release and vital lint pass. Version **4.1.0 / 40100** preserves the application ID and signing identity. Release verification records signature, native dependency completeness, 16 KB alignment, corresponding source hashes and preservation of earlier release files. The source archive excludes local credentials and signing material.

The user chose APK self-testing and software comparisons because no phone or SDS100 is attached. Actual internal-speaker playback, background operation, USB hub operation, RF speech quality, battery improvement and an SDS100 comparison remain pending. See [4.1 notes](UPGRADES-4.1.md), [comparison workflow](RECEIVER-COMPARISON.md) and [phone acceptance](PHONE-ACCEPTANCE.md). Earlier results below are historical.

---

# Version 4.0.0 validation

All **27 application host groups**, **66 QML cases** and **30 full-I/Q decoder regressions** pass. The **599-entry Spanish catalog** passes placeholder and required new-screen coverage checks. The new pages were rendered and inspected at 320 logical pixels and 130% text scale; a clipped heading was corrected.

The host parity runner executes all **13 bundled app-lab cases** and **four DSP comparison settings**. All baseline expectations pass, all trials exit successfully, and six voice fixtures produce nonzero PCM samples. The [machine-readable report](IQ-LAB-4.0.json) records fixture identity, exits, expected evidence, P25 FEC telemetry and PCM measurements. These synthetic fixtures do not establish over-the-air speech intelligibility. P25 Phase 2 I/Q coverage is SACCH/control; existing supplied-key tests exercise its production voice payload routines separately.

With identical CQPSK settings, the simulcast fixture reports 52 accepted / 0 rejected frames with both bypass and the experimental equalizer. No improvement is established. The equalizer remains off by default.

New native tests cover CRC-verified MDC/FleetSync decoding from generated AFSK, corrupt-CRC rejection, all DTMF digits, paging order, shared capture frequency translation, trial DSP, equalizer bypass/finite output, P25 grant context, analog PCM/WAV construction and squelch hang, and finalized-call retention/favorites/search/export boundaries. Previous analog demodulation, routing, scanner, RadioReference and privacy tests continue passing.

The Android ARM64 release build and vital lint pass. The package uses version 4.0.0 / 40000 and the existing com.xerax.sdr identity/certificate. Final package size, hashes, source verification and dependency/alignment checks are recorded in `dist/XeraX-SDR-4.0.0-verification.json` and `dist/SHA256SUMS.txt`.

No physical phone, SDR/USB hub, live RF or live Premium API session was available. Android worker IPC, service reconnection, document-provider export and actual speaker playback remain device acceptance items: compiled/linted, not executed on the phones. See [4.0 limits](UPGRADES-4.0.md) and [phone acceptance](PHONE-ACCEPTANCE.md). Earlier findings below are historical.

---

# Version 3.0.0 validation

All **26 host test groups** passed. The QML executable passed **60 cases** with no failures or skipped cases. The Spanish catalog check passed all **437 placeholder checks** and required receiver-tool string coverage. Layouts were rendered and inspected in English at 390 logical pixels and Spanish at 320 pixels with larger text; narrow tabs use two rows.

The additional checks cover real native per-frequency audio filters, synthetic tone gating, measured gain trials and rollback, site selection/cooldown/hold guards, discovery persistence/export, bounded capture arguments and TAR contents, live replay buffering during output suppression, language changes, and direct/automatic ADP profile validation. The native AAudio tests use a fake Android API, not a handset.

Privacy validation goes beyond UI fields: independent PyCryptodome-generated ciphertext passes through the production P25 Phase 1 ADP, P25 Phase 2 ADP and left/right DMR ARC4 voice payload routines. A fixed NXDN vector passes through the production 15-bit voice descrambler. The real NXDN element key loader is tested for received-ID selection, destination fallback, NXDN96 mapping, direct-override preservation, explicit zero material and clearing a missing key after a previous match. P25/DMR scalar activation also checks slot isolation and missing-entry handling. NXDN profile checks accept 0/32767 and ID 63, and reject 32768 and ID 64. These are deterministic payload/configuration checks, not tests of unknown-key identification or full RF-to-speaker decoding.

The Android ARM64 release build and vital lint succeeded with native warnings treated as errors. Signing, ZIP alignment, dependency closure, license assets and 16 KB ELF alignment are independently checked for the delivered APK; the current package report is `dist/package-verification.json` and hashes are in `dist/SHA256SUMS.txt`. Version is `3.0.0` / `30000`, with the existing `com.xerax.sdr` identity and signing certificate.

The signed 3.0.0 APK is 36,445,407 bytes and contains 79 ARM64 native libraries. SHA-256: `e3e5aa93b218d75698be765982850d559bc0671dafaf71c50eaa1ec4ce538526`. Its certificate SHA-256 is `43044bacd6d5ac2e407952e07a59e57dce06409f030408e84b79283dcfa765b5`, matching earlier XeraX releases.

No physical phone, SDR, live RF, known encrypted radio recording or live Premium API session was tested here. UI timers do not promise to survive Android activity destruction. See [3.0 limitations](UPGRADES-3.0.md) and [phone acceptance](PHONE-ACCEPTANCE.md). The earlier release findings below are retained as history.

---

# Version 2.0.0 validation

The configured host suite passed all 21 groups. This includes 51 QML cases, the real conventional SOAP shapes, native mixed-mode/priority CSV parsing, ring-buffer wrap and stereo resampling, WAV framing, portable backup merge/UID relocation, synthetic CTCSS/DCS and noise rejection, and AM/NFM/WFM discriminator correlation. QML screenshots of Receiver tools and Conventional channels were inspected and the clipped filter label corrected. The prior 1.4.0 findings below are historical; conventional frequency browsing is now implemented.

The Android release build and vital lint succeeded. Signing/package checks are recorded in `dist/package-verification.json` and `dist/SHA256SUMS.txt` for the delivered APK. No S25, Pixel 9 Pro, SDR hardware, live Premium API session or real RF recording was available here. See [2.0.0 limitations](UPGRADES-2.0.md) and the [phone acceptance procedure](PHONE-ACCEPTANCE.md).

---

# XeraX SDR 1.4.0 validation

This is a built and signed Android release APK, based on the pinned DSD-neo engine. It is ready for installation and device evaluation. It has **not been run on a Galaxy S25, Pixel 9 Pro, or a connected SDR** in this workspace. No claim of measured reception superiority is made.

## Build and package results

| Check | Result |
|---|---|
| Native ARM64 release build | Passed, NDK 28.2 / Clang 19, `-O3`, ThinLTO |
| Android release packaging and vital lint | Passed, Gradle 9.3.1 / Android Gradle Plugin 9.0.0 |
| Application label | `XeraX SDR` |
| Application ID / version | `com.xerax.sdr` / `1.4.0` (10400) |
| SDK | Minimum 29, target and compile 36 |
| APK signature verification | Passed, APK Signature Scheme v3, RSA 4096 |
| ZIP integrity | Passed |
| Native payload | 79 ARM64 libraries; no other ABI |
| ELF load segment alignment | All native libraries meet 16 KB alignment checks |
| APK ZIP alignment | `zipalign -c -P 16 4` passed |
| Native library dependencies | All non-system dependencies included |
| Licenses | Engine license, inherited notices and 37 additional dependency/license assets included |

APK size: 36,322,527 bytes (about 34.6 MiB).

APK SHA-256:
`d239871dd9869fd4c273eb67eda6d3964ef7e8d10f19e7c6451833b876d8ab08`

Signing certificate SHA-256:
`43044bacd6d5ac2e407952e07a59e57dce06409f030408e84b79283dcfa765b5`

The package has its own local signing identity. It is not signed by the upstream DSD-neo maintainer. v3 is appropriate for the minimum Android 10 version; v1/v2 signatures are not required for this minimum version. Static 16 KB checks establish packaging compatibility, not successful execution on a 16 KB device.

## Automated checks

All seventeen selected host check groups passed. The account/model group was rerun after correcting the Windows test executable's UTF-8 path handling and using a floating-point tolerance for the zero-distance test:

1. **FEC_block_codes:** upstream block-code error-correction tests.
2. **FEC_bptc_rs:** upstream BPTC/Reed–Solomon tests, including DMR codewords.
3. **P25_BCH:** upstream P25 NID BCH tests.
4. **NXDN_convolution:** upstream NXDN convolutional-code tests.
5. **NXDN_lfsr:** upstream NXDN LFSR tests.
6. **SESSION_ARGUMENTS_AND_KEYS:** real upstream Qt session argument/model validation.
7. **PRIVACY_EDITOR_QML:** instantiates the actual modified QML editor with the real argument validator. Checks DMR basic 0 and 255, rejects −1 and 256; NXDN 0 and 32767, rejects 32768; RC4 hex validation; and protocol-incompatible key selection.
8. **SCANNER_POLICY_AND_PERSISTENCE:** visit/dwell/hold boundaries; invalid types and overflow; inherited versus explicit zero; precedence over advanced global options; saved-model reload and partial updates.
9. **SCANNER_TARGET_REGRESSION:** upstream target-generation suite for saved systems, protocols, CSV settings and invalid configurations.
10. **SCANNER_AND_RECEPTION_QML:** actual scan-editor preset application, save/reload and keyboard edits; lower dwell bound; reception messages, private flags, Airspy versus RTL sample state, invalid/stale SNR suppression, manual squelch request, and component widths of 320/390/480 logical pixels. External file picking is a fixture; these tests do not open a tuner.
11. **ANALOG_AND_DIGITAL_MODE_PRESETS:** upstream tests over the actual mode-preset implementation, including analog transitions and decoder frame flags.
12. **ANDROID_AUDIO_ROUTING_AND_BACKEND:** real native AAudio implementation with a fake Android API. Covers selecting an initial output, deferring a route change until the writer resumes, one reopen per request, explicit retry, default routing, rejection of negative IDs, reporting the actual device when Android grants a different one, preserving the request during sample-rate fallback, failed-open backoff, and input-stream isolation. Existing conversion, recovery and pump checks also run.
13. **RADIOREFERENCE_ACCOUNT_MODEL_AND_IMPORT:** real Qt import model, Expat parser, generated files and library persistence with captured SOAP replies. Covers built-in key precedence, authentication failure handling, account gates, browse/cancel/refresh behavior, single and multiple site imports, missing positions and distance from Indio. A Windows UTF-8 process manifest permits the test's non-ASCII filenames; no Android production change was needed for that host issue.
14. **RADIOREFERENCE_soap:** actual SOAP envelope construction and response parsing, including malformed/missing location data.
15. **RADIOREFERENCE_client:** actual request worker, response/error handling and cancellation with injected transport responses.
16. **RADIOREFERENCE_generate:** generated channel/group files round-tripped through the real decoder CSV validators.
17. **RADIOREFERENCE_import:** system classification and import policy for supported protocols.

The QML executable passed. Cases cover analog setup/startup arguments; analog/digital restart requests from Radio; stored Explore mode; analog reception guidance; protocol catalog flags and dPMR/DMR profile mapping; production Main.qml component compilation; a real pointer swipe with no retune before release; a real two-finger pinch with no retune; fine preview and one release command; canceled/controller-blocked/rejected tunes; Pan at the viewport edge; channel-step controls; peak snapping; and the compact spectrum layout. Audio-selector cases cover the speaker button, dropdown requests, selection bindings, mismatched actual output, invalid indices, removed-device/error display, empty choices and 320/390/480 logical-pixel layouts. A synthetic spectrum producer, route map and command recorder replace hardware. These tests do not exercise the Kotlin router on Android, the full Android restart lifecycle or audible playback.

The RadioReference QML cases also passed: keyed login visibility, Riverside County selection, inclusive 50-mile boundary, original site indexes, missing/nonfinite positions, busy/account gates, manual overrides, empty results, conventional repeater selection and compact layouts. Both the county search and selected-site views were rendered and visually inspected.

The approved application key was verified inside the signed APK without printing it. The HTTPS WSDL was fetched and its operation list inspected. The account and import tests use a dummy key and injected SOAP replies, not a live Premium login. The current app importer does not fetch a flat county analog frequency list. See [RadioReference setup](UPGRADES-1.4.md).
The privacy editor, scanner editor, visit-limit fields, reception panel, analog setup, fine-tuning spectrum and audio-output selector were rendered with Qt Quick's desktop software backend for visual inspection. Preview receiver values are test data. These checks cover selected decoder primitives and configuration behavior. They do not validate complete radio-to-audio decoding, all protocol variants, or the full upstream test suite.

Nonfatal packaging warnings include the runtime-registered `DsdNeo` QML module, the legacy manifest package attribute being superseded by the Gradle namespace, and SDK metadata version skew. Release packaging and vital lint completed successfully. The final package ID, application label and increased version code were independently verified with `aapt2 dump badging`. The signing certificate matches 1.0.0, allowing an in-place update; that update has not been performed on a physical phone here.

## Device acceptance checks still required

| Area | Check on each phone |
|---|---|
| Installation/startup | App launches; all screens display; no native load error |
| USB | Permission, tuner identification, detach/reconnect and sustained receive |
| Clear NXDN | Known calls and IDs on NXDN48 and NXDN96 |
| Clear DMR | Color code, source/destination IDs and both slots |
| Privacy | Known test calls using matching configured NXDN/basic/RC4/AES keys |
| P25 | Phase 1 C4FM, Phase 1 simulcast, Phase 2, and control-channel following |
| Audio/background | Speaker selected while earbuds are connected; wired/Bluetooth/USB and default selection; reported route; disconnect fallback; restart preference; screen-off playback; notifications and clean stop |
| Analog FM | Known narrow FM voice, audible noise with squelch off, media volume keys, route changes and analog/digital restart at the same frequency |
| Spectrum touch | Fine swipes, peak taps, pinch zoom, controller ownership and update latency on both phones |
| Sustained operation | Dropped buffers, memory, temperature and battery during a long session |

Other receivers were enabled according to upstream support, not physically tested here. The build does not establish manufacturer-wide privacy interoperability or guaranteed decoding of weak, overloaded, multipath, or incorrectly configured signals.
