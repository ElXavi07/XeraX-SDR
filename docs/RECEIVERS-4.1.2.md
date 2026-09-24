# XeraX SDR 4.1.2: Android architectures, USB receivers and PPM

There are separate signed APKs for **arm64-v8a** and **armeabi-v7a**. Both require
Android 10 or newer and retain the same decoder features. Galaxy S25 and Pixel 9
Pro use the ARM64 APK. The ARMv7 APK is for phones with a 32-bit Android runtime;
it does not make those phones as fast as newer hardware. These APKs use the
existing application ID and signing certificate.

## Receiver coverage

| Receiver | Connection | Implementation / limits |
|---|---|---|
| RTL-SDR Blog V3, V4, V4 Lite | USB OTG or compatible RTL-TCP server | Bundled Blog driver includes V4 input switching and HF conversion; USB ID 0BDA:2838 is accepted. Use an updated Blog driver on a remote server too. |
| Compatible RTL2832U receivers | USB OTG / RTL-TCP | Known USB IDs in the Android filter; actual tuning range depends on the tuner. |
| Airspy R2 / Mini | USB OTG | Existing Airspy backend, separate Airspy source and controls. |
| HackRF One | USB OTG, select USB dongle | New experimental receive backend, USB ID 1D50:6089. Current app tuning is limited to approximately 1 MHz–2 GHz, not the hardware's full tuning range. No transmit controls. |
| Other SDR families | Not claimed | SDRplay, LimeSDR, Airspy HF+, and arbitrary SoapySDR devices do not have direct Android drivers in this APK. |

The screenshot's V4 report does not establish the cause of that phone's USB
failure. **Tools → Receiver tools → USB receiver check** now lists the devices
Android sees, their USB IDs, whether a driver is present, and whether permission
is granted. Stop reception before using **Request USB access again**. If no
device appears, check the OTG/data connection and power. Frequency correction
does not fix USB enumeration.

HackRF uses libhackrf v2026.01.3, pinned at
`1cfe7dfe98d333450217d50e3f3a1ad0702e000f`, with an Android permission-descriptor
wrapper. Signed 8-bit IQ is converted into the decoder's unsigned IQ format.
The ADC runs at least 8 MS/s; cascaded 47-tap halfband filters reduce it to the
decoder capture rate. Rate changes stop/reconfigure/restart streaming. The RF
amplifier and antenna power start off. Automatic gain requests use a moderate
32 dB manual setting; live gain reports the setting actually applied. HackRF
does not expose RTL-style PPM correction in this release. Power, throughput,
firmware compatibility and audio remain physical-device acceptance items.

## Calibration controls

While listening, open the radio controls from **Spectrum**. **Automatic PPM**
uses the existing DSD-neo estimator and reports waiting/locked status from the
engine. It needs a suitable stable signal and may remain waiting on weak,
short, changing or unsuitable signals. It is not a universal auto-tune guarantee.
**Manual PPM** accepts whole numbers from -200 through 200, disables automatic
correction, and saves the requested value for later sessions. +/- controls remain.
Driver readback determines the displayed applied value after a request settles.
The controls and USB diagnostic labels are available in English and Spanish.

## Verification and limits

The release report records signed package hashes, ABI/ELF inspection, native
dependency closure, source matching, Android build/lint results and automated
tests. Tests include actual HackRF adapter code with a mocked USB library,
real signed-IQ conversion and anti-alias filters, lifecycle/failure cleanup,
PPM engine tests, UI validation, and full digital I/Q regressions.

Software checks do not establish reception or speaker playback on a physical
V4, HackRF, S25, Pixel, or 32-bit phone. Hardware testing is pending. Existing
4.1.1 audio fixes are retained; this release is not a claim that every silent
radio channel has been resolved.

## Primary references

- [RTL-SDR Blog V4 guide](https://www.rtl-sdr.com/V4/)
- [RTL-SDR Blog driver](https://github.com/rtlsdrblog/rtl-sdr-blog)
- [HackRF sample-rate and filtering guidance](https://hackrf.readthedocs.io/en/latest/sampling_rate.html)
- [Pinned libhackrf source](https://github.com/greatscottgadgets/hackrf/tree/v2026.01.3/host/libhackrf/src)
- [Qt Android ABI selection](https://doc.qt.io/qt-6/cmake-target-property-qt-android-abis.html)
- [Android ABI documentation](https://developer.android.com/ndk/guides/abis)

## Reproducible ARMv7 build

After installing the standard build prerequisites, run:

```powershell
python scripts/install_qt.py "$env:LOCALAPPDATA\XeraXSDR-build" --abi armeabi-v7a --skip-host
./scripts/dependencies.ps1 -Abi armeabi-v7a
./scripts/build.ps1 -Abi armeabi-v7a
./scripts/sign.ps1 -Abi armeabi-v7a
python scripts/verify_apk.py dist/XeraX-SDR-4.1.2-armeabi-v7a.apk --abi armeabi-v7a
```

The default ABI remains ARM64. Architecture-specific build and dependency
directories prevent mixing native libraries. The loader selects the native
library using the Android process bitness. ARMv7 portability fixes preserve
64-bit audio replay arithmetic and omit a compiler flag unsupported by ARMv7;
stack-protector-strong and compiler warnings-as-errors remain enabled.
