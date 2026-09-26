# XeraX SDR 4.3.2-rc.3 â€” NXDN confirmation reliability

RC3 puts the measured NXDN rejected-frame correction into Android **arm64-v8a**
and **armeabi-v7a** APKs, plus the Windows **x64 installer and portable ZIP**.
Android requires version 10 or newer. Use the ARM64 APK for Galaxy S25 and
Pixel 9 Pro. Existing official signing, application and settings identities are
preserved. RC1, RC2 and earlier downloads remain available.

## What changed

A frame rejected at its NXDN LICH header now clears that frame's evidence and
breaks a pending weak-confirmation streak. Previously, two weak observations
separated by a rejected header could be counted as consecutive. An already
confirmed call retains its historical confirmation, while the rejected frame
does not count as fresh proof. The correction applies with the faster detection
option both off and on.

**Faster NXDN48 detection (experimental)** remains off by default. Enable it in
**Tools â†’ Decoding Â· next start**, then stop and start listening. No new setup
step is needed for the rejected-frame correction.

## Validation and scope

The new regression fails against the original source and passes against the
integrated correction. It checks parity, unsupported-header and direction
rejection; pending and confirmed calls; voice/file gates; scanner clocks; and
both acquisition-option settings. Eleven current-source Windows native test
groups, 91 interface cases and 983 translation checks pass. Eight Linux native
groups pass in both release and ASan/UBSan builds. Thirty checks run against the
packaged Windows application, including synthetic analog TCP reception, output
acceptance, replay and connection failures.

Both APKs pass manifest, ABI, dependency, signature and alignment verification.
ARM64 native libraries meet 16 KiB LOAD alignment; ARMv7 requires and meets
4 KiB alignment. The portable archive matches every checked staging file.
See [verification.json](verification.json), [SHA256SUMS.txt](SHA256SUMS.txt) and the validation ZIP for exact build
identities, logs and package hashes.

This integrates the candidate already tested through real synchronization,
dispatch, FEC and CRC in the controlled [continuous-engine study](../../docs/research/NXDN-ENGINE-GAP-2026-09-25.md). Those finite
discriminator-stream measurements are separate from product/package regressions.
Historical studies retain their original source snapshots; they are not relabeled
as current-product tests.

Physical phone/RF reception, human listening and Windows installer execution
remain unverified. This release does not establish faster audible voice, better
RF sensitivity, GPU decoding or unknown-key recovery. Earlier acquisition remains
experimental; encryption support continues to require authorized supplied keys
or controlled test vectors.

## EspaÃ±ol

RC3 incorpora la correcciÃ³n comprobada de confirmaciÃ³n NXDN en los APK para
Android **arm64-v8a / armeabi-v7a** y en el **instalador / ZIP portÃ¡til de
Windows x64**. Conserva la identidad de actualizaciÃ³n y los ajustes existentes.
Para Galaxy S25 y Pixel 9 Pro, usa el APK ARM64.

Un encabezado NXDN rechazado ahora interrumpe la secuencia pendiente de
confirmaciones dÃ©biles. Una llamada ya confirmada mantiene su estado histÃ³rico;
la trama rechazada no aporta evidencia nueva. La opciÃ³n **DetecciÃ³n mÃ¡s rÃ¡pida
de NXDN48 (experimental)** continÃºa desactivada por defecto. Esta correcciÃ³n no
necesita activar esa opciÃ³n.

Pasan las pruebas de regresiÃ³n, interfaz y paquetes indicadas arriba. TodavÃ­a
faltan pruebas fÃ­sicas con telÃ©fonos y radios, escucha humana y ejecuciÃ³n del
instalador. No se afirma una mejora medida de sensibilidad, velocidad de audio
ni recuperaciÃ³n de claves desconocidas.
