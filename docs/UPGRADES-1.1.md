# XeraX SDR 1.1 — research and implemented upgrades

Research and build date: 22 September 2026. This release improves scanner operation and troubleshooting on the existing native decoder. It does not claim improved demodulator sensitivity or measured superiority over another decoder.

## Why these changes

The first audit found that the engine already includes scan Hold/Next/Avoid, voice-only scanning, scoped keys, per-target modulation/gain, call history, aliases, and P25/DMR/NXDN trunk following. Adding duplicate switches would contribute little. A useful missing Android control was the maximum time spent visiting a target: the engine supported it, but the UI required advanced command-line arguments. A busy system could otherwise occupy the receiver while the rest of the list waited. The limit can interrupt a call, so it must be explicit and optional. [Pinned engine scan design](https://raw.githubusercontent.com/arancormonk/dsd-neo/8c9c120389401fc2db3ef52869e13d555712e5fb/docs/trunk-scan.md).

The hardware has a different constraint: excessive gain can overload a receiver. A software button promising universally stronger decoding would be misleading. The new reception panel therefore explains reported receiver states and offers a manual squelch action, while leaving gain and modulation decisions visible. [RTL-SDR gain guidance](https://www.rtl-sdr.com/sdrsharp-users-guide/), [Blog V3 hardware guide](https://www.rtl-sdr.com/rtl-sdr-blog-v-3-dongles-user-guide/).

## Included in this APK

### Scan timing presets

Open **Home → Scan lists → New/Edit**. Presets apply to list defaults; explicit target overrides remain in effect.

| Preset | Idle dwell | Conventional activity hold | Maximum visit | Voice-only hold | Intended tradeoff |
|---|---:|---:|---:|---|---|
| Balanced | 3 s | 1.2 s | Unlimited | Off | Initial setting for a mixed list |
| Patrol | 1 s | 0.8 s | 15 s | On | More frequent visits; can miss short calls or interrupt a busy call |
| Patient | 5 s | 2 s | Unlimited | Off | More acquisition time; slower return to other channels |

These values are engineering starting points, not RF-benchmarked optimizations. Patient does not amplify a weak signal. Voice-only behavior applies to conventional targets; trunked control-channel handling retains the engine's rules. Voice hang time is separate from these settings.

### A saved maximum visit for each scan list

Under **Advanced → Maximum visit per target**, enter milliseconds:

- Empty inherits the prior global/advanced configuration.
- `0` explicitly removes the default limit.
- `1000` through `3600000` sets a limit of one second through one hour.

The list's explicit value overrides the app-wide extra argument. A target's own options still override that list default. Existing lists without this field preserve their previous behavior. The engine's manual Hold pauses its visit budget; this feature does not force a hop against an operator Hold.

The saved model, CSV validation path, session argument builder and actual QML editor all participate in validation. Dwell/hold values between 1 and 249 ms are now rejected in the editor instead of only when preparing the session. Invalid edits stay visible so they can be corrected.

### Live reception check

While listening, open **Spectrum → Radio → Reception check**. The panel distinguishes:

- Startup or a stopped receiver.
- No incoming RTL samples, including a possible USB/power/network problem or a brief retune.
- Muted audio.
- Enabled squelch without digital frame synchronization.
- Waiting for recognized digital framing, which can simply mean the channel is idle.
- Frame synchronization with or without an active private-call flag.

It displays an SNR estimate only when the engine marks the estimate valid and the source has radio metrics. It does not show stale RF numbers after stop or invent them for an audio input. Airspy is not judged by the RTL-only sample-stream flag. A private-call flag never asserts that a key is missing or incorrect.

**Turn squelch off** sends the existing native command. Rejected commands are reported; a requested change is not presented as verified reception. No automatic gain, PPM or modulation changes run behind the user's back.

## Evaluated for a later release

| Improvement | Value | What is needed before implementation |
|---|---|---|
| Recorded-IQ comparison corpus | Best route to measuring actual weak-signal and simulcast gains | Reference captures for both NXDN rates, both DMR slots, P25 C4FM/LSM and Phase 2, with expected results |
| Thermal/power telemetry | Useful for long phone sessions | Real S25/Pixel tests, baseline battery/temperature measurements and restrained refresh rates |
| Multiple simultaneous channel decoders | Avoids some traffic lost while a single decoder scans | A channelizer, multiple independent decoder/vocoder states, audio policy, USB bandwidth and phone thermal testing |
| Automatic priority revisits | Could reduce latency for selected targets | A clear interruption policy and tests proving it cannot strand a call or corrupt per-system state |

Desktop SDRTrunk demonstrates simultaneous decoding of channels within a tuner's sampled bandwidth. That capability does not automatically exist in this one-decoder Android architecture; it would require substantial engine work. [SDRTrunk manual](https://github.com/DSheirer/sdrtrunk/wiki/User-Manual).

Android exposes thermal status and headroom APIs, but availability and interpretation vary by device. A future thermal feature should report measured status and reduce expendable UI work before altering audio processing. It should not infer a universal temperature threshold or silently sacrifice decoder reliability. [Android Thermal API](https://developer.android.com/games/optimize/adpf/thermal).

## Evidence and remaining limits

See [validation](VALIDATION.md) for build, signing, package and test results. The new tests exercise real model persistence, real session arguments and the actual scan editor. They cover preset selection, save/reload, timing bounds, explicit zero/inheritance, per-list precedence and receiver-status transitions.

The images below are desktop Qt renders of the production components using illustrative test data, not phone screenshots or live reception evidence:

- [Scan-list editor](preview-scanner.png)
- [Visit-limit editor](preview-scan-timing.png)
- [Reception check](preview-reception.png)

Installation, USB stability, received speech, key interoperability, prolonged background operation and RF performance still require physical-device testing.
