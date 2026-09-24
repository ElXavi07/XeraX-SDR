# XeraX SDR 3.0.0

Open **Receiver tools** from the listening screen or Settings. Four sections keep the controls together: **Quality**, **Channels**, **Clips**, and **More**. Tabs use two rows on narrow screens or with larger text. Forms scroll above the on-screen keyboard.

## The eight improvements

| Improvement | Where and behavior |
|---|---|
| Decode quality | Quality shows 30-second control-frame successes/failures, synchronization losses, player underruns, input clipping and available SNR. A percentage requires at least eight published control frames; unavailable measurements are explicit. These counters do not rate speech intelligibility. |
| Automatic gain | Quality → Try automatic gain. On a steady RTL channel, measure a baseline, try a bounded gain change, then keep it only with better measured evidence. Calls pause measurement; a failed comparison restores the old gain. Manual changes take priority. Trials have a two-minute cooldown. Airspy, scan lists and controller-owned tuning are excluded. |
| Raw signal capture | Clips → Capture current signal. Restart a single-channel RTL USB, rtl_tcp or Airspy session to collect native I/Q and tuning metadata. The UI restores the original session after 20 running seconds; native recording always has a 64 MB cap. Stop listening before exporting a TAR containing both `.iq` and `.iq.json`. |
| Channel filters | Channels accepts an exact frequency with CTCSS or DCS, DMR color code/time slot, and talkgroup ID. Blank means unrestricted. A missing or mismatched required tone/code keeps audio closed. Use at least three seconds of scan dwell for tone acquisition. Raw recordings retain the original signal. Imported database tone labels are not automatically enabled as audio gates. |
| Discovery notebook | Channels → Remember discoveries stores up to 500 local observations after three consistent observations. Frame synchronization and unconfirmed energy are distinguished. The newest 30 appear on screen; JSON export contains all entries. Save an observation as a listening preset, not a generated trunking definition. |
| Replay while receiving | Clips or the monitor's Replay button plays the latest 30/60 seconds while decoding, scanning, buffering and configured recording continue. The live speaker stream is temporarily suppressed; playback returns to live when finished. WAV export remains available. Silent gaps are omitted. |
| Automatic site trials | Quality → Choose sites automatically. Uses eligible saved sibling sites in the same RadioReference system and with matching source/protocol settings. Calls and manual holds prevent switching. After sustained poor evidence, restart at a candidate, compare for about 35 seconds, then keep a measured improvement or return to the original site. Five-minute trial cooldown. No GPS roaming or discovery of unsaved sites. |
| Audio recovery | Quality → Audio help distinguishes no received audio, mute, media volume zero, audio focus loss, replay, source errors and output-route warnings. Speaker, system-output and retry controls are explicit. Android may decline a requested route; verify the reported output. |

Automatic gain/site trials are opt-in for the current UI session. Their timers and the 20-second capture return require the UI lifecycle to remain alive. If Android destroys the activity during capture, the native 64 MB recording bound remains, but automatic return to the old session is not guaranteed. Free-space checks require 150 MB before starting capture. Multiple captures consume additional storage.

## English and Spanish

Use **Settings → Language / Idioma**, or **Receiver tools → More**. The language updates without restarting reception and is remembered. The catalog contains 437 translations covering the new tools, main navigation, common settings and key guidance; Android notification actions also follow the selection. Some older advanced screens, technical diagnostics, externally supplied errors and database labels remain in their original language. This is not a claim that every inherited upstream string is translated.

## ADP/ARC4 and automatic supplied keys

For one fixed key, use **More → Create ADP / ARC4 profile**. Enter exactly ten hexadecimal digits, including leading zeros, then assign the saved profile under the system's **Decryption keys**. P25 Phase 1/2 uses ALG `AA`; DMR Enhanced Privacy uses ALG `21`. The app uses the engine's existing native cipher and IMBE/AMBE processing paths.

For several supplied keys, use **More → Set up automatic P25 / DMR keys**. Add the received key ID and its corresponding material to the managed collection, save it, and assign the profile to the system. Choose a P25 or DMR profile when those systems use different values for the same ID. P25 IDs are up to `FFFF`; DMR IDs are `00–FF`. Explicit DMR talkgroup mappings are also available in the profile editor. A profile match selects saved material; it does not establish that the material is correct. The decoder does not brute-force or discover unknown keys.

For NXDN, use **More → Set up NXDN scrambler keys** and add decimal scrambler values `0–32767`. NXDN48 can use received key IDs `00–3F` in hex, with a destination mapping as fallback. NXDN96 uses a configured destination mapping or a direct scrambler profile. Destination IDs are decimal and at most 65535. Unmatched automatic lookups clear the previous scalar key instead of reusing it. A direct profile continues using its explicitly configured value. Zero-valued saved scalar keys remain distinct from missing entries.

## Evidence and remaining device work

The native ADP payload transformations are checked against independent PyCryptodome 3.23.0 reference ciphertext for P25 Phase 1, P25 Phase 2 and both DMR slots. The NXDN fixture uses the pinned engine's fixed LFSR vector through its production voice-transform routine. Separate tests exercise the actual NXDN element key loader, missing-key clearing, destination fallback, direct overrides, zero values and slot isolation. These tests exercise real production code rather than an imitation decoder, but stop short of RF acquisition and audible output.

No Galaxy S25, Pixel 9 Pro, SDR, real encrypted test recording or live RF path was exercised in this workspace. Complete [phone acceptance](PHONE-ACCEPTANCE.md) before considering this production ready. Reception depends on the antenna, tuner, RF environment, system parameters and compatible supplied material. No claim of perfection or measured superiority over other receivers is made.

Implementation references: pinned [DSD-neo CLI and protocol options](https://github.com/arancormonk/dsd-neo/blob/8c9c120389401fc2db3ef52869e13d555712e5fb/docs/cli.md), Android [audio focus](https://developer.android.com/media/optimize/audio-focus) and [MediaPlayer routing](https://developer.android.com/reference/android/media/MediaPlayer), and Qt [runtime retranslation](https://doc.qt.io/qt-6/qqmlengine.html#retranslate).
