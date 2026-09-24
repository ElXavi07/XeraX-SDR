# XeraX SDR 4.3.0: complete feature guide

This inventory describes included software, not certification of hardware interoperability or reception quality. Historical version guides retain their original evidence and limits; this page describes the combined release.

## Reception and decoding

| Module | Included behavior | Configuration / limit |
|---|---|---|
| Analog NFM | Narrowband FM speech, filtering/level handling, squelch and analog scan activity | Select NFM explicitly; digital Auto does not play analog |
| AM | Analog AM voice, including aviation-style listening | Separate analog mode |
| Broadcast FM | Wide FM mono demodulation | No stereo or RDS |
| NXDN48 / NXDN96 | Native decoding, RAN/call signaling and compatible supplied scrambler handling | Separate rate selections; vendor/system interoperability needs testing |
| DMR | Tier II dual-slot and alternate single-slot decoding, color code, slot, source/destination IDs and supported signaling/trunking | Correct system/channel configuration required |
| P25 | Phase 1/2, C4FM/CQPSK/LSM choices, configured control following and parked voice | Phase 2 requires appropriate network/slot context |
| Additional families | D-STAR, YSF, M17/Codec2, dPMR, X2-TDMA, ProVoice, EDACS standard/Extended Addressing and ESK options | Some choices require saved-system setup; EDACS requires a correct LCN map |
| Digital acquisition | Existing multi-protocol frame and symbol-rate hunt | Known-mode selection is often preferable; no neural RF classifier |
| IDs and aliases | Radio/contact aliases, talkgroups and channel maps | Metadata alone does not establish intelligible audio |

[Protocol details](PROTOCOLS.md)

## Scanning and navigation

| Feature | Included behavior |
|---|---|
| Range scanner | Wideband FFT surveys followed by candidate tuning; start/end MHz, 5–100 kHz steps and 440–450 / 440–460 MHz presets |
| Range bounds | Requested range 24–1766 MHz, maximum 50 MHz span and 10,001 positions; receiver limits still apply |
| Timing | Fast/Balanced/Thorough, relative signal threshold, acquisition dwell, resume delay and visit cap |
| Live controls | Hold/Resume, Skip, temporary Avoid/Clear avoids and Save frequency |
| Discovery evidence | RF activity, analog carrier, digital sync and observed voice distinguished; up to 500 findings in memory |
| Scan lists | Saved systems/explicit channels, mixed NFM/digital lists, priority rotation, dwell/hold/hang settings, finish-active-call option and per-target settings |
| Spectrum | Waterfall, peak selection, fine swipe tuning with preview, 6.25/12.5/25 kHz steps, zoom and view panning |
| Band survey | Repeated grid visits, sampled occupancy, timestamps, qualified protocol labels, listen/save and restore on stop |
| Nearby sites | Distance-based selection/rotation of eligible saved sites; coordinates and radius configuration required |
| Navigation | Listen, Scan, Calls and Tools, with session shortcuts |

One tuner observes portions of the band sequentially and can miss brief transmissions. The scanner does not reconstruct unknown trunking maps. [Range scanner](RANGE-SCANNER-4.3.0.md)

## Receiver and signal tools

| Feature | Included behavior |
|---|---|
| Inputs | RTL USB, RTL-TCP, Airspy R2/Mini USB, experimental HackRF One RX, supported PCM/file inputs |
| USB check | Device IDs, known-driver status, permission state and permission retry |
| Calibration | Automatic PPM estimator with waiting/locked status; saved manual −200 to +200 ppm where supported |
| Quality | Available SNR, sync losses, control-frame results, clipping and player underruns; unavailable evidence remains explicit |
| Measurement | Fixed-channel reception measurement over 30 seconds |
| Gain trials | Opt-in bounded comparison, ownership/call guards and restoration when evidence is worse or insufficient |
| Site trials | Eligible saved sibling-site comparison, call/hold protection and rollback |
| Filters | Frequency, CTCSS/DCS, DMR color code/slot and talkgroup gates |
| Notebook | Consistent observations, save as conventional preset and JSON export |
| I/Q capture | Local native samples plus metadata, duration/size bounds and compatible replay export |
| I/Q lab | Pinned synthetic fixtures, actual native replay, payload/FEC/PCM evidence and exportable reports |
| Saved-signal comparison | Bounded mode/offset/filter trials; P25 C4FM/CQPSK/equalizer comparisons |
| Experimental equalizer | Optional adaptive CQPSK filter with bypass/A-B comparison; no demonstrated general reception improvement |
| Nearby receivers | Extra decoder workers in the same RTL capture, frequency translation/filtering and individual recordings/audio selection |
| Four-channel DMR | Experimental four DMR frequencies within one 1.536 MS/s RTL capture, 192 kS/s workers and automatic audible-output selection |
| Two-dongle P25 | Separate control/voice RTL receivers; native voice-grant/context updates without reopening the voice engine |
| Health/recovery | Battery/saver/thermal reporting, thermal limits on extra processing, source errors, bounded network reconnect and optional same-device USB recovery |

Only one receiver output is audible at a time. Shared reception does not cover arbitrary distant frequencies. USB power, throughput, heat and background recovery need device tests. [Receivers](RECEIVERS-4.1.2.md) · [Shared reception](RECEPTION-4.1.4.md) · [TCP recovery](TCP-RECOVERY-4.1.3.md)

## Audio, signaling and recordings

| Feature | Included behavior |
|---|---|
| Routing | Phone speaker, system default and available Android outputs; requested versus reported route |
| Recovery | Restore speaker audio, audio-focus retry and native test tones |
| Diagnostics | Distinguishes missing PCM, silence, mute, focus loss and output acceptance |
| Replay | Last 30/60 seconds while reception continues; live speaker temporarily suppressed |
| Recordings | Digital per-call WAV/metadata and analog activity-segmented WAVs |
| Library | Search, favorites, retention, playback and WAV/JSON export to an Android-selected folder |
| Analog signaling | CTCSS/DCS, CRC-checked MDC-1200/FleetSync IDs, DTMF and configured two-tone sequences |
| Activity alerts | Talkgroup/radio-ID notifications with rate limits and Android permission |
| Background controls | Foreground-service controls for listening, hold/next/mute/speaker/stop where available |

Android may decline an output route. Nonzero PCM does not prove intelligible speech. [Audio guide](AUDIO-4.1.1.md)

## Imports, configuration and languages

- RadioReference conventional and supported trunked-system imports; county/category/system-ID browsing and site selection.
- Indio/Coachella Valley shortcut and 50-mile site-selection aid. Database coordinates are not guaranteed tower positions or coverage.
- Users supply their own entitled RadioReference account. Account passwords are not compiled into the app. The released APK carries the approved project application key; source builds can supply their own.
- Contact aliases, maps, talkgroups, receiver profiles, local site plot and portable configuration backups.
- English/Spanish selection without restarting reception; 878 translations checked in 4.3.0. Some inherited technical strings and imported labels remain untranslated.
- Configuration, observations and recordings remain local unless exported or used by a network feature.

## Radio privacy handling

| Feature | Scope |
|---|---|
| DMR Basic Privacy | Configured decimal values 0–255 |
| NXDN scrambler | Supplied values 0–32767; direct profiles, supported key-ID/destination lookup and stale-key clearing |
| ADP/ARC4 | Supplied 40-bit profiles; compatible P25 ALG AA and DMR ALG 21 paths, ID/talkgroup mappings |
| P25 AES/DES | Compatible supplied material and native payload paths; independent payload-vector checks |
| Other formats | Existing engine-compatible profiles; no universal vendor compatibility claim |
| DMR RAS | Explicit compatible RAS handling option; RAS is not encryption |
| Experimental NXDN search | Opt-in 15-bit scrambler candidate search with two separate voice-pattern matches before applying a candidate |

A matching key ID selects stored material; it does not prove the key is correct. NXDN search has synthetic evidence, with scrambled-radio acceptance pending. It does not guarantee a result or provide general unknown-key recovery for P25/DMR encryption. [NXDN scope](NXDN-SEARCH-4.1.5.md) · [Profiles](UPGRADES-3.0.md) · [P25 checks](UPGRADES-4.1.md)

## Optional AI investigations

- Disabled by default; OpenAI or DeepSeek using the user's key.
- Authenticated model discovery and function-call compatibility check.
- Android Keystore-backed encrypted provider-key storage; session-only fallback if secure saving fails.
- User-started plain-language investigations using sanitized numerical diagnostics.
- Actual local tools: 30-second measurements, bounded gain trials and comparison of a selected local I/Q capture.
- Per-run experiment controls, cancellation, bounded tool calls and adjustable daily request count.
- Radio audio, I/Q, radio keys, account credentials, GPS, raw logs and file paths are excluded from the AI diagnostic payload. User questions are sent as entered.
- RF/DSP remains on the phone; model inference runs at the provider over HTTPS. No developer AI key or offline language model is bundled.

AI adds no new demodulator, universal decoder or encryption-key recovery. Provider/model access and live calls need acceptance testing. [AI guide](AI-4.2.0.md)

## Testing and limits

4.3.0 records **33 host test groups, 80 QML cases and 878 translation checks**, Android release builds/lint for both ABIs, signature verification and source/native matching. ARM64 native segments meet 16 KB alignment checks; ARMv7 passes its corresponding 32-bit ABI/alignment checks. Earlier reports include synthetic I/Q, payload, transport and DSP tests; these are separate scopes, not a combined hardware score.

No completed physical S25/Pixel/ARMv7 acceptance or comparative SDS100 benchmark is claimed. Live RadioReference/AI accounts, real speech, thermal/battery load, screen-off scanning and interoperability need community testing. Recovery after reboot, force-stop or process death is not guaranteed.

Not included: TETRA, POCSAG/FLEX, ACARS/VDL, AIS, ADS-B, satellite/weather images, general HF modems, SSB or stereo/RDS. Experimental features are not proof of universal decryption or improved sensitivity.

[Verification](../releases/4.3.0/verification.json) · [Phone acceptance](PHONE-ACCEPTANCE.md) · [Contributing](../CONTRIBUTING.md)
