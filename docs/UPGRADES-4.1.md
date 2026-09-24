# XeraX SDR 4.1.0

An installable test release for Galaxy S25 and Pixel 9 Pro, continuing the 4.0 features. No phone or SDS100 was connected during development. Software results are recorded separately from physical acceptance.

| Improvement | Result and location |
|---|---|
| P25 supplied-key confidence | Independently generated AES-128, AES-256 and DES OFB reference payloads test the production Phase 1 and both Phase 2 slot routines, multiple message indicators, missing keys and incorrect keys. Existing ADP and NXDN tests remain. Receiver lab → Reception shows algorithm, key ID and availability without exposing key material. |
| DMR RAS reception | A dedicated, persistent main-receiver switch enables the existing BPTC RAS heuristic without relaxing P25 or M17 CRC checks. A known RAS I/Q fixture decodes control identity when enabled; strict mode rejects it. Counters distinguish checked control bursts, suspected RAS and rejected bursts. RAS is separate from encrypted voice. |
| More efficient extra receivers | One shared immutable input block feeds the bounded worker queues. Each lane translates and anti-alias filters the capture through 47-tap half-band stages, delivering 192 kS/s instead of the entire capture. At 1.536 MS/s this reduces each worker's transported samples by eight. Five full-chain P25/DMR/NXDN replay cases retain expected evidence. Phone CPU/power improvement is unmeasured. |
| Continuous P25 voice process | Two-dongle mode queues one native command for phase, modulation, WACN/SYSID/NAC, slot selection and frequency, keeping the USB connection and decoder process open. It waits for acknowledgment and stops on rejection/timeout. The other TDMA slot is muted. The displayed latency is command acknowledgment, not first-word audio latency. |
| Simulcast evidence | A reproducible harness compares identical CQPSK settings across five synthetic impairment cases, recording sample hashes and FEC counts. The equalizer stays experimental and off by default. Saved-capture reprocessing remains available. |
| Antenna/gain comparison | Receiver lab → Reception measures a named fixed setup for 30 seconds, stores control-frame counter differences and valid SNR readings, and exports up to 30 recent results. Stops, retunes and counter resets invalidate a measurement. Repeat with one changed setting; changing traffic remains a confounder. Existing automatic gain trials remain available. |
| Comparison workflow | A documented paired-radio procedure and validated CSV summarizer are included. An empty form reports pending. They do not invent SDS100 measurements. |
| English and Spanish | Six receiver-lab tabs adapt to narrow screens. The expanded catalog has 629 entries. |

## Start here

Install the 4.1 APK over the prior XeraX installation; the package identity and signing certificate are preserved. For your analog two-way channel, select **Analog NFM**, tune the correct frequency, select **Phone speaker**, raise media volume and temporarily open squelch. The existing audio-route picker and spectrum drag/fine-tune controls remain available.

Open **Tools → Receiver lab → I/Q lab** to run the 15 bundled cases on your phone. Then use **Reception** for the main-receiver RAS switch, supplied-key status and antenna/gain measurements. Enable RAS only when appropriate to the received DMR system; suspected RAS is not a valid-call or decryption claim. Extra live workers keep their own configuration; this main-receiver switch does not change a running worker.

Shared nearby receivers still require a fixed 48 kHz base-bandwidth RTL capture and a target inside its usable window. There are still at most two extra workers and one audible receiver. The new filtering is a multistage per-channel downconverter, not an FFT/polyphase channel bank. Main-tuner changes, incompatible rates or a slow lane stop that lane explicitly.

Two-dongle mode still needs a separately permitted RTL-SDR and adequate USB power. It is P25-only, has a busy-call guard, and requires complete nonzero Phase 2 network context. The command test checks actual application of mode/network/slot context and rejection without a live tuner. USB retune latency, IPC behavior and intelligible opening words require phone testing.

## Measured software results

- 28 application host groups and 67 QML cases pass; the Spanish catalog passes all 629 placeholder/coverage checks.
- 30 full-I/Q regression cases and the atomic voice-command case pass.
- All 15 app-lab expectations pass; four additional offset/filter comparisons complete.
- All five shared-channel parity cases decode the expected P25/DMR/NXDN evidence after conversion from 1.536 MS/s to 192 kS/s.
- Ten equalizer/bypass runs complete. The reference, mild-noise and two echo cases tie at 52 accepted / 0 rejected control frames. The heavy-noise case gives 48/0 with bypass and 50/0 with equalization. These are short, deterministic synthetic samples with one seed, not proof of general RF improvement.

See [I/Q results](IQ-LAB-4.1.json), [channel/simulcast results](RECEPTION-BENCHMARK-4.1.json), [comparison procedure](RECEIVER-COMPARISON.md) and [phone acceptance](PHONE-ACCEPTANCE.md). The APK signature, native dependencies and 16 KB page alignment are verified in the release verification JSON.

Matching supplied keys are required for encrypted content. No unknown-key search or recovery was added. A matching key ID is availability metadata, not proof of correct speech. Hardware acceptance, real speech quality, battery behavior and superiority over an SDS100 remain unproven.
