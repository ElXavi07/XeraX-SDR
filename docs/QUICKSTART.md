# XeraX SDR

An Android app based on DSD-neo, with separate ARM64 and ARMv7 packages. Current version: **4.3.0**. Package: `com.xerax.sdr`. Minimum Android: 10. Galaxy S25 and Pixel 9 Pro use ARM64; physical-device acceptance remains necessary.

## Install and receive

The home navigation is **Listen / Scan / Calls / Tools**. During reception the session menu also opens Scan, Calls and Tools without stopping the receiver. Calls enables recording for the next session and searches/plays/exports completed recordings. Tools → Receiver tools → Receivers, I/Q lab and scanning opens the new receiver lab. See the [4.0 guide](UPGRADES-4.0.md) for all ten upgrades and their operating limits.

1. Download the appropriate 4.3.0 APK from [Releases](https://github.com/ElXavi07/XeraX-SDR/releases/tag/v4.3.0) and open it. Galaxy S25/Pixel 9 Pro use `XeraX-SDR-4.3.0-arm64.apk`; 32-bit ARM Android runtimes use `XeraX-SDR-4.3.0-armeabi-v7a.apk`. Allow installation from that file manager when Android asks. Official XeraX releases use the same signing identity, so updating retains data. It installs separately from DSD-neo.
2. Connect the RTL-SDR through a USB-C OTG data adapter. Open XeraX SDR and grant access to the receiver. Grant notification permission for visible background playback controls.
3. Add a system. Select the local RTL-SDR source and enter a known receive frequency in MHz. The initial example frequency is not a local-frequency recommendation.
4. Choose **NXDN48**, **NXDN96**, **DMR Tier II**, **P25 Phase 1 + 2**, or **P25 Simulcast**. Use a specific mode when known; **Auto—all digital** searches additional rates.
5. Begin with squelch off, bias tee off and normal tuner mode. Try automatic gain, then adjust manually while watching synchronization/error quality.
6. Tap Listen. Open the site/network details for color code/RAN/NAC and call information. Source IDs and destination/talkgroup IDs are separate fields. Import a Radio IDs CSV for contact aliases.

## Check speaker audio

During reception, tap **Check audio**. **Restore speaker audio** unmutes the main receiver, ends replay/extra-receiver playback, requests the phone speaker and retries Android audio focus. **Test sound** sends two short tones through the same native AAudio output used by the receiver (8 kHz digital and 48 kHz analog paths). It works without a radio signal. Use the phone media-volume buttons. An accepted write confirms that Android accepted samples; it does not prove that you heard them. The status explains missing PCM, silence, focus loss and output acceptance. These controls and messages are available in English and Spanish.

## Listen to VHF/UHF analog FM

Open **Explore**, choose your receiver, select **Analog FM (NFM)** and enter the channel frequency. Start exploring, unmute playback and raise the phone's **media volume**. In **Radio → Reception check**, try **Turn squelch off**: channel noise should be audible even between transmissions. In **Radio → Audio output**, tap **Use phone speaker** if Android has routed audio to an earbud or another device.

Existing saved analog channels can be edited to use **Analog FM (NFM)**. During manual listening, **Radio → NFM** changes mode at the current frequency with a brief receiver restart. Digital auto modes do not play analog audio. Analog voice is demodulated; it does not have DMR color codes, digital talkgroups or digital frame sync.

In the spectrum, use **Fine** to swipe a little left/right with a frequency preview. Release to tune. Tap the **12.5 kHz** button to cycle 25, 6.25 and 12.5 kHz steps; minus/plus move one step. Tap a strong peak to tune near its center, or pinch to zoom. **Pan** moves the displayed window without changing the tuner. If the spectrum says **VIEW ONLY**, use **Explore from here** to enable manual tuning.

Analog spectrum sweep uses measured channel energy; digital sweep uses synchronization. For configurable band scanning use **Explore → Scan a frequency range**. Enter start/end MHz (or 440–450 / 440–460 presets), spacing, mode and speed. Start with Balanced; use Hold, Skip, Avoid and Save frequency while running. [Full range-scanner guide](RANGE-SCANNER-4.3.0.md).

## Choose the speaker or another audio output

Open **Radio → Audio output** or **Settings → Listening → Audio output**. Tap **Use phone speaker** for the internal loudspeaker, or choose an available output from the dropdown. **System default** lets Android choose. The app initially requests **Phone speaker**; the phone earpiece is a separate device.

Changes apply with the next audio buffer and can cause a brief audio interruption without restarting the SDR receiver. Check **Reported output** while listening: Android can decline a requested route. Selecting the same output again retries the request. Use the phone's media volume keys and unmute the app.

Available devices depend on what Android exposes, including wired headphones, Bluetooth and USB audio. Disconnecting a selected external output requests the phone speaker. Speaker/default preferences are saved; external devices must be selected again after the app process restarts because their Android IDs can change. An RTL-SDR receiver supplies radio samples and is not itself an audio-output device.

## Scan several channels or systems

Open **Home → Scan lists**, create a list, and add saved systems or explicit frequencies. Choose one receiver for the whole list.

Use **Balanced** initially. **Patrol** checks idle channels more quickly and caps a visit at 15 seconds, but can interrupt calls. **Patient** allows more acquisition time and returns to other channels less often. These presets change list defaults; per-target overrides remain active.

Under **Advanced**, set **Maximum visit per target** in milliseconds. Empty inherits the global setting; `0` disables the default cap; `1000..3600000` sets one second through one hour. Target options may override it. Manual Hold pauses the visit budget. Dwell, activity hold and voice hang time are separate timers.

Use the live monitor's Hold/Release, Next and Avoid controls during a scan. One receiver cannot listen to all frequencies at once.

## Additional digital modes

The saved-system mode picker also offers **D-STAR, YSF, M17, dPMR, X2-TDMA, ProVoice**, and **EDACS** standard/Extended Addressing variants with or without ESK 0xA0. Use ProVoice for a parked traffic channel; EDACS following needs the correct site's LCN channel map. **DMR single-slot** is an alternate decoder; normal **DMR Tier II** handles both slots. EDACS and ProVoice are configured in saved-system setup so their startup settings are applied together.

**Auto—all digital** searches the digital candidate set built into the engine. A known protocol is usually a better starting point than broad detection. See [protocol coverage](PROTOCOLS.md) for the supported families and limits.

## Privacy fields

- Clear channels: leave the key unset.
- DMR basic privacy: choose **Basic · 0–255** and enter the configured decimal value.
- NXDN scrambling: choose **Scrambler · 0–32767** and enter the configured decimal value. Radio programming commonly uses 1–32767.
- DMR enhanced privacy: choose **Enhanced · RC4** and enter the actual configured key in hex, commonly 10 hex digits for 40-bit RC4.
- AES/vendor formats: use **Hex / AES** with the correct protocol-specific format. A color code, talkgroup ID or encryption key ID is not a secret key.

The app accepts compatible supplied keys. An optional **experimental NXDN 15-bit scrambler search** is also included; its synthetic tests do not establish real-radio key recovery. See [NXDN search scope](NXDN-SEARCH-4.1.5.md). General unknown encryption-key recovery is unsupported. Stored radio-key material uses the upstream app-private store; do not include keys in diagnostic reports.

## P25 Phase 2 and trunking

Choose **P25 Phase 1 + 2** on the control channel, then enable trunk following. Use **P25 Simulcast** for an LSM/CQPSK site. A **P25 Phase 2 voice** selection parks on a traffic channel; if it lacks MAC signaling, advanced parameters such as `-X WACNSYSNAC` may be required (five, three and three hex digits respectively). These must come from the actual system.

Import channel maps/talkgroup lists when the system requires them. One dongle follows one RF frequency at a time; it can miss simultaneous traffic on other frequencies.

## Other inputs

- Blog V4/V4L and supported RTL-compatible dongles use the local RTL path.
- Airspy R2/Mini use the separate Airspy source and controls.
- A supported remote `rtl_tcp` server can provide IQ. TCP/UDP PCM and local file inputs are also available.
- HackRF One has an experimental direct USB receive-only backend, with current app tuning approximately 1 MHz–2 GHz. See [receiver setup and limits](RECEIVERS-4.1.2.md).
- Direct SDRplay, LimeSDR, Airspy HF+ and arbitrary SoapySDR support is not included.

## If it does not decode

Check USB permission/power, frequency, protocol and bandwidth first. Reduce excessive gain, turn squelch off, try another antenna position, and select simulcast mode when appropriate. Stop other apps that have claimed the dongle. For a private call, verify the algorithm and supplied key. For a trunked call, verify control-channel following and channel data.

Open **Spectrum → Radio → Reception check** for an explanation based on the engine's current state. It can identify muted audio, missing RTL samples, enabled squelch without sync, and private-call flags. A manual **Turn squelch off** action is available where applicable. SNR and frame sync alone do not guarantee intelligible speech.

For a useful report, include phone model, Android version, receiver/tuner, protocol, frequency, a redacted diagnostic export and the exact failure. A reproducible clear-channel recording is preferable to a description of garbled audio. Never send private key material.
