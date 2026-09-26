# XeraX SDR 4.3.2-rc.1 — NXDN correctness research candidate

This prerelease corrects NXDN soft error-correction costs and resets the shared
convolution decoder between independent blocks. Previously, missing/punctured
bits could bias path selection, and one block's survivor costs could affect the
next. The same correction is built for Android ARM64, Android ARMv7 and Windows
x64. The earlier 4.3.1 prerelease remains available while field testing continues.

## Measured results

- Independent mathematical checks: **1,952/1,952 passed**, versus 1,245 before.
- Independently encoded known-payload experiment: **1,542/1,792 exact blocks**,
  versus 397 before; incorrect source bits fell from 36,240 to 872. All 512
  clean candidate blocks passed. This tests the convolutional code, not complete
  NXDN frames, radio reception, decryption, or speech intelligibility. The normal
  receiver also uses CRC validation and hard fallback.
- Full receiver: **76 paired IQ cases / 152 completed runs**, with all mandatory
  clean and negative gates passing. DMR/P25 observations and audio were unchanged.
  Eight impaired NXDN cases changed confirmation/output timing; common voice
  payloads remained identical. Five existing non-gated impairment misses remain.
- A separate M17 stream replay produced identical non-silent PCM and normalized
  logs, checking a real user of the shared convolution routine.

The research source also contains a standalone IQ-history experiment and an
explicit sample-timing contract. They prepare further acquisition and recovery
experiments; they are not enabled features in these application packages. No GPU
decoding or unknown-key recovery was added. There is no whole-receiver speedup
or universal weak-signal improvement claim.

Android retains package ID `com.xerax.sdr`, minimum Android 10, and the existing
signing identity. Version code is 40302. Physical phone/USB/Wi-Fi RF testing and
human listening acceptance remain pending. Windows binaries are unsigned.

See [the research ledger](../../docs/research/OVERNIGHT-RESEARCH-2026-09-25.md),
[independent evidence](../../docs/research/ACQUISITION-HYPOTHESES-2026-09-25.md),
and the accompanying `verification.json` for exact scope and package checks.

## Español

Esta versión de prueba corrige el cálculo de corrección de errores NXDN y evita
que el estado de un bloque anterior afecte al siguiente. La mejora se comprobó
con datos independientes y reproducciones de señales; no significa que todas las
señales débiles se escuchen mejor ni que pueda recuperar claves desconocidas.
Los experimentos de historial de IQ y medición de tiempos todavía están separados
de la recepción en vivo. La versión de prueba anterior, 4.3.1, sigue disponible mientras continúan
las pruebas. Aún faltan pruebas físicas en teléfonos y receptores reales.
