# XeraX SDR 4.3.0 — frequency-range scanner

## Start scanning

Open **Explore**, choose USB radio, Airspy or RTL-TCP and enable **Scan a frequency range**.
Enter start/end MHz, choose channel spacing, listening mode and speed, then tap **Start range scan**.
Presets fill 440–450 or 440–460 MHz. For the existing Wi-Fi receiver, keep the working RTL-TCP
host/port. A receiver must be connected and supplying samples; the phone itself is not an RF tuner.

During reception open the session menu's **Scan**, or **Receiver tools → Frequency range scanner**.
Changing between analog and digital modes restarts through the existing receiver/USB-permission
flow so the frontend and audio output use the right format. An unchanged listening mode and
digital-to-digital changes use the live decoder. Existing saved channel-list scanning remains available.

**Hold** stays on a candidate; **Resume** releases it. **Skip** tries the next candidate.
**Avoid frequency** excludes it for this scan session; **Clear avoids** restores excluded channels.
**Save frequency** creates a conventional saved system with its source/host/port and listening mode.
Secrets, key profiles, aliases and trunk maps are not copied into a discovery. Up to 500 unique
findings remain in memory; save desired entries before starting another scan.

## What runs

The scanner uses the actual capture-rate 1024-bin spectrum from the receiver pipeline, independent
of whether the spectrum page is open. It surveys a conservative central 60% of each capture,
evaluating multiple channel-grid positions before tuning to candidates. Empty positions do not each
receive a full decoder dwell. With a 1.536 MHz capture and 12.5 kHz grid, the 801 positions in
440–450 MHz occupy 11 survey tiles; 440–460 occupies 22. Each candidate requires its own tune
and acquisition time. This is sequential reception from one tuner, not simultaneous reception of
the entire range, and survey dwell is a brief observation rather than continuous monitoring.

The grid uses integer Hz, includes the endpoint only when it lies on that grid, and never tunes a
candidate above the endpoint. Supported requested ranges are 24–1766 MHz, up to 50 MHz wide and
10,001 positions, with 5–100 kHz spacing. Actual hardware tuning limits still apply. Capture bandwidth
must resolve at least two FFT bins per channel step; incompatible combinations are refused.

A median nearby-noise estimate, adjacent-bin evidence and at least two distinct FFT observations
qualify activity. This rejects flat noise, invalid numbers and isolated single-bin spikes. It cannot
guarantee that every candidate is a separate transmitter or reject all interference. Noise-floor
estimates and relative dB are not calibrated RSSI or receiver-sensitivity measurements.

The receiver waits for fresh, correctly centered spectrum frames after a tune, including two settling
frames. RTL-TCP receives additional settling time; its protocol does not provide hardware RF timestamps,
so large server/network backlogs can still distort timing. Stale/disconnected sources, rejected commands,
unexpected modes or bandwidth changes stop the scan with an error rather than presenting fabricated
progress. One scanner owns retuning; conflicting trunk/list scanning, workers, tests and recordings are
refused. AI measurement/gain tools and surveys cannot move this scanner's tuner.

## Listening modes and timing

Choose **Auto digital**, **NFM**, **AM**, **DMR**, **P25 Phase 1**, **P25 Phase 2**, **NXDN48** or **NXDN96**.
Auto digital uses the existing native multi-protocol hunt; it does not classify analog voice or invent
a new decoder. A known digital mode normally acquires sooner. NFM/AM gate listening on measured carrier
activity. Digital holds require matching-frequency sync, an active voice call and new nonzero PCM;
sync-only carriers eventually release. Findings distinguish RF-only activity, analog carriers,
digital sync and observed voice output. These indicators do not prove intelligible speech.

Fast/Balanced/Thorough use 120/180/300 ms minimum settling plus matching-frame confirmation;
RTL-TCP adds 180 ms. They require 2/2/3 spectrum observations per tile. Candidate acquisition is
1.2/3/6 seconds for Auto digital and analog, and 0.9/2/4 seconds for a selected digital mode.
The default signal threshold is 10 dB above nearby noise (adjustable 6–30 dB). Resume delay defaults
to 1.2 seconds (300–5000 ms). The default visit cap is 15 seconds, configurable to 5–120 seconds or
0/unlimited; Hold overrides it. A finite cap can leave an ongoing call deliberately to continue searching.
Lower thresholds and longer acquisition can help weak/short signals but make sweeps slower.

Survey/tune phases independently suppress the physical live audio sink. This gate cannot clear
replay/worker suppression or the user's mute. Analog closes this gate as the measured carrier drops;
digital opens it after settling for actual decoder PCM. Existing squelch, privacy, tone/talkgroup filters
and audio routing remain effective. **Stop range scan** releases scan ownership and leaves the receiver
on its current channel. A tuning command already accepted by the backend may still finish.

Conventional range scanning does not reconstruct unknown trunk systems or follow their grants.
P25 Phase 2 still needs usable system parameters. Encrypted traffic still requires the existing
supported key configuration. Fast acquisition may miss short/weak transmissions, and control channels
may produce sync without voice. This update does not guarantee reception, decryption, a scan-speed
number or performance above another receiver.

## Phone and verification scope

No AI, API key, cloud service or PC is required for the scanner itself. RTL-TCP requires its radio server
and network. Scanning continues when its page is closed; its timers and spectrum demand are independent
of the visible spectrum page. Android service/background and screen-off behavior needs device acceptance;
this release has not been tested on a physical S25/Pixel with a radio. It does not restart a range scan
automatically after a killed process. Longer scanning uses more battery than a fixed idle channel.

Host tests run the actual controller and detector with deterministic FFT frames, clock and command
responses. They cover grid coverage, noise/spikes, tune completion, duplicate/stale frames, analog audio
gating, digital voice/tail behavior, holds, skip/avoid, source startup/shutdown, conflicts, errors and
saved-channel credential exclusion. The synthetic blank-sweep result is a scheduling test, not a hardware
benchmark. QML checks cover source routing, invalid input and Spanish layouts at 320 pixels/130% text.
The full existing decoder/audio/API regression suite and both Android release builds are also checked.
