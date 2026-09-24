param([string]$BuildCache="$env:LOCALAPPDATA/XeraXSDR-build", [switch]$InstallDependencies)
$ErrorActionPreference='Stop'
$repo=(Split-Path $PSScriptRoot -Parent).Replace('\','/')
$BuildCache=$BuildCache.Replace('\','/')
$vcpkg="$BuildCache/vcpkg"
$taskMingw=(Split-Path (Split-Path (Get-Command g++).Source)).Replace('\','/')
$taskClang="$env:LOCALAPPDATA/Android/Sdk/ndk/28.2.13676358/toolchains/llvm/prebuilt/windows-x86_64/bin".Replace('\','/')
if(!(Test-Path "$taskClang/clang++.exe")) { throw 'Install the NDK used by the Android build first.' }
New-Item -ItemType Directory -Force "$repo/build" | Out-Null
if($InstallDependencies) {
    & "$vcpkg/vcpkg.exe" install 'mbe-neo:x64-mingw-static' 'libsndfile[core]:x64-mingw-static' 'codec2:x64-mingw-static' 'openssl:x64-mingw-static' --classic "--overlay-ports=$repo/upstream/dsd-neo/vcpkg-ports" "--x-install-root=$BuildCache/lab-installed"
    if($LASTEXITCODE -ne 0) { throw 'Host lab dependencies failed.' }
}
# Clang uses native Windows TLS. The installed GCC's emulated TLS destroys C++
# thread-local storage before running destructors during full DSP thread teardown.
@"
set(CMAKE_SYSTEM_NAME Windows)
set(CMAKE_SYSTEM_PROCESSOR AMD64)
set(CMAKE_C_COMPILER "$taskClang/clang.exe" CACHE FILEPATH "" FORCE)
set(CMAKE_CXX_COMPILER "$taskClang/clang++.exe" CACHE FILEPATH "" FORCE)
set(CMAKE_C_COMPILER_TARGET x86_64-w64-windows-gnu)
set(CMAKE_CXX_COMPILER_TARGET x86_64-w64-windows-gnu)
set(CMAKE_SYSROOT "$taskMingw")
"@ | Set-Content "$repo/build/iq-host-clang.cmake"
cmake -S "$repo/upstream/dsd-neo" -B "$repo/build/iq-lab-clang" -G Ninja -DCMAKE_BUILD_TYPE=Release `
    "-DCMAKE_TOOLCHAIN_FILE=$vcpkg/scripts/buildsystems/vcpkg.cmake" "-DVCPKG_CHAINLOAD_TOOLCHAIN_FILE=$repo/build/iq-host-clang.cmake" `
    -DVCPKG_TARGET_TRIPLET=x64-mingw-static -DVCPKG_HOST_TRIPLET=x64-mingw-static "-DVCPKG_INSTALLED_DIR=$BuildCache/lab-installed" -DVCPKG_MANIFEST_MODE=OFF `
    -DDSD_ENABLE_TERMINAL_UI=OFF -DDSD_ENABLE_QT_UI=OFF -DDSD_ENABLE_RTLSDR=OFF -DDSD_ENABLE_AIRSPY=OFF -DDSD_ENABLE_SOAPYSDR=OFF `
    -DDSD_FORCE_RADIO_PIPELINE=ON -DDSD_AUDIO_BACKEND=none -DDSD_WARNINGS_AS_ERRORS=OFF -DBUILD_TESTING=ON `
    -DCMAKE_DISABLE_FIND_PACKAGE_CURL=ON -DCMAKE_DISABLE_FIND_PACKAGE_EXPAT=ON '-DCMAKE_EXE_LINKER_FLAGS=-pthread'
if($LASTEXITCODE -ne 0) { throw 'Host lab configure failed.' }
cmake --build "$repo/build/iq-lab-clang" --target dsd-neo dsd-neo_test_scan_mode_replay dsd-neo_test_receiver_lab dsd-neo_test_p25_voice_tune --parallel 8
if($LASTEXITCODE -ne 0) { throw 'Host lab build failed.' }
ctest --test-dir "$repo/build/iq-lab-clang" -R '^DECODE_IQ_' --output-on-failure --parallel 4
if($LASTEXITCODE -ne 0) { throw 'Full I/Q regression failed.' }
ctest --test-dir "$repo/build/iq-lab-clang" -R '^P25_ATOMIC_VOICE_TUNE$' --output-on-failure
if($LASTEXITCODE -ne 0) { throw 'Atomic voice tune regression failed.' }
python -X utf8 "$repo/scripts/run_iq_lab.py" "$repo/build/iq-lab-clang/tests/dsd-neo_test_receiver_lab.exe" --output "$repo/build/iq-lab-report"
if($LASTEXITCODE -ne 0) { throw 'Android lab parity cases failed.' }
