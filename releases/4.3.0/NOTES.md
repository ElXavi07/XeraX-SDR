# XeraX SDR 4.3.0 — community testing release

Android SDR receiver, decoder and scanner with English/Spanish controls. Requires **Android 10+** and a supported SDR or network/file input.

## Choose your APK

- **XeraX-SDR-4.3.0-arm64.apk**: Galaxy S25, Pixel 9 Pro and other 64-bit ARM Android runtimes.
- **XeraX-SDR-4.3.0-armeabi-v7a.apk**: devices with 32-bit ARM Android runtimes.
- **XeraX-SDR-4.3.0-source.zip**: matching complete source and original release documentation.
- **XeraX-SDR-4.3.0-SHA256SUMS.txt** and verification JSON: checksums and recorded evidence.

Install over an earlier official XeraX release to retain data. Package ID: com.xerax.sdr.

## New in 4.3.0

Frequency-range scanning surveys spectrum blocks, tunes candidates, acquires analog/digital signals, resumes and saves discoveries. Includes 440–450 / 440–460 MHz presets, configurable spacing, Fast/Balanced/Thorough, Hold, Skip and Avoid. Open **Explore → Scan a frequency range**. It runs locally and requires no AI key.

## Included from earlier versions

NFM/AM/FM-mono; NXDN48/96, DMR, P25 Phase 1/2 and additional documented modes; configured trunk following; saved/priority scan lists; spectrum gestures; speaker/audio diagnostics; replay/WAV recordings; analog signaling; RadioReference imports; calibration/measurements; local I/Q lab; experimental nearby-channel/two-dongle reception; supplied-key profiles; optional experimental NXDN search; and optional OpenAI/DeepSeek investigations.

[Complete features](https://github.com/ElXavi07/XeraX-SDR/blob/main/docs/FEATURES.md) · [Setup](https://github.com/ElXavi07/XeraX-SDR/blob/main/docs/QUICKSTART.md) · [Español](https://github.com/ElXavi07/XeraX-SDR/blob/main/README.es.md)

## Evidence and remaining work

Recorded: **33 host groups, 80 QML cases, 878 Spanish translations**, both release builds/lint, signatures, ABI/dependencies and source/native matching. Hardware acceptance is pending. These checks do not establish real scan speed, intelligible speech, background reliability or superiority over another receiver.

One tuner scans sequentially and may miss short calls. Auto digital does not classify analog. Trunking/P25 Phase 2 need system configuration. HackRF and advanced multi-receiver features remain experimental. Privacy handling is limited to compatible formats/material; NXDN search is not universal encryption recovery. Optional AI uses your key and the provider's internet service.

Report results in [Issues](https://github.com/ElXavi07/XeraX-SDR/issues), in English or Spanish.

**Español:** versión de pruebas para la comunidad con escaneo por rangos y controles bilingües. Para S25/Pixel 9 Pro usa ARM64. Se aprobaron las pruebas de software indicadas; la recepción y el audio reales requieren pruebas de dispositivos. El escáner no necesita IA. Comparte tus resultados sin publicar claves ni contraseñas.

Independent GPL-3.0-or-later derivative of DSD-neo, with corresponding source and retained third-party notices.
