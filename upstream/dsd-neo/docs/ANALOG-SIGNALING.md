# XeraX analog signaling

`src/platform/analog_signaling.cpp` uses eight AFSK timing phases, 1200/1800 Hz tone energy and raw/NRZI framing on the NFM audio stream. MDC-1200's 40-bit sync and 16-column/7-row deinterleaver lead to a mandatory CRC over the information bytes. FleetSync uses its two supported sync patterns, CRC-15 and even parity; an extended fleet block also needs its own valid CRC. IDs are published only after these checks. A bounded queue retains the latest 100 events for the UI.

Field layouts, CRC parameters and MDC deinterleaving were adapted from [SDRTrunk](https://github.com/DSheirer/sdrtrunk/tree/80360029efb008dca993938d1e34ad4a7a8c15bd), Copyright (C) 2014–2018 Dennis Sheirer, GPL-3.0-or-later. The project retains GPL-3.0-or-later licensing and includes the GPL text. The [MDC reference](https://kr8mer.github.io/eas-station/reference/protocols/MDC1200/) was also consulted for CRC verification.

DTMF uses independent row/column Goertzel powers, dominance/twist checks and two consecutive 20 ms windows. Two-tone paging is an explicitly configured ordered pair, with 300–3000 Hz tones and 100–5000 ms minimum durations. It does not guess a paging-plan name.

Host tests generate actual AFSK/NRZI waveforms for independent known MDC and FleetSync codewords and reject corrupt CRCs; all 16 DTMF symbols, single-tone/noise rejection and reversed paging tones are checked. This implementation does not perform MDC convolutional-error repair, FleetSync GPS/extended message decoding, or guarantee decoding through every radio's pre-emphasis and timing distortion. Over-the-air validation remains pending.
