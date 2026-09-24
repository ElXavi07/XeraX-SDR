# XeraX SDR 4.1.1 — audio corrections

This release addresses the reported silent analog listening and makes digital/analog audio failures visible. It preserves the package ID, signing certificate, saved channels and RadioReference integration. Install the new APK as an update; uninstalling is unnecessary.

## Confirmed defects and changes

- The analog speech passband was configured for 8–12 kHz, removing most speech. NFM and AM now use 300–3400 Hz speech filtering. Broadcast FM bypasses that speech filter and keeps its existing 15 kHz audio low-pass/de-emphasis path.
- Normalized RTL samples now convert to PCM16 using the full-scale factor before the existing manual gain and clipping stages. With the same 1 kHz / 2.5 kHz-deviation NFM input, output RMS rises from 29.884 to 1998.758 PCM units (about 67 times the amplitude, 36.5 dB). The measured output peak is 2831, well below clipping.
- The RTL-TCP reader previously consumed the advertised gain count as if a list followed the header. Standard RTL-TCP sends exactly twelve header bytes, then I/Q. The corrected reader accepts fragmented headers and leaves all I/Q bytes intact. On V3, the old behavior lost 116 initial bytes; this alone does not establish the cause of ongoing silence. [RTL-SDR Blog server source](https://github.com/rtlsdrblog/rtl-sdr-blog/blob/master/src/rtl_tcp.c).
- Android audio-focus callbacks are tied to their request generation, so callbacks from an abandoned request cannot suppress a new one. A starting foreground receiver retains its focus lease while the native engine starts.
- **Check audio → Restore speaker audio** clears mute/replay/extra-receiver ownership, selects the phone speaker and retries focus. **Test sound** sends bounded test tones through native AAudio at digital/analog sample rates without needing reception.
- Audio health now distinguishes decoded PCM, silent PCM, Android write acceptance, replay/worker ownership, focus loss and zero media volume. Call animation has been replaced by a real PCM status.
- New controls and messages are translated to Spanish.

## Verification

- 29 application host groups pass, including the real AAudio backend against mocked Android device APIs: route changes, 8-to-48 kHz fallback, open/write errors, suppression, test cancellation and test-sample exclusion from radio telemetry/replay.
- 68 QML cases pass. Audio controls were rendered and inspected at 320 logical pixels with 130% text scale; layout also passes at 390/480 pixels.
- The actual Kotlin focus-state class passes grant, delayed grant, temporary loss, retry, stale-callback and abandonment tests.
- 30 full-I/Q decoder regressions, the P25 atomic voice command, and two core audio/filter groups pass (33 engine groups).
- 15 app-lab cases and four DSP comparisons complete. Five shared-channel checks and ten deterministic simulcast comparisons complete.
- Five new localhost tests traverse the production RTL-TCP reader, demodulator, analog filters and PCM output. They honor real tuning/sample-rate commands and fragment the server header. NFM passes at 400, 1000 and 2500 Hz, AM at 1000 Hz, and broadcast FM at 8000 Hz. Each requires nontrivial audio level, no clipping, and the expected tone dominating neighboring frequencies by at least 20 dB. [Measurements](AUDIO-NETWORK-4.1.1.json).
- 655 Spanish catalog entries pass placeholder checks and receiver/audio-screen coverage.
- Android release compilation and vital lint pass. Signing and 16 KB alignment use the existing certificate. The release verification JSON records package integrity, native dependencies and corresponding-source checks.

## Limits

The RTL-TCP integration test ends at captured UDP PCM. AAudio is tested separately with mocked device APIs. These tests do not reproduce Samsung/Pixel audio policy or prove physical speaker playback. No handset is connected for installation or listening tests. The phone screenshot showing SCHOOL / TG 46 establishes call metadata, not successfully decoded audible speech or encryption. The specific cause of that digital-call silence cannot be confirmed from the screenshot alone.

This release does not claim new encryption-key recovery, universal decoding, improved RF sensitivity or superiority over a hardware scanner.
