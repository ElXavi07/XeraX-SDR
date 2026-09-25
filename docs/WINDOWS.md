# XeraX SDR for Windows — 4.3.0 Windows preview 1

Native desktop application for Windows 10/11 x64. No Android emulator is needed.
This community preview shares the Android decoder engine and interface, but does
not yet include every Android feature. Windows ARM64 emulation and 32-bit Windows
have not been validated.

## Install and listen

Use the **x64-setup.exe** installer, or extract the entire **portable.zip** into a
writable folder and open **XeraX-SDR.exe**. Keep all DLLs and subfolders together.
The installer is per-user and does not install USB drivers or change the firewall.
The executable is currently unsigned. Verify the release SHA-256 checksum.

1. For a dongle attached to this PC, choose USB RTL-SDR in Explore. The Windows
   WinUSB driver must already be assigned to the correct SDR interface. Close
   other programs that own the same dongle. Airspy R2/Mini uses its Airspy source.
2. For a network receiver, choose RTL-TCP and enter the server address and port.
   If rtl_tcp runs on this same PC, use **127.0.0.1:1234**. Only one client can
   use a typical rtl_tcp server at a time. For a remote PC, use its LAN address.
3. Enter the frequency and mode. Analog two-way channels normally use **Analog
   FM (NFM)**. Try squelch off during an analog audio diagnosis.
4. Select the desired default speakers/headphones in Windows sound settings,
   then start reception. Stop and restart reception after changing that output.
5. With reception stopped, **Check audio → Test sound** checks Windows playback.
   An active digital control channel does not guarantee voice traffic.
6. Use Settings to select English or Spanish. In Explore, enable frequency-range
   scanning and choose endpoints, spacing, mode and speed. Start with Balanced.

Close the application to stop reception. This preview has no Windows background
service or system-tray receiver. Settings and logs are stored per user; the
portable package does not imply portable user data.

## Included and limited features

| Feature | Windows preview |
|---|---|
| NFM, AM, broadcast FM mono | Native demodulation and Windows speaker output |
| DMR, NXDN48/96, P25 Phase 1/2 | Shared production decoder engine; signal and configuration dependent |
| Other inherited modes | Same engine implementations; see PROTOCOLS.md, not independently certified on Windows |
| Saved systems, scan lists, frequency-range scan | Included |
| Spectrum, waterfall, fine tuning, gain and PPM | Included |
| RTL-SDR V3/V4/V4 Lite and supported RTL2832U | Native driver included; USB hardware acceptance pending |
| Airspy R2/Mini | Native driver included; USB hardware acceptance pending |
| RTL-TCP, supported file and PCM input | Included |
| Replay, call recordings and WAV export | Included; Windows default output; PCM WAV playback |
| RadioReference | Approved application key in official binary; each user's entitled account required |
| English / Spanish | Shared interface plus translated Windows messages |
| HackRF direct USB / SoapySDR / SDRplay | Not included in this preview |
| Optional AI providers | Android-only in this preview |
| Extra receiver workers, four-channel audio, automated in-app I/Q lab | Android-only in this preview |
| GPS and Android notifications/background services | Not included |

User-supplied privacy keys and inherited experimental tools retain their existing
limits. This release does not promise recovery of unknown encryption keys,
universal decoding, or measured superiority over a hardware scanner.

## Build from the matching source

Install Qt 6.11.2 `mingw_64` with Qt Quick, a WinLibs POSIX MinGW x64 toolchain,
NDK 28.2.13676358 (its Clang compiler targets native Windows here), CMake, Ninja
and vcpkg. `scripts/build_windows.ps1` uses the documented cache under
`%LOCALAPPDATA%/XeraXSDR-build`. The NDK compiler is used to avoid the observed
GCC emulated-TLS teardown crash in this DSP pipeline; the output is Windows PE.
Use vcpkg commit `6e856794aebd1ee877acb74c9264d9552903c6fe` and the engine overlays.

```powershell
./scripts/build_windows.ps1 -InstallDependencies
./scripts/package_windows.ps1 -StageOnly
python scripts/check_windows.py dist/XeraX-SDR-4.3.0-windows.1-x64/XeraX-SDR.exe
./scripts/package_windows.ps1
```

For the installer, install the official Inno Setup 7.1.0 x64 compiler into
`%LOCALAPPDATA%/XeraXSDR-build/InnoSetup`. The public source contains no account
passwords or developer keys. Optionally pass `-RadioReferenceKeyFile` pointing
to your approved key, or supply `DSD_RR_APP_KEY` in the build environment.

Qt is dynamically linked. Dependency notices and Qt SBOMs ship under `licenses`.
Qt 6.11.2 source: https://download.qt.io/official_releases/qt/6.11/6.11.2/submodules/
Engine, XeraX modifications and build scripts are included in the matching source
archive. The source manifest validates this snapshot. The original Android patch
describes the 4.3.0 baseline; Windows changes are recorded in repository history.

## Español

Aplicación nativa para **Windows 10/11 de 64 bits**. Usa el instalador `.exe` o
extrae el ZIP completo y abre `XeraX-SDR.exe`, conservando sus carpetas y DLL.
No requiere un emulador de Android. El instalador es por usuario, todavía no está
firmado y no cambia controladores USB ni reglas del firewall.

Conecta un RTL-SDR con el controlador WinUSB correcto, o selecciona RTL-TCP. Si
el servidor está en esta misma computadora, usa `127.0.0.1`, puerto `1234`.
Cierra cualquier otro programa que esté usando el receptor. Elige la frecuencia
y el modo; para radio analógica de dos vías, usa **Analog FM (NFM)**. Selecciona
los altavoces en Windows y reinicia la recepción después de cambiar la salida.
Detén la recepción antes de usar **Probar sonido**. Cambia el idioma en Ajustes.

Incluye el motor DMR/NXDN/P25, recepción analógica, espectro, escaneo por rangos,
listas, grabaciones, repetición y RadioReference con tu propia cuenta habilitada.
Los controladores RTL-SDR V3/V4 y Airspy están incluidos; falta la validación con
cada equipo físico. **HackRF USB, IA, receptores adicionales, GPS y servicios de
Android no están incluidos en esta versión preliminar.** Al cerrar la aplicación
se detiene la recepción. No se promete descifrar cualquier señal ni superar al
SDS100. Reporta resultados con la versión, el receptor, la frecuencia, el modo y
los registros de diagnóstico; no publiques contraseñas ni claves privadas.
