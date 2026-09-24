# Building XeraX SDR on Windows

For the separate ARMv7 build and architecture switches introduced in 4.1.2, see [receiver/ABI build instructions](RECEIVERS-4.1.2.md). The default remains ARM64.

## Full I/Q lab (4.0)

Run `./scripts/build_iq_lab.ps1 -InstallDependencies` once, then omit the dependency switch on later runs. It uses NDK Clang as a Windows host compiler with the installed MinGW headers/libraries, builds the real engine, executes 30 upstream I/Q regressions and then the 13 Android lab cases plus four DSP comparisons. JSON, logs and WAVs appear under `build/iq-lab-report`. Fixture hashes are verified before replay; previous test WAVs are removed to prevent append contamination.

This compiler choice avoids the installed MinGW emulated-TLS destructor failure reproduced with a minimal vector/thread program. No decoder workaround or test bypass was added. GCC documents that [native Windows TLS requires a compiler configured with --enable-tls](https://gcc.gnu.org/gcc-16/changes.html); the [MinGW destructor ordering issue](https://github.com/msys2/MINGW-packages/issues/2519) describes the failure class. Android always uses the NDK ARM64 toolchain.

The public repository and release source ZIP contain the complete patched decoder tree under `upstream/dsd-neo`, plus its baseline source manifest. `UPSTREAM.json` pins the original upstream revision and `patches/xerax.patch` records its changes. The upstream license and notices are retained. `prepare_source.py` verifies an unchanged source snapshot; if you edit the source, build directly rather than asking that script to verify the original manifest again. It never resets your edits.

## Toolchain used

- Windows x64, PowerShell 7 and Python 3.11 (`requests`)
- MinGW GCC/G++ 16.1 and Ninja for host code generation and checks
- JDK 21
- Android SDK platform 36, build-tools 36.0.0
- Android NDK 28.2.13676358
- Qt 6.11.2 Android ARM64 and Windows MinGW host kits
- vcpkg commit `6e856794aebd1ee877acb74c9264d9552903c6fe`; manifest baseline is pinned upstream

Build cache defaults to `%LOCALAPPDATA%\XeraXSDR-build`. Keep the cache outside OneDrive. Place the JDK under `jdk/<jdk-directory>` within that cache. SDK installation defaults to `%LOCALAPPDATA%\Android\Sdk`.

## Commands

```powershell
python scripts/prepare_source.py
./scripts/dependencies.ps1
python scripts/install_qt.py "$env:LOCALAPPDATA\XeraXSDR-build"
./scripts/build.ps1
./scripts/sign.ps1
```

`install_qt.py` verifies Qt's metadata SHA-256 and archive SHA-1 checksums over HTTPS, then extracts the two kits separately. The helper exists because the available aqt release did not understand Qt 6.11's host repository layout. Dependencies are fetched with the vcpkg manifest/overlay hashes.

The Codec2 overlay supplies an explicit native host compiler and `.exe` suffix when cross-compiling on Windows. This does not change its codec algorithms. Dependency builds are release-only. The APK is compiled with the NDK, a native AAudio backend, RTL/Airspy backends, ARM64 DSP, and link-time optimization. SoapySDR is disabled on Android.

## Tests

```powershell
cmake -S checks -B build/checks -G Ninja -DCMAKE_BUILD_TYPE=Debug `
  "-DCMAKE_PREFIX_PATH=$env:LOCALAPPDATA/XeraXSDR-build/QtKits/6.11.2/mingw_64" `
  "-DXERAX_EXPAT_SOURCE=C:/path/to/libexpat-R_2_8_4/expat"
cmake --build build/checks --parallel 4
$env:Path = "$env:LOCALAPPDATA\XeraXSDR-build\QtKits\6.11.2\mingw_64\bin;" + $env:Path
ctest --test-dir build/checks --output-on-failure
```

The configuration needs the official Expat 2.8.4 source tree at the supplied path. Version 4.3.0 records 33 host groups and 80 QML cases, including selected upstream FEC/NXDN/P25 code, actual session arguments, scanner policy/persistence, analog DSP, native AAudio against a fake Android API, offline RadioReference/AI replies, and the range controller with synthetic FFT frames and a deterministic clock. Audio checks cover device requests/readback, writer-thread routing, retries and rate fallback. These do not substitute for Android radio/audio testing.

Set `XERAX_PREVIEW_DIR` to an existing absolute directory to save desktop renders during the scanner QML checks. The test harness selects the same Basic control style as the app.

## Signing and updates

For the 4.1 software evidence, build `checks`, then run `ctest --test-dir build/checks --output-on-failure`. Run `scripts/build_iq_lab.ps1` for the 30 full-I/Q cases, atomic P25 command test and 15 app-lab cases plus four DSP comparisons. The script uses the host dependency/toolchain setup described in its parameters. Run `python -X utf8 scripts/benchmark_reception.py build/iq-lab-clang/tests/dsd-neo_test_receiver_lab.exe build/checks/channel_capture.exe` for five channel-filter cases and ten simulcast comparisons.

`scripts/generate_privacy_vectors.py` regenerates public synthetic P25 vectors using PyCryptodome 3.23.0. Regeneration needs that Python package; normal builds and tests use the included reference header and do not require it. Reference keys are fixed test data, not user secrets. `scripts/compare_receivers.py` and `docs/RECEIVER-COMPARISON.md` define the separate manual paired-radio workflow.

The first signing run creates a local XeraX release identity under `%LOCALAPPDATA%\XeraXSDR-signing`, outside the source repository. Its password is protected with Windows DPAPI for this Windows account. Preserve that directory securely: losing the signing identity prevents in-place updates to already-installed copies. The key is not the upstream project's signing key and is not included in source/output ZIPs.

The signing script aligns the APK, signs it, verifies it and writes a SHA-256 manifest. Package ID `com.xerax.sdr` permits installation alongside the original app. Public/store distribution and Play Console enrollment are separate work.

## RadioReference application key

For a keyed build, provide `DSD_RR_APP_KEY` in the build process environment, or put your approved application key in `.local/radioreference-app-key.txt`. An explicit `-RadioReferenceKeyFile <path>` argument can select another file. The local file takes precedence over the environment; an explicitly supplied path must exist. The script passes the key through the environment to the upstream generated source mechanism, without printing its value. The local file and generated build files are excluded from the source bundle. A source-only build without a key retains the editable key field.

The released 4.3.0 APK carries XeraX's approved application key. Each user still needs their own entitled RadioReference account; account credentials are never compiled into the app. Passwords remain in session memory only.

The full host suite enables offline RadioReference integration checks with `-DXERAX_EXPAT_SOURCE=<path-to-expat-source>/expat` when configuring `checks`. The host run used Expat 2.8.4, downloaded from the official `libexpat/libexpat` R_2_8_4 archive and verified against the SHA-512 in the pinned vcpkg port. These six RadioReference test groups exercise the real SOAP parser, worker/client with injected replies, CSV generators, import policy and Qt import model. They use a dummy built-in key and captured API fixtures, without a live account or curl transport. The QML suite also covers the Indio selection and keyed sign-in UI.

## Source licensing

The 3.0 host checks additionally require `XERAX_CODEC_HEADERS` pointing to a directory containing `mbelib-neo/mbelib.h` and `sndfile.h`. The default locates the headers installed by the Android build under `%LOCALAPPDATA%/XeraXSDR-build/installed/arm64-android-static/include`. Only their declarations are needed by the native payload fixtures; the host check does not link an Android binary. Run `python -X utf8 scripts/check_spanish.py` to check the receiver-tools translation coverage and placeholders. `scripts/spanish_catalog.py` regenerates the checked-in catalog.

The fixed ARC4 ciphertext in `checks/native_voice_privacy.c` was generated independently with PyCryptodome 3.23.0; that package is not required to run the tests or build the APK. Native transformation tests include production C source to reach internal functions; they do not substitute a mock decryption algorithm. Test artifacts and temporary reference dependencies under `build/` are excluded from the source ZIP.

DSD-neo is GPL-3.0-or-later, with additional embedded notices. Keep those notices and supply corresponding source when distributing this derivative. The source bundle includes the patched engine and build scripts; upstream vcpkg manifests and Qt source links identify the external dependencies. Full third-party notices ship inside the APK. See the engine's `COPYRIGHT`, `LICENSE` and `THIRD_PARTY.md`.
