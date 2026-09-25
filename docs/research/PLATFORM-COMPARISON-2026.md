# XeraX SDR engineering comparison, September 2026

Research completed before receiver changes in this work. Source revisions were checked against the projects' GitHub APIs on September 24 PDT / September 25 UTC, 2026; see [machine-readable snapshot](platform-snapshot-2026.json). These five projects are a deliberately complementary comparison set, not an objective worldwide top-five ranking. No common-corpus performance ranking has been established.

## Versions matter

| Project | Verified release/development distinction | Main comparison value |
| --- | --- | --- |
| SDR++ | Stable 1.0.4 is from 2021; inspected master 8c9f5ee is July 2026. The moving nightly release has an old creation date. | Modular receiver, multi-VFO and SIMD DSP |
| SDRangel | Latest listed stable v7.27.2, August 2026; inspected master e164076, September 2026 | Device/channel/feature plugins, multiple streams and automation |
| SDRTrunk | Stable v0.6.1 is December 2024; inspected master 8036002, August 2026. Nightly features must not be attributed automatically to stable. | Trunked multi-channel reception and CPU implementation calibration |
| DSD-FME | Public Windows release 20260715; inspected audio_work 719d970, September 2026 | Broad digital protocol and vendor-signaling coverage |
| OP25, boatbod | No GitHub release assets; pin master 71abcd0, August 2026 | P25 reception, trunk following, replay and independent comparisons |
| XeraX baseline | Windows preview 3, ab79212; shared engine pinned to 8c9c120 plus recorded local changes | Android/Windows interface and broad native decoding |

Release references: [SDR++](https://github.com/AlexandreRouma/SDRPlusPlus/releases), [SDRangel](https://github.com/f4exb/sdrangel/releases), [SDRTrunk](https://github.com/DSheirer/sdrtrunk/releases), [DSD-FME](https://github.com/lwvmobile/dsd-fme/releases/tag/20260715), [OP25 revision](https://github.com/boatbod/op25/commit/71abcd0ead32f86f51615ea6cc8a6a4dba4c949a).

## Receiver architecture, hardware and acceleration

| Project | Hardware/input support | DSP and concurrency | SIMD / GPU evidence |
| --- | --- | --- | --- |
| SDR++ | Dedicated source modules plus SoapySDR; RTL, Airspy, HackRF, SDRplay and others depend on build/driver | Native C++, modular stream processing, multiple VFOs | Explicit SIMD DSP support. OpenGL display is not proof of GPU radio decoding. |
| SDRangel | Source/sink plugins for RTL, Airspy, HackRF, SDRplay, LimeSDR, Pluto, bladeRF and more; build-dependent | C++/Qt, per-device streams and channel plugins; GUI and REST-controlled server forms | Optimized native DSP; no universal GPU DMR/NXDN/P25 decoder established by reviewed material |
| SDRTrunk | Native tuner integrations, including RTL, Airspy, SDRplay and HackRF; current tree also includes HydraSDR | Java, oversampled polyphase channelizer, channel pools and independent decoder chains | Scalar and Java Vector API implementations with calibration machinery; no documented general GPU decoder in this review |
| DSD-FME | Audio/discriminator files and streams, RTL path and external tuner control | Native C protocol engine; terminal-centric; multiple independent processes need external orchestration | Do not assume SIMD/GPU acceleration from a dependency or compiler flag; measure the selected build |
| OP25 | GNU Radio source ecosystem; RTL and wider-band devices via installed source drivers; file/symbol inputs | GNU Radio/C++ DSP with Python control; multi_rx supports concurrent channels/shared or multiple receivers | GNU Radio/CPU optimization ecosystem; no universal GPU protocol decoder established |
| XeraX | Windows native RTL V3/V4 and Airspy, RTL-TCP and replay. Direct HackRF/Soapy/SDRplay absent from Windows preview 3 | Native C/C++ with Qt UI; experimental shared workers exist on Android but are unavailable on Windows | Runtime AVX2/SSE2/scalar paths, ARM NEON paths. GPU inventory only, not GPU compute |

Primary architecture references: [SDR++ README](https://github.com/AlexandreRouma/SDRPlusPlus/blob/8c9f5ee8fe405775bfcd62c8c8f8c0fc928a64af/readme.md), [SDRangel quick start](https://github.com/f4exb/sdrangel/wiki/Quick-start), [SDRangel server](https://github.com/f4exb/sdrangel/blob/master/sdrsrv/readme.md), [SDRTrunk channelizer](https://github.com/DSheirer/sdrtrunk/blob/80360029efb008dca993938d1e34ad4a7a8c15bd/src/main/java/io/github/dsheirer/dsp/filter/channelizer/ComplexPolyphaseChannelizerM2.java), [SDRTrunk tuners](https://github.com/DSheirer/sdrtrunk/wiki/Tuners), [OP25](https://github.com/boatbod/op25/blob/71abcd0ead32f86f51615ea6cc8a6a4dba4c949a/README.md), [XeraX Windows scope](../WINDOWS.md).

## Protocols, operations and extensibility

| Project | Digital voice and trunking relevant here | UI / inspection | Recording/replay / plugins |
| --- | --- | --- | --- |
| SDR++ | General receiver foundation; stock core is not a complete DMR/NXDN/P25 trunking suite | Spectrum/waterfall, compact controls and multiple VFOs | Recorder/file source; explicit loadable module architecture |
| SDRangel | DSDcc plugin documents DMR, NXDN, dPMR, D-STAR and YSF; P25 is not in that plugin's documented list. Do not equate DMR demodulation with complete vendor trunk following. | Dense modular Qt workspaces, channel logs and REST control | File/SigMF inputs and sinks; device, channel and feature plugin categories |
| SDRTrunk development | P25 Phase 1/2; DMR state handling includes Tier III, Capacity Plus/Max and Connect Plus. Current NXDN code has 4800/9600/Type-D configuration and traffic management. Scope still needs corpus validation. | Playlist, calls/events, aliases and tuner views; useful debugging tools | Baseband/audio recording and replay; internal decoder/source extension architecture rather than SDR++-style generic modules |
| DSD-FME | DMR conventional/vendor trunking, NXDN conventional/Type-C/Type-D, P25 Phase 1/2 and other digital families; configuration and variant support matter | Terminal/status/event output and diagnostic options | Discriminator/symbol/MBE/audio workflows; extend source or wrap CLI rather than assume a stable plugin ABI |
| OP25 | Strong P25 comparison candidate. Its DMR document explicitly lists Tier II base station and experimental Connect Plus; lists simplex, Capacity Plus and Tier III as unsupported | Terminal/web interfaces and signal plots | Symbol and supported I/Q/audio replay; GNU Radio block/source extensibility |
| XeraX | DMR/NXDN/P25 native paths and other modes; broad implementation is not full interoperability certification | English/Spanish Qt interface, scan tools, spectrum, key profiles, diagnostics | Call audio/replay, I/Q machinery; Android-only worker/lab limits; no stable public decoder plugin ABI |

Protocol-specific evidence: [SDRangel DSD plugin](https://github.com/f4exb/sdrangel/blob/e1640760e4c8c1c0e46023b47f0bd2d9776c96eb/plugins/channelrx/demoddsd/readme.md), [SDRangel feature plugins](https://github.com/f4exb/sdrangel/wiki/Feature-plugins), [SDRangel SigMF sink](https://github.com/f4exb/sdrangel/tree/e1640760e4c8c1c0e46023b47f0bd2d9776c96eb/plugins/channelrx/sigmffilesink), [SDRTrunk DMR state](https://github.com/DSheirer/sdrtrunk/blob/80360029efb008dca993938d1e34ad4a7a8c15bd/src/main/java/io/github/dsheirer/module/decode/dmr/DMRDecoderState.java), [SDRTrunk NXDN configuration](https://github.com/DSheirer/sdrtrunk/blob/80360029efb008dca993938d1e34ad4a7a8c15bd/src/main/java/io/github/dsheirer/module/decode/nxdn/DecodeConfigNXDN.java), [DSD-FME options](https://github.com/lwvmobile/dsd-fme/blob/719d9709e6d4c738be70183616b7b87081b50776/examples/cygwin_bat/complete_usage_options.txt), [OP25 DMR limits](https://github.com/boatbod/op25/blob/71abcd0ead32f86f51615ea6cc8a6a4dba4c949a/op25/gr-op25_repeater/apps/README-dmr.md), [XeraX coverage](../PROTOCOLS.md).

## Demodulation quality and decoding speed

There are no defensible numeric rankings from the feature lists above. Acquisition time, FEC recovery, demodulation CPU cost, total replay speed and subjective speech quality are different measurements. They require identical captures, input stage, hardware, build options, operating modes, instrumentation and scoring.

Use three comparison tracks:

1. I/Q-to-frames: measures the receiver DSP and protocol chain together.
2. Discriminator/symbol-to-frames: isolates later stages. Never present this as an RF sensitivity comparison.
3. Frame-to-audio: compares vocoders/authorized-key transformations with known inputs.

SDR++ does not get a digital-voice score without a named external decoder. SDRangel's REST operations and SDRTrunk's replay facilities are integration opportunities, not evidence that automated adapters already work. Missing adapters/captures must appear as pending, not successful tests.

## Additional reference: DSDPlus

DSDPlus is relevant to community listening comparisons but is not an inspectable open engine. The official site announced a new public release in December 2025 and stated that Fast Lane continues for existing members while new memberships are closed. Compare a specifically identified public or legitimately available build; do not assume the old public feature set or redistribute Fast Lane. [Official DSDPlus announcement](https://www.dsdplus.com/).

## Architecture decision

Keep XeraX's current engine until paired experiments support replacing a component. Borrow design ideas: shared channelization from SDRTrunk, explicit module boundaries from SDR++, automation and capture formats from SDRangel, protocol edge cases from DSD-FME, and P25 comparison cases from OP25. Common ancestry and shared vocoders mean agreement between programs is not automatically independent ground truth.

The primary opportunities are persistent control/voice workers, retained raw I/Q, per-bit confidence preservation, bounded timing/equalizer hypotheses, protocol-aware acquisition scheduling and observable queue/transport behavior. GPU work should follow profiling of batched filtering/FFTs or many-channel workloads; [NVIDIA recommends profiling and counting transfer costs](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/). [VkFFT](https://github.com/DTolm/VkFFT) is a candidate math backend, not a radio protocol decoder.
