param([string]$BuildCache = "$env:LOCALAPPDATA\XeraXSDR-build",
    [ValidateSet("arm64-v8a","armeabi-v7a")][string]$Abi = "arm64-v8a")
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'android_abi.ps1')
$taskTarget = Get-XeraXAndroidTarget $Abi
$repo = Split-Path $PSScriptRoot -Parent
$env:VCPKG_ROOT = Join-Path $BuildCache 'vcpkg'
$env:ANDROID_NDK_HOME = "$env:LOCALAPPDATA\Android\Sdk\ndk\28.2.13676358"
$env:XERAX_HOST_CC = (Get-Command gcc).Source.Replace('\','/')
$env:XERAX_HOST_CXX = (Get-Command g++).Source.Replace('\','/')
$env:VCPKG_KEEP_ENV_VARS = 'ANDROID_NDK_HOME;XERAX_HOST_CC;XERAX_HOST_CXX'
if (!(Test-Path "$env:VCPKG_ROOT\vcpkg.exe")) {
    if (!(Test-Path $env:VCPKG_ROOT)) {
        git clone https://github.com/microsoft/vcpkg.git $env:VCPKG_ROOT
        if ($LASTEXITCODE -ne 0) { throw 'vcpkg clone failed' }
        git -C $env:VCPKG_ROOT checkout 6e856794aebd1ee877acb74c9264d9552903c6fe
        if ($LASTEXITCODE -ne 0) { throw 'vcpkg checkout failed' }
    }
    & "$env:VCPKG_ROOT\scripts\bootstrap.ps1" -disableMetrics
}
& "$env:VCPKG_ROOT\vcpkg.exe" install --triplet $taskTarget.Triplet --host-triplet x64-mingw-static `
    "--overlay-triplets=$repo/upstream/dsd-neo/vcpkg-triplets" `
    "--overlay-ports=$repo/upstream/dsd-neo/vcpkg-ports" `
    "--x-manifest-root=$repo/upstream/dsd-neo" "--x-install-root=$BuildCache/$($taskTarget.Installed)" --clean-after-build
if ($LASTEXITCODE -ne 0) { throw 'Native dependency build failed' }
