param(
    [string]$BuildCache = "$env:LOCALAPPDATA\XeraXSDR-build",
    [string]$RadioReferenceKeyFile,
    [ValidateSet('arm64-v8a','armeabi-v7a')][string]$Abi = 'arm64-v8a',
    [ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9_-]*$')][string]$BuildDirectoryName,
    [switch]$ConfigureOnly
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'android_abi.ps1')
$taskTarget = Get-XeraXAndroidTarget $Abi
if ($BuildDirectoryName) { $taskTarget.Build = $BuildDirectoryName }
$repo = (Split-Path $PSScriptRoot -Parent).Replace('\','/')
$BuildCache = $BuildCache.Replace('\','/')
$source = Join-Path $repo 'upstream\dsd-neo'
if ($RadioReferenceKeyFile -and !(Test-Path -LiteralPath $RadioReferenceKeyFile -PathType Leaf)) {
    throw 'The specified RadioReference key file does not exist.'
}
if (!$RadioReferenceKeyFile) { $RadioReferenceKeyFile = Join-Path $repo '.local/radioreference-app-key.txt' }
if (Test-Path -LiteralPath $RadioReferenceKeyFile) {
    $env:DSD_RR_APP_KEY = (Get-Content -LiteralPath $RadioReferenceKeyFile -Raw).Trim()
}
if ($env:DSD_RR_APP_KEY) { Write-Output 'RadioReference application key supplied for this build.' }
$build = Join-Path $BuildCache $taskTarget.Build
$env:VCPKG_ROOT = Join-Path $BuildCache 'vcpkg'
$env:ANDROID_SDK_ROOT = "$env:LOCALAPPDATA/Android/Sdk".Replace('\','/')
$env:ANDROID_NDK_ROOT = Join-Path $env:ANDROID_SDK_ROOT 'ndk\28.2.13676358'
$env:ANDROID_NDK_HOME = $env:ANDROID_NDK_ROOT
$env:QT_ANDROID_ROOT = Join-Path $BuildCache ("QtKits\6.11.2\" + $taskTarget.Kit)
$env:QT_HOST_ROOT = Join-Path $BuildCache 'QtKits\6.11.2\mingw_64'
$env:QT_HOST_ROOT = $env:QT_HOST_ROOT.Replace('\','/')
$env:QT_ANDROID_ROOT = $env:QT_ANDROID_ROOT.Replace('\','/')
$env:ANDROID_NDK_ROOT = $env:ANDROID_NDK_ROOT.Replace('\','/')
$env:JAVA_HOME = (Get-ChildItem (Join-Path $BuildCache 'jdk') -Directory | Select-Object -First 1).FullName
$env:XERAX_HOST_CC = (Get-Command gcc).Source.Replace('\','/')
$env:XERAX_HOST_CXX = (Get-Command g++).Source.Replace('\','/')
$env:VCPKG_KEEP_ENV_VARS = 'ANDROID_NDK_HOME;XERAX_HOST_CC;XERAX_HOST_CXX'
$env:Path = "$env:JAVA_HOME\bin;$env:QT_HOST_ROOT\bin;$env:SystemRoot\System32;$env:SystemRoot\System32\WindowsPowerShell\v1.0;" + $env:Path
$cmake = (Get-ChildItem "$BuildCache\vcpkg\downloads\tools\cmake*\*\bin\cmake.exe" | Select-Object -First 1).FullName
if (!$cmake) { $cmake = (Get-Command cmake).Source }
$ninja = (Get-Command ninja).Source
python (Join-Path $PSScriptRoot 'stage_notices.py') $BuildCache --abi $Abi
if ($LASTEXITCODE -ne 0) { throw 'License staging failed' }
& $cmake -S $source -B $build -G Ninja `
    "-DCMAKE_MAKE_PROGRAM=$ninja" `
    "-DCMAKE_TOOLCHAIN_FILE=$env:VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake" `
    "-DVCPKG_CHAINLOAD_TOOLCHAIN_FILE=$env:QT_ANDROID_ROOT/lib/cmake/Qt6/qt.toolchain.cmake" `
    "-DVCPKG_TARGET_TRIPLET=$($taskTarget.Triplet)" '-DVCPKG_HOST_TRIPLET=x64-mingw-static' `
    "-DVCPKG_OVERLAY_TRIPLETS=$source/vcpkg-triplets" `
    "-DVCPKG_OVERLAY_PORTS=$source/vcpkg-ports" `
    "-DVCPKG_INSTALLED_DIR=$BuildCache/$($taskTarget.Installed)" '-DVCPKG_MANIFEST_INSTALL=OFF' `
    "-DQT_HOST_PATH=$env:QT_HOST_ROOT" "-DANDROID_NDK=$env:ANDROID_NDK_ROOT" `
    "-DANDROID_SDK_ROOT=$env:ANDROID_SDK_ROOT" `
    "-DANDROID_ABI=$Abi" '-DANDROID_PLATFORM=android-29' `
    '-DCMAKE_BUILD_TYPE=Release' '-DBUILD_TESTING=OFF' `
    '-DCMAKE_C_FLAGS_RELEASE=-O3 -DNDEBUG -flto=thin' `
    '-DCMAKE_CXX_FLAGS_RELEASE=-O3 -DNDEBUG -flto=thin' `
    '-DCMAKE_SHARED_LINKER_FLAGS=-flto=thin -fuse-ld=lld' `
    '-DDSD_ENABLE_TERMINAL_UI=OFF' '-DDSD_ENABLE_QT_UI=ON' `
    '-DDSD_AUDIO_BACKEND=aaudio' '-DDSD_FORCE_RADIO_PIPELINE=ON' `
    '-DDSD_ENABLE_RTLSDR=ON' '-DDSD_ANDROID_VENDORED_RTLSDR=ON' `
    '-DDSD_ENABLE_AIRSPY=ON' '-DDSD_ENABLE_SOAPYSDR=OFF' `
    '-DDSD_REQUIRE_CODEC2=ON' '-DDSD_REQUIRE_CURL=ON' '-DDSD_REQUIRE_EXPAT=ON' `
    '-DDSD_ENABLE_LTO=OFF' '-DDSD_WARNINGS_AS_ERRORS=ON' '-DDSD_RR_APP_KEY='
if ($LASTEXITCODE -ne 0) { throw 'CMake configure failed' }
if ($ConfigureOnly) { return }
& $cmake --build $build --target apk --parallel 8
if ($LASTEXITCODE -ne 0) { throw 'APK build failed' }
Write-Output "Unsigned APK: $build\android\android-build\dsd-neo-app.apk"
