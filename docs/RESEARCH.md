# XeraX SDR — Android receiver and decoder research

Research date: 21 September 2026. Target phones: Samsung Galaxy S25 and Google Pixel 9 Pro. Source snapshot: DSD-neo `8c9c120389401fc2db3ef52869e13d555712e5fb`, with XeraX changes recorded separately.

Updated scanner and reception work for version 1.1 is documented in [UPGRADES-1.1.md](UPGRADES-1.1.md).
Version 1.2 adds [analog audio and fine tuning](UPGRADES-1.2.md), plus an audit and exposure of the engine's [digital voice families](PROTOCOLS.md).

## Decision

Build on DSD-neo's existing Android implementation. It combines a native demodulator, protocol parsers, error correction and an IMBE/AMBE vocoder with direct USB device handling and an Android foreground audio service. That is a substantially better starting point for this request than recreating these components from protocol descriptions. This is an engineering selection, **not a measured claim that it outperforms every receiver**. No comparative weak-signal or simulcast benchmark was performed on the user's radios.

DSD-neo documents NXDN, DMR and both P25 phases, ARM64 Android builds, RF diagnostics and direct or network inputs. Its native radio path includes symbol-domain FSK/CQPSK demodulation, filtering, timing recovery and optional frequency correction. [Project overview](https://github.com/arancormonk/dsd-neo).

## Requirements mapped to actual behavior

| Requested item | XeraX SDR implementation | Important distinction |
|---|---|---|
| USB RTL V3 | Android USB permission + native RTL-SDR receive path | USB-C OTG/data connection; no root |
| Other receivers | RTL-compatible devices, Blog V4/V4L; native Airspy R2/Mini; network inputs | A dongle being an SDR does not make its USB protocol RTL-compatible |
| NXDN48 | Dedicated 4800 bit/s decode selection | 6.25 kHz channel; 2400 symbols/s |
| “NXDN98” | Interpreted as NXDN96, with its own selection | 9600 bit/s; 12.5 kHz channel; 4800 symbols/s |
| NXDN 0–32767 | Validated direct scrambler-value entry | A configured value, not a search through unknown keys |
| DMR Tier II | Two-slot digital voice and call metadata | DMR direct/simplex and repeater behavior differ |
| DMR color code | Decoded from signaling | 0–15; neither a talkgroup nor a privacy key |
| Contact | Destination/talkgroup and source radio IDs; imported aliases | A numeric ID does not automatically identify a person |
| Basic privacy 0–255 | Validated basic-privacy value entry | Manufacturer interoperability is not guaranteed |
| Enhanced privacy | Supplied RC4 key; supported AES/vendor key formats | A key ID alone cannot decrypt the call |
| P25 Phase 1/2 | Combined trunk-following mode, separate parked-channel choices, simulcast choice | Phase 2 voice may need WACN/system/NAC context |

NXDN uses FDMA and 4FSK; its 6.25 and 12.5 kHz variants are separate modes. [NXDN Forum overview](https://www.nxdn-forum.com/what-is-nxdn/nxdn-a-brief-overview/). The documented KENWOOD NXDN bit-scrambler programming range is 1–32767. The decoder API additionally accepts zero; that does not imply every radio programs zero as an active key. [KENWOOD NXDN function manual](https://pdfs.kenwoodproducts.com/97/NX-1200_NX-1300_Function.pdf).

The protocol flags, key types and Phase 2 parameter handling were checked against the upstream CLI and the source's `session_args.cpp`, `EncryptionEditor.qml`, protocol directories and Android bridge. [CLI reference](https://github.com/arancormonk/dsd-neo/blob/main/docs/cli.md). Motorola documents that matching privacy material is required for intelligible private calls; basic and enhanced privacy are distinct. [Motorola radio manual](https://www.motorolasolutions.com/content/dam/msi/docs/business/products/_documents/_static_files/mot_mototrbo_dgp_5050-dgp_8050_non-display_portable.pdf).

## Alternatives considered

| Project | Where it fits | Decision for this APK |
|---|---|---|
| DSD-neo | Native Android UI/service plus the requested protocol families | Selected and pinned; no dependence on an external desktop decoder |
| DSD-FME | Mature DSD-derived multi-protocol engine, including NXDN and P25 Phase 2 | Useful reference; would require more Android integration work |
| Original DSD | Foundational digital-speech decoding code | Insufficient starting point for the complete modern Android feature set |
| SDRTrunk | Desktop monitoring/recording and multi-channel workflows | Useful desktop comparison; its documented deployment targets are desktop OSes |
| SDR++ / SDR Touch ecosystem | General receiver, tuning and source frontend | Useful for receiving or supplying compatible streams; not by itself evidence of all requested decoders |

[DSD-FME source and examples](https://github.com/lwvmobile/dsd-fme), [original DSD](https://github.com/szechyjs/dsd), [SDRTrunk project](https://github.com/DSheirer/sdrtrunk). DSD-FME's usage notes also describe limitations of its Phase 2 PSK path, which is one reason to evaluate demodulation quality instead of comparing only feature lists. [DSD-FME usage notes](https://github.com/lwvmobile/dsd-fme/blob/audio_work/examples/Example_Usage.md).

## USB and radio compatibility

**RTL-SDR Blog V3:** the main target. VHF/UHF digital voice uses the tuner path; V3 HF direct-sampling settings are not appropriate for these channels. Leave the bias tee off unless the connected RF accessory requires DC power and is designed for it. [V3 manufacturer guide](https://www.rtl-sdr.com/rtl-sdr-blog-v-3-dongles-user-guide/).

**Blog V4/V4L:** driver currency matters. The chosen source pins librtlsdr 2.0.3 and the upstream 2.9.0 release specifically includes the V4L driver update. A V3-only driver cannot be assumed to support every newer Blog tuner revision. [DSD-neo 2.9.0 release](https://github.com/arancormonk/dsd-neo/releases/tag/v2.9.0), [V4 manufacturer guide](https://www.rtl-sdr.com/V4/).

**Airspy R2/Mini:** the chosen source has a native Android backend, with gain/sample-rate controls distinct from RTL-SDR. This does not cover Airspy HF+ or every product bearing the Airspy name. [Native Airspy documentation](https://github.com/arancormonk/dsd-neo/blob/main/docs/airspy.md).

**HackRF, SDRplay, LimeSDR and others:** no claim of direct Android USB support in this build. They can be used only through a suitable external frontend providing a supported stream. `rtl_tcp` expects RTL-style unsigned 8-bit IQ with its wire protocol; TCP/UDP audio inputs expect the documented demodulated PCM format. Arbitrary raw IQ is not interchangeable with either. Desktop SoapySDR support does not imply it is included in this Android APK. [Android implementation and limits](https://github.com/arancormonk/dsd-neo/blob/main/android/README.md).

The Android USB host flow requests permission and obtains a device connection; the native driver uses the granted descriptor. An app should not attempt to open protected USB device nodes without this flow. [Android USB host documentation](https://developer.android.com/develop/connectivity/usb/host).

## What will improve reception most

These are setup recommendations, not measured results for the user's location:

1. Start with a known strong, clear conventional channel and its correct protocol. This separates source/tuning problems from trunking and privacy configuration.
2. Use an antenna appropriate to the band and try several positions. Place the dongle away from the phone with a short, sound USB extension if local interference is apparent.
3. Compare moderate manual gain with automatic gain. The highest gain can overload an 8-bit receiver and reduce decodability. Favor stable synchronization and fewer decoder errors over a taller spectrum peak. [RTL-SDR gain/overload guidance](https://www.rtl-sdr.com/sdrsharp-users-guide/).
4. Leave squelch off initially. A threshold that clips bursts can prevent acquisition. Apply it only after stable reception is established.
5. Correct a reproducible frequency offset with PPM. Do not use PPM to compensate for being on the wrong channel.
6. Select NXDN48 or NXDN96 explicitly when known. Broad auto-detection must spend time examining multiple rates.
7. On an LSM/CQPSK P25 site, use P25 Simulcast. If audio is still poor, change antenna position or reduce reception of competing sites; software cannot undo every multipath condition.
8. For a trunked P25 system, start on its control channel and enable following. A parked Phase 2 traffic channel can be silent without the necessary network parameters even when RF power is strong.
9. A powered OTG hub can help with receiver power and long sessions. Verify it supports USB data and the phone's host mode; charging behavior is hub/phone-specific.

## Limits and quality criteria

One decoder/tuner follows one selected RF channel at a time. A DMR carrier can contain two slots, but that is not simultaneous monitoring of arbitrary frequencies. While following a voice grant, a single receiver can miss activity elsewhere. No unlimited multi-channel claim is made.

The app includes a spectrum/waterfall, decoder quality indicators, call history, source/talkgroup labeling, importable configuration and foreground audio. Treat FEC success and corrected-error indicators according to their labels; a voice-error count is not automatically a calibrated RF BER measurement. Keys retained by the upstream system store are in app-private storage with Android backups disabled, not hardware-keystore encrypted.

A fair “strongest decoder” benchmark needs the same IQ captures, gain, bandwidth, frequencies and expected calls across candidate engines. Measure valid calls recovered, metadata accuracy, audio intelligibility, false locks, dropped buffers, CPU, thermal stability and battery consumption. For P25, include both C4FM and simulcast recordings; for DMR, both slots and mixed clear/private calls; for NXDN, both symbol rates. This build should not be described as benchmark-winning until those measurements exist.

See `VALIDATION.md` for what was actually checked and `QUICKSTART.md` for installation and receiver setup.
