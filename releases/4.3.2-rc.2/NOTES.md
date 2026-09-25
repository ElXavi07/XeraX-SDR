# XeraX SDR 4.3.2-rc.2 — optional earlier NXDN48 detection

[RC2 prerelease and packages](https://github.com/ElXavi07/XeraX-SDR/releases/tag/v4.3.2-rc.2)

RC2 adds an optional NXDN48 acquisition experiment to the shared Android and
Windows interface. Packages cover Android **arm64-v8a** and **armeabi-v7a**
(Android 10+), plus a Windows 10/11 **x64 setup installer and portable ZIP**.
The [RC1 release](../4.3.2-rc.1/NOTES.md) and earlier releases remain available.

## Enable it for a new listening session

Open **Tools** in the main navigation to reach the Settings page. Scroll to
**Decoding · next start** and enable **Faster NXDN48 detection (experimental)**.
While listening, reach the same page through **Session options → Settings**.

The preference is **off by default**. Stop and start listening to apply a change;
the toggle does not change a running receiver. Existing settings are preserved.
Saved systems, Explore, scan lists and Android additional receiver sessions use
the preference at startup. Diagnostic saved-I/Q reprocessing and the built-in
lab retain their own trial settings and do not inherit this toggle.

## What the experiment changes

For an unconfirmed NXDN48 waveform on the 2400-symbol/s four-level profile, it
provisionally accepts the first **canonical positive** synchronization sign
pattern. Existing LICH, frame/FEC and CRC validation remain in place. A
provisional match alone does not refresh scanner hold clocks in the opt-in
path; the existing frame-confirmation logic decides when to refresh them.

The early shortcut does not apply to inverted-polarity sync, NXDN96 or raw
symbol-file input. It adds no encryption-key recovery capability.

## Evidence and limits

The preceding [synthetic component experiment](../../docs/research/NXDN-FIRST-SYNC-2026-09-25.md)
recovered the first complete, correctly decoded control frame
**79.9375–80.0625 ms earlier in all 120 positive cases**, while retaining later
frames recovered by the baseline. Its **36 negative/history controls** gained
no false current-frame proof. These are measurements of generated discriminator
streams through acquisition and frame validation, with no RF hardware or voice
in that experiment.

This is not evidence of faster audible voice, reduced CPU use or power,
whole-application speed, or improved reception on physical devices. Invalid
candidates can cause additional decoding work. Weak-signal, impaired-IQ,
mixed-protocol/scanner and physical phone/receiver testing remain incomplete;
human listening acceptance is pending. The option remains experimental and
disabled by default.

## RC2 verification

The public session option reproduces the component result on Windows and Linux
release/ASan/UBSan builds. Parsed observations and sample traces match across
all three pairs. Seven native regression groups, 91 QML cases, 983 translation
entries and 30 packaged Windows checks pass. Android packages pass signing,
ABI/dependency and alignment checks. See [verification.json](verification.json)
and the validation ZIP in this release for exact hashes, evidence and limits.

The Windows executable was exercised with synthetic input, real audio output,
replay and connection errors. Phone installation, real radio reception and
human listening acceptance remain pending. APKs retain the existing signing
certificate and application ID; previous releases remain available.

## Español

RC2 añade una opción experimental de adquisición NXDN48 a Android y Windows.
Hay paquetes Android **arm64-v8a / armeabi-v7a** (Android 10+) e **instalador y
ZIP portátil para Windows 10/11 x64**.

Abre **Herramientas** para llegar a Ajustes. En **Decodificación · próximo
inicio**, activa **Detección más rápida de NXDN48 (experimental)**. Durante la
escucha, usa **Session options → Ajustes**. Está **desactivada por defecto**:
detén e inicia de nuevo la escucha para aplicar el cambio. Conserva los ajustes
existentes. El reprocesamiento de I/Q y el laboratorio integrado mantienen sus
propios ajustes y no heredan esta opción.

La opción prueba antes la primera sincronización canónica de polaridad positiva
de una señal NXDN48, sin retirar la validación de tramas y CRC. Una coincidencia
provisional no renueva por sí sola los tiempos de retención del escáner. El
atajo no se aplica a sincronización invertida, NXDN96 ni archivos de símbolos.

En el experimento sintético previo, la primera trama de control válida llegó
unos **80 ms antes en 120 casos positivos**; los **36 controles negativos y de
historial** no ganaron validaciones falsas de la trama actual. No demuestra audio más
rápido, menor consumo de CPU o energía ni mejor recepción real. Los candidatos
inválidos pueden requerir más trabajo de decodificación. Continúan las pruebas
con señales débiles, I/Q deteriorada y escaneo; faltan pruebas físicas con
teléfonos/receptores y aceptación mediante escucha humana.
