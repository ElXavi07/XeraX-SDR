**XeraX SDR: decoder selection and reception improvements**

Research checked on 22 September 2026. Baseline: XeraX SDR 4.1.3, DSD-neo source snapshot `8c9c120389401fc2db3ef52869e13d555712e5fb` plus the existing XeraX changes. Targets: Galaxy S25, Pixel 9 Pro, and the separately built ARMv7 edition.

**Recommendation:** retain DSD-neo as the native Android engine, compare its P25 output against OP25 and SDRTrunk, compare DMR trunk handling against SDRTrunk, and evaluate DSDcc selectively for conventional DMR/NXDN/amateur modes. Use dedicated libraries for genuinely new formats. The largest practical improvements are continuous observation of a site's channels, reliable call acquisition, and measured recovery of intelligible speech.

“Best fit” below is an engineering recommendation based on documented scope, integration cost and current XeraX evidence. It is not a measured sensitivity ranking. This research did not run competing decoders against a common RF recording, install another decoder, or change the APK. The proposed additions remain unimplemented.

The phone test tones now work. School-system radio audio is still unverified. Network connectivity, decoded signaling, synthesized samples and intelligible received speech are distinct milestones.

**What the present build already has**

The local source passes soft confidence values into IMBE/AMBE frame decoding in [dsd_mbe.c](../upstream/dsd-neo/src/core/vocoder/dsd_mbe.c#L157); Phase 2 also contains ranked soft-erasure recovery. This is already substantive decoding code. Automatic/manual PPM, gain trials, supplied-key profiles, I/Q replay, experimental equalization, two extra nearby receivers and two-dongle P25 operation also already exist. Improvements must extend or validate these paths rather than relabel them as new features. See the [local protocol inventory](../docs/PROTOCOLS.md), [4.1 changes](../docs/UPGRADES-4.1.md) and [4.1.3 verification](TCP-RECOVERY-4.1.3.md).

The verification record reports 30 full-I/Q cases. Its Phase 2 I/Q coverage includes control/SACCH; separate tests cover voice payload operations. Neither those tests nor nonzero PCM alone establish real speech intelligibility. The experimental equalizer's short synthetic comparison is insufficient to establish a general improvement. These are the most important evidence gaps to close.

**Recommendations for every existing receive family**

| XeraX module | Recommended native path and comparison | Highest-value next work |
|---|---|---|
| P25 Phase 1, C4FM | Retain DSD-neo; compare the same I/Q with OP25 and SDRTrunk. | Measure acquisition time, complete calls and the first intelligible word; test fading, frequency error and false locks. |
| P25 Phase 1, CQPSK/LSM simulcast | Retain the current CQPSK path; use OP25 and SDRTrunk as comparison receivers. | Compare timing/carrier recovery and equalizer bypass across realistic delayed paths. Keep changes only when they improve held-out recordings. |
| P25 Phase 2 | Retain DSD-neo; prioritize an OP25/SDRTrunk comparison. | Add complete RF-to-speech tests for both slots, correct WACN/SYSID/NAC context, late entry, slot changes, call ends and reacquisition. |
| DMR Tier II conventional | Retain DSD-neo; compare SDRTrunk and DSDcc where their supported mode matches. | Independently verify both slots, repeater/direct mode acquisition, color code, source/destination IDs and speech continuity. |
| DMR trunked variants | Retain the existing engine; use SDRTrunk as the first Capacity Plus comparison and DSD-FME as an implementation reference. | Validate each site's LCN/LSN mapping; test moving rest channels, simultaneous calls, stale assignments and return from voice. Treat Cap+, Con+, Tier III/CapMax and XPT as separate acceptance cases. |
| NXDN48 | Retain DSD-neo; compare DSD-FME and SDRangel/DSDcc. | Test the 2400-symbol/s path on weak short calls, RAN filtering, complete speech and the relevant trunking variant. |
| NXDN96 | Retain DSD-neo; compare DSD-FME and SDRangel/DSDcc. | Independently test the 4800-symbol/s path and applicable channel assignment; do not infer performance from NXDN48 results. |
| dPMR | Retain DSD-neo; evaluate DSDcc as an alternate receive path. | Verify actual voice, IDs, polarity handling and narrow-channel acquisition using known recordings. |
| D-STAR | Retain DSD-neo; compare DSDcc. | Test GMSK acquisition, valid headers, slow-data text and AMBE speech; keep header validity separate from audio quality. |
| Yaesu System Fusion | Retain DSD-neo; compare DSDcc for the supported voice/data modes. | Build fixtures per voice mode, validate FICH/data handling, and avoid generalizing one passing mode to the entire family. |
| M17 | Retain DSD-neo with Codec2; use the M17 project's libm17 as an RF reference. | Compare soft FEC, LSF/stream/packet handling, CRC rejection and recoveries. Codec2 is the voice codec; libm17 supplies RF framing/FEC building blocks. |
| X2-TDMA | Retain DSD-neo; use DSD-FME as a related reference. | Obtain representative recordings and test slot/audio boundaries. The benefit of a separate port is currently unestablished. |
| EDACS / ProVoice | Retain DSD-neo; compare DSD-FME for applicable variants. | Test EDACS channel maps and control following separately from ProVoice speech, including return to control and site variants. |
| Analog NFM | Retain the working native demodulator; compare noise-squelch behavior with OP25's documented analog path. | Add noise-based squelch with hang time and optional speech detection, calibrated against missed weak speech and unwanted openings. Preserve the signaling tap before voice processing. |
| Analog AM | Retain the native path; evaluate selective DSP changes using liquid-dsp. | Measure adjacent-channel rejection, AGC recovery, clipping and intelligibility on aviation speech. |
| Broadcast FM | Retain mono reception; evaluate stereo decoding and redsea for RDS. | Preserve a sufficiently wide multiplex signal for stereo/RDS; the current speech/mono output is not a substitute for the multiplex input. |
| Supplied-key privacy handling | Retain the tested native paths. | Expand known-key interoperability tests by protocol/vendor, including missing/wrong keys and call transitions. Key-ID matching alone does not prove correct decoding; stronger RF decoding does not recover an unknown encryption key. |

The project documentation establishes the candidates' protocol scope: [DSD-neo](https://github.com/arancormonk/dsd-neo), [OP25](https://github.com/boatbod/op25), [SDRTrunk release notes](https://github.com/DSheirer/sdrtrunk/releases), [DSD-FME usage](https://github.com/lwvmobile/dsd-fme/blob/audio_work/examples/Example_Usage.md), [SDRangel's DSDcc plugin](https://github.com/f4exb/sdrangel/blob/master/plugins/channelrx/demoddsd/readme.md), [libm17](https://github.com/M17-Project/libm17) and [redsea](https://github.com/windytan/redsea). The improvement priorities in the table are my proposed engineering work.

**What each candidate contributes—and what it would take to use it**

| Candidate | Evidence from its maintainers | Proposed role in XeraX |
|---|---|---|
| DSD-neo | Native C/C++, broad protocol coverage, packaged Android support and symbol-domain SDR input. | Keep as the default engine. Pin and test updates; its documentation identifies ongoing stabilization. [Source](https://github.com/arancormonk/dsd-neo) |
| OP25, boatbod fork | P25 conventional/trunking, both phases, TDMA control channels, automatic fine tuning and concurrent receiver operation. Its current build notes use GNU Radio 3.10. | Strong P25 comparison candidate on a Linux host. A standalone Android port would require substantial extraction/integration; Linux ARM support is not an Android APK. [Capabilities](https://github.com/boatbod/op25), [build notes](https://github.com/boatbod/op25/blob/master/README-gr3.10) |
| SDRTrunk | Desktop Java application with P25/DMR support and multiple tuners/channels. Its release history explicitly addresses Capacity Plus rest-channel rotation and Phase 2 chopped audio. | First desktop comparison for the school system and P25 call handling. Reuse documented behavior and tests through a deliberate port or remote bridge. Its distributed desktop runtime is not an Android component. [Releases](https://github.com/DSheirer/sdrtrunk/releases), [Cap+ fix](https://github.com/DSheirer/sdrtrunk/pull/1798), [Phase 2 audio fix](https://github.com/DSheirer/sdrtrunk/pull/1904) |
| DSD-FME | Broad digital modes and trunking; its notes document limits and quirks, including Capacity Plus rest-channel hunting. | Useful compatibility reference. It shares ancestry with DSD-neo, so agreement is not wholly independent validation and a wholesale replacement has no proven benefit. [Source](https://github.com/lwvmobile/dsd-fme), [usage notes](https://github.com/lwvmobile/dsd-fme/blob/audio_work/examples/Example_Usage.md) |
| DSDcc | A C++ decoder library with sample-push integration. SDRangel documents DMR, NXDN, dPMR, D-STAR and YSF use. | Plausible selective NDK port and alternate demodulation comparison. Its own overview has stale NXDN wording; the integration documentation and source include NXDN. No P25 Phase 2 replacement is established here. [Library](https://github.com/f4exb/dsdcc), [integration documentation](https://github.com/f4exb/sdrangel/blob/master/plugins/channelrx/demoddsd/readme.md) |
| DSDPlus | The official site published a newer public release on 4 December 2025. Its downloaded Notes.txt documents digital voice/trunking including NXDN, DMR and P25 I/II. | Useful optional Windows comparison. No embeddable Android SDK or redistribution basis was established in this research. The official site says new Fast Lane memberships are closed; do not build the plan around purchasing one. [Public release](https://www.dsdplus.com/a-new-public-release-is-here/), [program change](https://www.dsdplus.com/fast-lane-news/) |
| mbelib-neo / JMBE | mbelib-neo offers native IMBE/AMBE decoding with soft-frame APIs; JMBE offers Java MBE audio conversion. | Keep mbelib-neo and compare identical decoded payloads through JMBE where the codec matches. This separates vocoder quality from RF acquisition. Do not promise that swapping vocoders fixes missing frames. [mbelib-neo](https://github.com/arancormonk/mbelib-neo), [JMBE](https://github.com/DSheirer/jmbe) |
| liquid-dsp | Embedded-oriented C DSP with filters, resamplers, synchronization, equalizers and channelizers; MIT/X11 license. | Evaluate individual DSP components. It is not a complete P25/DMR decoder. NDK suitability is an engineering inference, pending builds and numeric parity tests on both ABIs. [Source](https://github.com/jgaeddert/liquid-dsp) |

For any incorporated component, pin the source revision, examine its actual file/dependency licenses and include the required corresponding source/notices. A desktop process bridge is an integration choice, not an assumed exemption from distribution terms. No external decoder binaries were executed during this research; the DSDPlus archive was inspected in memory for its documentation.

**The most promising substantial addition: watch the entire school site**

RadioReference lists four Capacity Plus carriers: 451.100, 451.850, 451.950 and 452.125 MHz. Their center-to-center span is **1.025 MHz**. The midpoint is **451.6125 MHz**. With an ideal 1.536 MS/s complex capture centered there, the outer carrier centers sit 512.5 kHz from center and 255.5 kHz inside each sampled band edge. This is arithmetic feasibility, not a demonstrated operating configuration. Actual tuner bandwidth, capture offset, anti-alias transition bands, interference and sample continuity still matter. [RadioReference system](https://www.radioreference.com/db/sid/13121)

Proposal: one fixed wideband capture feeds four channel decoders, each tracking its two DMR slots. Keep observing rest-channel information while calls occur on other carriers. A common call manager chooses the audible talkgroup and can record other calls within a resource budget. This avoids some single-tuner retuning gaps. It cannot monitor frequencies outside the capture window.

The current XeraX limit is a main decoder plus two extra workers, with one audible receiver. It therefore does not already provide this complete four-carrier arrangement. Start by benchmarking four per-channel downconverters against a shared polyphase filter bank. For only four channels, a filter bank is not automatically faster. Nonuniform carrier locations also require appropriate bin selection, translation and filtering. Liquid-dsp supplies candidate primitives. [DSP library](https://github.com/jgaeddert/liquid-dsp), [channelizer documentation](https://liquidsdr.org/doc/firpfbch/)

A bounded I/Q prebuffer could recover the beginning of calls already inside this capture. It cannot recover a frequency the receiver was not sampling. At 1.536 MS/s, unsigned 8-bit I plus 8-bit Q is 3.072 MB/s, so five seconds is about 15.36 MB before metadata; retaining float-complex samples would require four times as much space.

**Other improvements worth building, in priority order**

1. **Show the exact reason for silence.** Extend existing diagnostics with current RF center, effective channel frequency, sample age/rate, last valid control and voice frames, selected slot, filter decisions and PCM arrival. Give a short English/Spanish explanation. Clear stale CC/rest-channel labels or mark their age. Completion means deliberately broken input, idle traffic, wrong mapping, blocked calls and output failures produce different, correct explanations.
2. **Strengthen Capacity Plus recovery.** Validate LCN/LSN maps before listening; preserve slot/call identity across rest moves; implement bounded reacquisition and explain unmapped grants. Compare event timelines with SDRTrunk. Its documented rest-channel fix is a useful regression reference, not evidence that XeraX has the same defect. [Reference fix](https://github.com/DSheirer/sdrtrunk/pull/1798)
3. **Compare two demodulation settings on difficult recordings.** Extend the existing I/Q lab with alternate timing/filter/equalizer paths and protocol-aware scoring. First evaluate offline; then consider a bounded live fallback. Use CRC/FEC evidence where available and consistent call context. Every voice frame does not necessarily have its own CRC. Do not select a path merely because it outputs louder audio.
4. **Add same-channel receiver diversity.** Two antennas/receivers could independently decode the same transmission, then select a better validated frame or call. This is a new experiment, separate from the existing control/voice two-dongle mode. Independent USB dongles have clock/frequency offsets; simple summing of their I/Q is not coherent combining. Alignment and duplicate suppression are prerequisites.
5. **Provide a PC-assisted listening mode.** Decode on the computer and send audio plus metadata to XeraX. Raw 1.536 MS/s 8-bit I/Q uses 24.576 Mb/s before overhead; a proposed Opus speech setting of 16–32 kb/s per audible call would be far smaller, plus metadata and transport. These are design rates, not measured quality results. Add sequence numbers, jitter buffering, stream health and reconnect handling. Existing PCM network input provides a starting point; the integrated Opus/control bridge would be new. [Opus](https://opus-codec.org/), [OP25's network-audio implementation](https://github.com/boatbod/op25/blob/master/README-browser-audio.md)
6. **Improve audible speech conservatively.** Benchmark vocoder concealment, level normalization and a limiter, keeping an original-audio comparison. Evaluate optional RNNoise only after analog demodulation or digital voice decoding. Its speech suppression cannot repair missing RF frames and may remove weak words, so disable it by default until listening tests justify it. [RNNoise](https://github.com/xiph/rnnoise)
7. **Adapt processing to sustained phone performance.** Use measured buffer deadlines and Android thermal state to reduce optional workers and waterfall load before audio fails. Maintain a lighter ARMv7 path. NEON is an implementation option; it is not evidence of improved RF sensitivity. Measure the real decoder workload, not only an isolated arithmetic benchmark.

**New format modules with credible starting points**

These are candidates for later implementation. A repository's Linux/desktop support does not establish direct Android USB operation; XeraX needs to supply appropriately formatted samples and own the USB permission lifecycle.

| New module | Candidate | Why it is worth considering / integration boundary |
|---|---|---|
| ADS-B / Mode S aircraft | [readsb](https://github.com/wiedehopf/readsb) | Purpose-built aircraft decoding and data output. Treat 1090 MHz reception as its own tuner task; 978 MHz UAT is a separate decoder project. |
| ISM sensors | [rtl_433](https://github.com/merbanan/rtl_433) | Many supported sensor protocols and structured output. Start with the user's own weather/sensor devices and per-protocol fixtures. |
| APRS / AX.25 | [Dire Wolf](https://github.com/wb2osz/direwolf) | Established packet modem and APRS parsing. Supply discriminator audio through an adapter; begin with receive-only operation. |
| POCSAG / FLEX / EAS / additional tone formats | [multimon-ng](https://github.com/EliasOenal/multimon-ng) | Multiple signaling/data decoders with file/stdin input. Add message framing, duplicate handling and local display; not just a protocol-selection label. |
| AIS vessels | [AIS-catcher](https://github.com/jvde-github/AIS-catcher) | Dual-channel AIS reception and structured/NMEA outputs. Useful where marine signals are receivable; lower local priority for an Indio setup. |
| ACARS aircraft messages | [acarsdec](https://github.com/TLeconte/acarsdec) | Dedicated ACARS SDR decoder. Keep this separate from ordinary AM aviation voice. |
| VDL Mode 2 | [dumpvdl2](https://github.com/szpajder/dumpvdl2) | Multichannel decoding, message reassembly and JSON; requires additional dependencies such as libacars. |
| FM station names/text | [redsea](https://github.com/windytan/redsea) | RDS decoding with JSON output. Requires the appropriate FM multiplex path. |
| HF digital voice | [Codec2/FreeDV](https://github.com/drowe67/codec2) | The FreeDV API adds modems and FEC around speech coding. Bundling Codec2 for M17 does not enable FreeDV reception by itself; mode selection and current upstream maintenance must be checked. |
| TETRA | [Osmocom TETRA](https://github.com/osmocom/osmo-tetra) | Research starting point for PHY/MAC, not a turnkey Android voice scanner. Demodulation, voice codec integration, trunking, licensing and fixtures would be a separate substantial project. |

For local usefulness, I would add ADS-B, rtl_433 and APRS before marine AIS or a large TETRA effort. That ordering is my recommendation; local signal availability has not been surveyed.

**How to earn a “stronger decoder” claim**

Use the same hashed I/Q recordings, source sample rate and expected call/event annotations for each candidate. Include clean speech, weak/fading signals, offset/drift, adjacent-channel interference, multipath, partial calls and multiple simultaneous calls. A second run with changing live traffic is not an equal-input comparison. Record exact decoder revisions and settings; do not turn off error checks merely to increase apparent frame counts.

| Measure | Evidence required |
|---|---|
| Call recovery | Fraction of independently annotated calls recovered, missing calls, wrong talkgroups and duplicate calls. |
| Speech completeness | First intelligible word delay, missing speech duration and blind listening to reference passages, including English/Spanish digits and call signs. |
| Decode correctness | Validated control/frame results, false locks and metadata errors. Raw FEC correction counts are not automatically RF bit-error rate. |
| Simulcast performance | Multiple real recordings plus varied delay/amplitude/noise trials; report failures as well as wins. |
| Network resilience | Sample stalls, delayed headers, disconnects and packet gaps; bound recovery and measure real audio continuity. |
| Phone cost | CPU, memory, battery, temperature and missed deadlines during sustained screen-on/off sessions on both requested phones and representative ARMv7 hardware. |

The next implementation sequence I recommend is: diagnose and repair the present DMR session, add the four-carrier school-site mode, establish OP25/SDRTrunk comparison fixtures, then implement the best-performing DSP/audio changes. Keep optional new protocols behind clear module choices and simple presets. No comparison winner or guaranteed weak-signal improvement has been measured by this research.
