# First research and benchmark milestone — September 24, 2026

**Result:** a reproducible benchmark foundation and initial experiments are implemented. No receiver algorithm was promoted and no new APK/EXE is claimed by this milestone. The evidence supports specific next experiments; it does not establish that XeraX outperforms the five reviewed platforms.

Research: [five-platform comparison](PLATFORM-COMPARISON-2026.md), [architecture experiments](RECEIVER-EXPERIMENTS.md), [privacy/conformance](PRIVACY-AND-CONFORMANCE.md), [prioritized roadmap](ENGINEERING-ROADMAP.md). Implementation and reproduction: [benchmark guide](../../benchmarks/README.md).

## What actually ran

The local experiments ran on Windows 10 build 19045, Intel family 6/model 126/stepping 5, eight logical CPUs, Python 3.11.15. CPU frequency was not locked. The native Release runner uses NDK 28.2 Clang targeting Windows GNU; fast-math, native-architecture flag and LTO were off. The package source baseline is **ab79212220b87b077a271194180ee071271d2e8c**. Its embedded version banner still says 5c93f66, so the exact binary hash, not that stale banner alone, identifies the executable.

XeraX runner SHA-256: `515e81d7fd0ce4bcd8c4ca299fa5232592141faff694640314358cc473e6668f`.

The independent reference is the official [DSD-FME public Windows release 20260715](https://github.com/lwvmobile/dsd-fme/releases/tag/20260715), whose actual banner is **AW 2026-34-g69d3115 (CYGWIN), MBElib 1.3.4**. This is different from the development revision examined in the platform research. Its binary/archive hashes and the individual measured observations are preserved in [machine-readable evidence](initial-observations-2026.json). The [capture catalog](initial-corpus-catalog.json) records input hashes, provenance, seeds, transformations and assertion scope. Raw logs, I/Q and decoded audio remain local; none are newly redistributed here.

There were **298 measured decoder process runs**, plus warmups, across the experiments below. Framework validation currently has **41 passing tests**. Regenerating the full corpus reproduced all 76 I/Q files and native metadata files byte for byte. The CI workflow is separate from native decoder acceptance: it exercises framework correctness and corpus generation on Windows/Linux and Python 3.11/3.13.

## Baseline corpus: 76 cases

Six input fixtures cover P25 Phase 1 C4FM and CQPSK control, P25 Phase 2 control, DMR voice, NXDN48 and NXDN96. Each is replayed under eleven conditions. Ten additional cases test noise/random nonprotocol 4FSK against five mode selectors.

- All 76 native processes completed; no crash or timeout occurred.
- All **six clean known-field checks** and **ten negative-signal checks** passed.
- **71/76 total field/negative assertions passed.** This is an assertion result, not 93% bit accuracy or a call-success rate.
- Expected-field misses occurred in P25 CQPSK cochannel interference, P25 Phase 2 cochannel interference, DMR added-noise 0 dB, DMR 100 ppm clock change, and DMR cochannel interference.

The clock case motivates a timing/filter/resampling investigation. The interference cases do not establish a receiver defect by themselves: independently overlapped signals may be unrecoverable at the declared powers. Negative checks reject the specified trusted-field/voice patterns; they do not prove zero internal sync hypotheses or zero false positives at all noise levels.

P25 Phase 1 and NXDN sources derive from real off-air I/Q; DMR voice and P25 Phase 2 sources were reconstructed from discriminator audio. “0 dB” here means added noise relative to total source sample power, including the source's existing noise. It is not calibrated RF SNR. Current payload truth is insufficient to compute BER or intelligibility.

## Existing P25 equalizer: useful on one condition, not a universal improvement

The same native binary was run with the existing lab equalizer off and on. Eleven CQPSK conditions had three measured repetitions per setting and one warmup. Three selected conditions also had five measured repetitions in speed mode, which omits added WAV/frame/event recording.

| CQPSK condition | Accepted-FEC counter, off → on | Median process time off → on, speed mode | Decision |
| --- | ---: | ---: | --- |
| Clean | 52 → 51 | 0.4763 s → 0.4732 s | Do not sacrifice a clean accepted unit for this timing difference |
| Added noise, 0 dB reference | 13 → 18 | 0.4681 s → 0.4732 s | Candidate for selective use; verify actual recovered payloads |
| One synthetic echo | 52 → 52 | 0.4684 s → 0.4715 s | No demonstrated decoding benefit here |

These FEC counters were repeatable within the runs. They count engine-accepted units, not independently verified correct bits. These are control captures, so missing vocoder payload hashes cannot establish audio equivalence. The roughly 0.47-second process times include startup/shutdown and ordinary logging; they are not synchronization latency. Small timing differences on an unlocked host are not compelling speedups.

**Promotion decision: leave the receiver default unchanged.** Investigate adaptive activation only with held-out captures and full payload/call metrics. This is a recorded experiment with a mixed outcome, not a new equalizer implementation.

## Independent DSD-FME reference: qualification findings

Both receivers received identical 48 kHz discriminator WAVs derived from the same I/Q. Four FSK families × three conditions × two receivers × three measured repetitions produced 72 measured runs. The adapter uses declared protocol selectors and default receiver filtering; no per-capture tuning was performed.

| Shared-audio test | XeraX required field | DSD-FME required field | Interpretation |
| --- | --- | --- | --- |
| P25 C4FM clean | Pass, 3/3 | Pass, 3/3 | Minimal clean-input qualification |
| DMR clean | Pass, 3/3 | Pass, 3/3 | Color-code qualification only |
| NXDN48 clean | Pass, 3/3 | Missing, 0/3 | Investigate input scaling/filtering/polarity and configuration |
| NXDN96 clean | Missing, 0/3 | Missing, 0/3 | Shared conversion/input path not qualified |

The reference run correctly returned a failing gate status for the nine missing required clean-field observations. XeraX's native I/Q NXDN96 case passed; its converted-audio case did not. That difference is a reason to investigate the test path, not conceal the result or rank the programs. Error counters and amounts of decoded audio also differ; fewer reported errors can simply reflect fewer processed frames. No across-application speed/sensitivity winner is declared.

OP25, SDRTrunk, SDRangel and SDR++ were researched from primary sources, **not executed in a common-corpus benchmark**. Their automated adapters remain pending in the [coverage ledger](../../benchmarks/coverage.json).

## Load, overlap and Tier III import

Four concurrent independent native replay processes completed **48/48 runs**, with all required field checks passing. They processed approximately **16.74 seconds of recorded input per elapsed second** in this short workload. This includes multiple processes, framework work and mixed short recordings; it is not a claim of 16 live channels or a sustained thermal result. A shared wideband receiver/channelizer was not exercised.

A byte-exact import of the existing DMR Tier III control fixture passed its color-code check in 3/3 measured runs. This validates registration/replay, not full Tier III grant-to-voice following.

An NXDN48 wanted capture mixed with an independent DMR capture at +12.5 kHz and equal total-source powers retained the expected NXDN source field in 3/3 measured runs. Only the wanted channel was scored. This is software interference testing; it does not validate simultaneous decoding of both transmissions or physical tuner overload handling.

## Next increment and remaining evidence

Proceed with sample-indexed acquisition/recovery instrumentation and qualification of independent reference inputs. Then investigate the DMR clock case and NXDN per-bit confidence preservation. The [experiment design](RECEIVER-EXPERIMENTS.md) specifies persistent channel workers, raw-I/Q prehistory, SIMD/GPU selection, local RF learning and protocol state tests after those foundations.

Still pending: valid known-bit synthetic protocol transmitters, independent holdout captures, true frame/bit error curves, sample-indexed first-audio measurements, high-grant-rate trunking scenarios, live device tests, long thermal/queue tests, other application adapters and GPU compute. Existing supplied-key payload vectors are documented separately; this benchmark milestone adds no unknown-key recovery and does not claim full on-air encryption interoperability.
