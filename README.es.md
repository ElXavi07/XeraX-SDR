# XeraX SDR

<img src="assets/xerax-icon.svg" alt="Icono de XeraX SDR" width="96">

**Receptor SDR, decodificador de voz digital y escáner para Android, con controles en español e inglés.**

[Descargar 4.3.0](https://github.com/ElXavi07/XeraX-SDR/releases/tag/v4.3.0) · [English](README.md) · [Funciones completas, en inglés](docs/FEATURES.md) · [Informar un problema](https://github.com/ElXavi07/XeraX-SDR/issues)

**Versión de pruebas para la comunidad.** Ambos APK están compilados y firmados. Se registraron 33 grupos de pruebas de software y 80 pruebas de interfaz aprobados. Faltan pruebas completas de recepción, audio, consumo y funcionamiento en segundo plano con teléfonos y radios físicos.

## Instalación

Necesitas **Android 10 o posterior** y un SDR compatible por USB OTG o una fuente de red compatible. El teléfono por sí solo no recibe estas señales.

- **[ARM64](https://github.com/ElXavi07/XeraX-SDR/releases/download/v4.3.0/XeraX-SDR-4.3.0-arm64.apk):** Galaxy S25, Pixel 9 Pro y otros Android ARM de 64 bits.
- **[ARMv7](https://github.com/ElXavi07/XeraX-SDR/releases/download/v4.3.0/XeraX-SDR-4.3.0-armeabi-v7a.apk):** Android ARM de 32 bits; también requiere Android 10+.
- **[Código fuente](https://github.com/ElXavi07/XeraX-SDR/releases/download/v4.3.0/XeraX-SDR-4.3.0-source.zip).** La publicación incluye sumas SHA-256 y verificación.

Instala como actualización sobre una versión oficial anterior para conservar los datos. En **Settings → Language / Idioma** puedes cambiar el idioma sin reiniciar la recepción. Hay 878 traducciones verificadas; algunos textos técnicos heredados y nombres de bases de datos mantienen su idioma original.

## Funciones

| Área | Qué incluye |
|---|---|
| Radio analógica | FM estrecha, AM y FM comercial mono |
| Voz digital | NXDN48/96; DMR Tier II y opción de una ranura; P25 Fase 1/2, C4FM/CQPSK y simulcast |
| Otros modos | D-STAR, YSF, M17 con Codec2, dPMR, X2-TDMA, ProVoice y EDACS configurado |
| Escaneo por rango | 440–450 / 440–460 MHz y rangos propios; pasos y velocidades; retener, saltar, evitar y guardar frecuencias |
| Listas y sistemas | Canales analógicos/digitales, prioridades, talkgroups, mapas, alias y seguimiento de sistemas compatibles |
| Espectro | Cascada, picos, ajuste fino deslizando, pasos, zoom, ganancia y PPM automático/manual |
| Audio | Altavoz interno u otra salida, tonos de prueba, diagnóstico real y repetición de los últimos 30/60 segundos |
| Grabaciones | WAV por llamada, actividad analógica, búsqueda, favoritos, retención y exportación |
| Señalización | CTCSS/DCS, MDC-1200, FleetSync, DTMF y secuencias de dos tonos |
| Herramientas | Diagnóstico USB, mediciones, ensayos acotados de ganancia/sitio, filtros, hallazgos y perfiles |
| Laboratorio I/Q | Captura local, repetición/comparación y ecualizador de simulcast experimental |
| Varios canales | DMR de cuatro frecuencias dentro de una captura RTL, selección de audio y P25 con dos dongles; experimental |
| Datos y ubicación | Sitios guardados cercanos, estudio de actividad de banda, importación RadioReference y copias de configuración |
| IA opcional | OpenAI/DeepSeek con tu clave, modelos obtenidos de la API y herramientas locales de medición/comparación |

La IA está desactivada inicialmente. Audio e I/Q permanecen en el teléfono; tu pregunta y datos numéricos filtrados se envían al proveedor. La inferencia usa internet. El escáner y los decodificadores no necesitan IA.

## Radios y límites

Se incluyen controladores para RTL-SDR Blog V3/V4/V4 Lite y RTL compatibles, Airspy R2/Mini y **HackRF One experimental, solo recepción**, con límite actual de la aplicación de aproximadamente 2 GHz. RTL-TCP permite usar una radio conectada a otra computadora. No hay soporte directo para SDRplay, LimeSDR, Airspy HF+ ni cualquier dispositivo SoapySDR.

Hay perfiles de claves suministradas: DMR Basic Privacy 0–255, NXDN 0–32767, ADP/ARC4 y otros formatos compatibles, incluidos caminos P25 AES/DES. Coincidir un ID de clave no demuestra que la clave sea correcta. RAS de DMR no es cifrado.

Existe una búsqueda **experimental y opcional del scrambler NXDN de 15 bits**, que exige dos coincidencias de patrones antes de aplicar un candidato. No está validada con recepción real codificada ni garantiza encontrar la clave. No es recuperación universal ni ruptura de AES/DES o cualquier cifrado P25.

Un receptor recorre el rango por partes; puede perder llamadas breves. El escáner admite solicitudes de 24–1766 MHz, hasta 50 MHz de ancho y 10 001 posiciones; también se aplican límites del hardware. P25 Fase 2 y trunking requieren configuración real. No se incluyen TETRA, ADS-B, AIS, ACARS, POCSAG/FLEX, SSB ni estéreo/RDS.

## Primera prueba

1. Abre **Explore**, elige receptor, frecuencia conocida y modo correcto.
2. Para voz analógica VHF/UHF elige **Analog FM (NFM)**.
3. Inicia, selecciona el altavoz y sube volumen multimedia. **Check audio → Test sound** comprueba el reproductor sin transmisión.
4. Para buscar, activa **Scan a frequency range** y empieza con **Balanced**.

Un canal de control puede tener actividad sin voz. “Esperando audio” no demuestra por sí solo una falla del altavoz.

## Comunidad

Aceptamos informes y contribuciones en español o inglés. Incluye versión, teléfono, Android, receptor, conexión, modo y pasos. No publiques contraseñas, claves ni exportaciones sin revisar. Consulta [CONTRIBUTING](CONTRIBUTING.md).

Derivado independiente de [DSD-neo](https://github.com/arancormonk/dsd-neo), bajo **GPL-3.0-or-later** y avisos de sus dependencias. [Motor completo](upstream/dsd-neo) · [Compilación](docs/BUILD.md).
