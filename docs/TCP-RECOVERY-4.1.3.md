# RTL-TCP recovery in XeraX SDR 4.1.3

Investigation on 22 September 2026 found two separate faults:

1. The Windows RTL-TCP process still listened on 192.168.1.245:1234 but its USB
   connection had failed. A direct probe received the correct 12-byte RTL0
   header and **zero I/Q samples**, while the server logged USB register and
   transfer failures. Restarting the server reopened the dongle. The phone
   reconnected. No driver or firewall changes were needed.
2. The app's TCP reader could exit after an incomplete/delayed header without
   notifying the decoder session. The session could remain alive without
   audio. Reconnects could also block reading a header before applying the
   socket timeout, and continuously unsuccessful reconnects had no deadline.

The native reader now tolerates header fragmentation and temporary receive
timeouts for up to six seconds, using 200 ms receive polling so Stop remains
responsive. This applies to initial connections and reconnects. A failed
handshake publishes a network failure, raises the session stop flag, and wakes
the waiting receiver threads. Repeated reconnect attempts have a 20-second
retry window; an already-started bounded connect/read attempt may finish after
that window. A header-only server failed out in approximately 30 seconds in
the automated regression, instead of leaving a silent session indefinitely.

The Windows helper now includes **Restart**, and the Desktop's **XeraX Wi-Fi
Receiver** folder has a **Restart Receiver** shortcut. Status reports known USB
failure messages. The helper only stops its own recorded process, checking its
executable and creation time. A running/listening process is not reported as
proof of reception.

## Verification

- Production decoder with a synthetic server delaying its header by three
  seconds: nonzero narrow-FM audio, no clipping, expected tone retained.
- Missing, invalid, and prematurely closed headers: receiver exits rather than
  hanging. A server sending a valid header but no I/Q also exits after bounded
  retries.
- The actual attached RTL-SDR, through a fresh localhost server and the PC
  decoder, produced **426,240 PCM samples**, including 424,723 nonzero samples,
  at 162.400 MHz in NFM with squelch off. RMS was approximately 1,498 PCM units.
  This verifies data and audio production, not station identification or phone
  speaker playback. Raw radio audio and I/Q were not saved.
- The initial physical probe's second sequential connection did not receive a
  header in time; that failed measurement was retained and prompted the
  handshake investigation. The fresh-server analog test passed.
- The release verification JSON records the new network tests, full-I/Q
  regressions, application tests, package ABIs and signatures.

## The school channel

The user's screenshot is the Desert Sands Unified School District **DMR
Capacity Plus** system. RadioReference lists four site frequencies: 451.100,
451.850, 451.950 and 452.125 MHz, with LCNs 1–4 respectively. The app's importer
expands Capacity Plus LCNs into two logical slot numbers per frequency. All four
frequencies and the correct mapping matter for following calls.

“No audio is reaching the player” does not establish a speaker failure or
encryption. It means the audio counter did not advance; idle traffic, poor voice
reception, filtering, or a tuning problem still need to be distinguished.
**Check audio → Test sound** checks the selected phone output independently.
Actual school voice reception and the handset speaker remain unverified.

[RadioReference system 13121](https://www.radioreference.com/db/sid/13121)

## Installation

Install the ARM64 APK on Galaxy S25 / Pixel 9 Pro, or the armeabi-v7a APK on a
32-bit Android phone. Android 10+ is required. Install as an update to retain
settings. Select RTL-TCP at **192.168.1.245:1234** on this home network.
