param([string]$BuildCache="$env:LOCALAPPDATA/XeraXSDR-build", [switch]$InstallDependencies, [switch]$ConfigureOnly, [string]$RadioReferenceKeyFile)
$ErrorActionPreference='Stop'
$taskRepo=(Split-Path $PSScriptRoot -Parent).Replace('\','/')
$BuildCache=$BuildCache.Replace('\','/')
$taskVcpkg="$BuildCache/vcpkg"
$taskQt="$BuildCache/QtKits/6.11.2/mingw_64"
$taskMingw=(Split-Path (Split-Path (Get-Command g++).Source)).Replace('\','/')
$taskClang="$env:LOCALAPPDATA/Android/Sdk/ndk/28.2.13676358/toolchains/llvm/prebuilt/windows-x86_64/bin".Replace('\','/')
$taskBuild="$BuildCache/windows-app"
if($RadioReferenceKeyFile) { $env:DSD_RR_APP_KEY=(Get-Content -Raw -LiteralPath $RadioReferenceKeyFile).Trim() }
if(!(Test-Path "$taskClang/clang++.exe") -or !(Test-Path "$taskQt/bin/windeployqt.exe")) { throw 'Install the documented NDK Clang and Qt Windows host kit first.' }
if($InstallDependencies) {
    & "$taskVcpkg/vcpkg.exe" install 'mbe-neo:x64-mingw-static' 'libsndfile[core]:x64-mingw-static' 'codec2:x64-mingw-static' 'openssl:x64-mingw-static' 'portaudio:x64-mingw-static' 'rtlsdr:x64-mingw-static' 'airspy:x64-mingw-static' 'curl[core,ssl]:x64-mingw-static' 'expat:x64-mingw-static' --classic --host-triplet=x64-mingw-static "--overlay-ports=$taskRepo/upstream/dsd-neo/vcpkg-ports" "--x-install-root=$BuildCache/lab-installed"
    if($LASTEXITCODE -ne 0) { throw 'Windows dependency installation failed.' }
}
New-Item -ItemType Directory -Force $taskBuild | Out-Null
@"
set(CMAKE_SYSTEM_NAME Windows)
set(CMAKE_SYSTEM_PROCESSOR AMD64)
set(CMAKE_C_COMPILER "$taskClang/clang.exe" CACHE FILEPATH "" FORCE)
set(CMAKE_CXX_COMPILER "$taskClang/clang++.exe" CACHE FILEPATH "" FORCE)
set(CMAKE_C_COMPILER_TARGET x86_64-w64-windows-gnu)
set(CMAKE_CXX_COMPILER_TARGET x86_64-w64-windows-gnu)
set(CMAKE_SYSROOT "$taskMingw")
"@ | Set-Content "$taskBuild/toolchain.cmake"
$env:Path="$taskQt/bin;$taskMingw/bin;"+$env:Path
cmake -S "$taskRepo/upstream/dsd-neo" -B $taskBuild -G Ninja -DCMAKE_BUILD_TYPE=Release `
    "-DCMAKE_TOOLCHAIN_FILE=$taskVcpkg/scripts/buildsystems/vcpkg.cmake" "-DVCPKG_CHAINLOAD_TOOLCHAIN_FILE=$taskBuild/toolchain.cmake" `
    -DVCPKG_TARGET_TRIPLET=x64-mingw-static -DVCPKG_HOST_TRIPLET=x64-mingw-static "-DVCPKG_INSTALLED_DIR=$BuildCache/lab-installed" -DVCPKG_MANIFEST_MODE=OFF `
    "-DCMAKE_PREFIX_PATH=$taskQt" -DDSD_ENABLE_TERMINAL_UI=OFF -DDSD_ENABLE_QT_UI=ON `
    -DDSD_ENABLE_RTLSDR=ON -DDSD_REQUIRE_RTLSDR=ON -DDSD_ENABLE_AIRSPY=ON -DDSD_REQUIRE_AIRSPY=ON -DDSD_ENABLE_SOAPYSDR=OFF `
    -DDSD_REQUIRE_CODEC2=ON -DDSD_REQUIRE_CURL=ON -DDSD_REQUIRE_EXPAT=ON -DDSD_FORCE_RADIO_PIPELINE=ON `
    -DDSD_AUDIO_BACKEND=portaudio -DDSD_WARNINGS_AS_ERRORS=OFF -DBUILD_TESTING=ON '-DCMAKE_EXE_LINKER_FLAGS=-pthread'
if($LASTEXITCODE -ne 0) { throw 'Windows configure failed.' }
if($ConfigureOnly) { return }
cmake --build $taskBuild --target xerax-sdr dsd-neo --parallel 8
if($LASTEXITCODE -ne 0) { throw 'Windows build failed.' }
Write-Output "Windows GUI: $taskBuild/windows/XeraX-SDR.exe"
