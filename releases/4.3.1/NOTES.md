# XeraX SDR 4.3.1 — Android and Windows

This community test release improves shared decoder efficiency and makes silence
easier to diagnose.

- Clear reception stages: radio samples, synchronization, voice activity and
  decoded audio, including a stopped-input message.
- **Receiver tools → Quality → Save reception report** exports local measurements
  without keys, account credentials or recordings.
- Correct handling of unavailable control-frame counters and resets when changing
  mode or saved system at the same frequency.
- Updated Spanish messages and platform-appropriate audio help.
- Shared soft-bit calculation avoids duplicate work. It was **1.52× as fast in an
  isolated Windows kernel benchmark**; this is not a whole-decoder or Android
  device speedup claim. All 76 before/after I/Q replay pairs produced identical
  PCM and observed decoded results. Existing weak-signal misses remain.
- Android includes the digital gain and analog peak fixes previously shipped in
  Windows 4.3.0 preview 3.

## Choose your download

- **ARM64 APK:** Galaxy S25, Pixel 9 Pro and other Android ARM64 devices.
- **ARMv7 APK:** 32-bit ARM Android runtimes. Both APKs require Android 10+ and use
  the existing official signing identity for updates.
- **Windows x64 setup EXE:** per-user installer for Windows 10/11. Windows package
  version is `4.3.1-windows.1`. The EXE remains unsigned.
- **Windows portable ZIP:** extract the entire folder; keep its DLLs/subfolders.
- **Source ZIP:** corresponding Android/Windows source, tests and benchmarks.

37 shared host test groups, 49 benchmark-framework tests, 29 packaged Windows
application checks and 981 translation placeholder checks passed. The release
includes SHA-256 checksums and a verification report.

Physical phone/receiver acceptance, weak-signal field tests and Android performance
measurements are still pending. No GPU decoder or new unknown-key recovery was
added. AI remains optional and does not accelerate radio demodulation.

[Measured changes](../../docs/RECEIVER-QUALITY-4.3.1.md) ·
[Windows setup](../../docs/WINDOWS.md) ·
[Screenshots](../../docs/WINDOWS-SCREENSHOTS.md)

## Español

Actualización para Android ARM64/ARMv7 y Windows de 64 bits. Mejora la eficiencia
de un cálculo del decodificador, muestra con más claridad por qué no hay audio y
permite guardar un informe local sin claves ni credenciales. Incluye nuevos
mensajes en español. Las 76 comparaciones de señales I/Q conservaron exactamente
el audio y los resultados observados; esto no demuestra una mejora de velocidad
total ni de recepción débil. Faltan pruebas con teléfonos y radios físicos.
