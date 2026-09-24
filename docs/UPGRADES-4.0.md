# XeraX SDR 4.0.0

This version implements the ten requested upgrades. It is a signed Android test release for device evaluation; multi-receiver USB reception, handset audio and Android lifecycle behavior still require physical acceptance on the Galaxy S25 and Pixel 9 Pro.

| Upgrade | What is implemented | Where to use it |
|---|---|---|
| I/Q regression lab | 13 pinned, hash-verified replay cases through the actual native receive chain; expected payload checks, P25 FEC counts, PCM output size, persistent/exportable reports | Tools → Receiver lab → I/Q lab |
| Simultaneous nearby channels | Two independent decoder processes fed by frequency-shifted copies of the main RTL CU8 capture; bounded queues, error reporting, individual audio selection and recordings | Receiver lab → Receivers |
| Two-dongle P25 trunking | The main decoder applies its normal grant policy and stays on control; a separately selected USB RTL-SDR receives admitted Phase 1/2 voice grants, including TDMA network/slot context | Receivers → Two-dongle P25 trunking |
| Simulcast equalization | Optional seven-tap adaptive CMA filter before CQPSK timing recovery; bypass and identical-capture A/B tests | I/Q lab → Experimental simulcast equalizer |
| Saved-signal reprocessing | Bounded actual DSP trials of C4FM/CQPSK, ±250 Hz offset and 6/12 kHz filters; CQPSK equalizer trial; comparison reports | I/Q lab → Reprocess a saved signal |
| Analog signaling | CRC-checked MDC-1200 and FleetSync IDs, 16 DTMF digits and a configurable two-tone sequence from NFM audio; bounded event history | Receiver lab → Signaling |
| Recording library | Digital per-call WAV/metadata plus squelch-segmented analog recordings; search, favorites, retention, playback and Android folder export | Calls → Recordings |
| Location-aware scanning | Distance-ordered saved sites, Indio or current location, radius/accuracy eligibility and 30-second rotation; calls and holds prevent switching | Scan → Nearby |
| Band activity survey | Frequency grid with repeated dwell, sampled occupancy, timestamps, evidence-qualified protocol labels, listen/save actions and restore on stop | Scan → Band survey |
| Background resilience | Service-owned 20-second capture deadline, UI reattachment, optional same-device USB reconnection, audio route/focus propagation and thermal stop for extra processing | Receivers → Background reception |

## Use

The home navigation is **Listen / Scan / Calls / Tools**. While receiving, the session menu also opens Scan, Calls and Tools. The receiver-tools shortcut opens the lab. English and Spanish update without restarting; the reviewed catalog contains 599 entries. New pages were tested at 320 logical pixels with 130% text size.

For shared reception, start one fixed USB RTL-SDR or rtl_tcp channel with a **48 kHz base bandwidth**, then add receiver 2 or 3 close to it. Each worker currently receives the full capture rate and performs its own DSP; this is more demanding than a polyphase channelizer. The accepted shared window is deliberately conservative. Airspy sharing and separate distant frequencies from one dongle are not supported. Moving the main tuner, unequal capture rates or a lagging worker stops that worker with an error. Only one receiver is audible at a time. Phone speaker and other output choices apply to workers too; replay/focus loss suppresses their live audio.

For two-dongle operation, select a second RTL-SDR through the USB picker, grant access and start a saved P25 trunked system on the main receiver before arming voice. Use adequate USB power. Voice grants currently restart the voice engine rather than retuning a continuously running voice DSP, so the opening of a call may be missed. The busy-call guard can hold a voice receiver for up to 30 seconds. This mode is P25 only. It needs hardware testing; desktop grant-context tests do not validate a USB hub or actual trunked traffic.

Enable per-call recording before starting the relevant receiver. Analog recordings use received squelch activity, a one-second hang and five-minute file segments. An open squelch can record noise. Metadata appears only after WAV close; active recordings are excluded from cleanup. Favorites survive retention. Export writes both WAV and JSON to the folder you select. The visible list starts with 50 matching calls and loads more on request.

Nearby rotation and band surveys run while the app is in the foreground. Surveys restore the original frequency when the app goes to the background. The primary decoder and worker engines are service-owned. Location does not measure RF coverage; rows without coordinates are excluded from automatic geographical selection. A survey samples visits rather than continuously watching the whole band, so short transmissions may be missed. Protocol confirmation currently uses the available P25 FEC telemetry; other signals may stay unconfirmed despite measurable energy.

USB recovery is opt-in, waits at most one minute, and needs the same VID/PID/serial and existing Android USB permission. A killed process loses in-memory receive arguments and supplied key material; this release does not promise unattended recovery after process death, reboot or force-stop. Android may still impose OEM/background restrictions.

## Evidence and limits

The 30 host full-I/Q regression cases pass. All 13 app-lab cases pass through the host parity runner, and four additional offset/filter trials complete. Six voice fixtures produce nonzero PCM samples. These are reproducible synthetic fixtures, not a speech-intelligibility comparison against real radios. P25 Phase 2 in the I/Q lab checks control/SACCH evidence; its existing privacy tests operate at the voice-payload level.

With both runs forced to CQPSK, the bundled simulcast case produces **52 accepted / 0 rejected P25 FEC frames** with bypass and with the equalizer enabled. This does **not** demonstrate improved reception. The equalizer remains experimental and off by default. The modulus-error display is not a decoding-success metric.

The 27 application test groups pass, including the actual analog AFSK parsers, CRC rejection, DTMF/two-tone detection, recording WAV construction, retention protection, shared-channel frequency translation, DSP trials and P25 grant context. The QML runner passes 66 cases. Android service/IPC/SAF behavior is compiled and linted but still needs device execution. See [phone acceptance](PHONE-ACCEPTANCE.md) and [validation](VALIDATION.md).

The existing supplied-key privacy implementations remain. A received key ID selects a saved mapping; it is not proof that a supplied key produces correct voice. The app does not recover unknown keys or decode every possible emission. See [protocol coverage](PROTOCOLS.md).
