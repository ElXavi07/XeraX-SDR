# XeraX SDR 4.3.0 protocol coverage

This is the coverage of the pinned DSD-neo engine and XeraX's exposed receive modes, not a claim to decode every radio emission. Implementations are included in the ARM64 and ARMv7 builds; physical-phone over-the-air acceptance remains pending.

| Family | App selection | Configuration and scope |
|---|---|---|
| Analog narrow FM | Analog FM (NFM) / NFM | VHF/UHF voice; CTCSS/DCS, MDC-1200/FleetSync IDs, DTMF and configured two-tone signaling |
| AM | AM aviation | Envelope-demodulated analog voice, standalone reception |
| Broadcast FM | Broadcast FM mono | Wide FM mono reception; no stereo/RDS |
| NXDN | NXDN48; NXDN96 | Separate 4800/9600 bit/s formats; RAN and call signaling; supported supplied-key handling |
| DMR | DMR Tier II; DMR single-slot | Dual-slot and alternate mono decoding; color code, source/destination IDs, supported data/signaling and trunk following with appropriate system setup |
| P25 | Phase 1 + 2; Phase 1 only; Phase 2 voice; Simulcast | C4FM/CQPSK choices, control-channel following and parked voice; Phase 2 needs correct network context |
| D-STAR | D-STAR | Digital amateur voice and supported slow-data handling |
| Yaesu System Fusion | YSF | Implemented digital voice/data frame handling |
| M17 | M17 | RF stream voice and implemented LSF/packet/BERT handling; Codec2 is included |
| dPMR | dPMR | Dedicated 6.25 kHz digital mode; supplied scrambler value where supported |
| X2-TDMA | X2-TDMA | Legacy X2 digital voice decoder |
| ProVoice | ProVoice, in saved-system setup | Parked traffic-channel decoder |
| EDACS / ProVoice | EDACS standard or Extended Addressing; optional ESK 0xA0 | Saved-system setup; correct site variant, AFS settings when needed, and LCN channel map |

The source documents the same digital families in its [project overview](https://github.com/arancormonk/dsd-neo) and [mode reference](https://github.com/arancormonk/dsd-neo/blob/8c9c120389401fc2db3ef52869e13d555712e5fb/docs/cli.md). The release was checked against the pinned source's protocol build files and CLI selectors, rather than assuming every advertised desktop input is available in the Android UI.

## What broad auto detection means

`Auto—all digital` enables the engine's digital candidate frame set and symbol-rate hunting. It is not analog/digital auto switching, universal trunked-site discovery, automatic channel-map generation, or proof that a private call can be decrypted. Known-protocol selections constrain acquisition; EDACS site variants and maps still need explicit setup.

One physical receiver tunes one RF center at a time. Shared reception can feed extra decoders with nearby channels in the same RTL capture window; 4.1.4 adds an experimental four-frequency DMR arrangement. A second dongle supports separate P25 voice reception. DMR's two slots alone do not provide simultaneous unrelated frequencies. Network and replay inputs must use supported formats; RF coverage does not expose every upstream transport or transmit function.

## Outside this build

No added TETRA, paging/POCSAG/FLEX, ACARS/VDL, AIS, ADS-B, satellite/weather image decoder, general HF modem suite, SSB, or stereo broadcast FM decoder. These require separate demodulators/parsers and validation. Version 4.1.5 adds an opt-in experimental NXDN 15-bit scrambler candidate search; see [its scope and evidence](NXDN-SEARCH-4.1.5.md). General unknown encryption-key recovery remains unsupported. A privacy key ID, DMR color code, or talkgroup number cannot substitute for the configured key.

Manufacturer-specific variants and encryption formats require compatible implementations and correct supplied material. No universal interoperability, guaranteed weak-signal performance, or measured "strongest decoder" claim is made.

## ADP and NXDN scrambler in 3.0

ADP/ARC4 is exposed as a 40-bit profile (exactly ten hexadecimal digits) for the engine's P25 Phase 1/2 ALG `AA` and DMR Enhanced Privacy ALG `21` paths. Automatic profiles load the entry matching the received key ID; DMR can also use explicit talkgroup-to-key mappings. The production IMBE/AMBE payload routines were tested with independently generated reference ciphertext, including both DMR and P25 Phase 2 slots. This is not an end-to-end RF or handset audio test.

NXDN's actual 15-bit voice descrambler is used, with decimal supplied values `0–32767`. NXDN48 automatic lookup prefers the received six-bit key ID, then a saved destination mapping. NXDN96 supports the destination mapping or a direct supplied value. An unmatched automatic lookup clears the previous scalar key. Explicitly supplied zero values remain distinguishable from missing entries. Native selection and descrambling fixtures cover these paths. A matched profile is configuration evidence, not cryptographic proof that the key is correct.

## Windows preview 3 validation

Additional independent supplied-key payload tests cover DMR DES/AES-128/AES-256 and NXDN DES/AES-256, including both DMR slots and all 32 NXDN voice frames per established IV period. See [decoder quality and limitations](DECODER-QUALITY.md). This expands software evidence; it does not add universal encryption support or validate on-air IV acquisition.
