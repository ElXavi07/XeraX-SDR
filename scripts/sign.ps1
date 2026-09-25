param([string]$BuildCache = "$env:LOCALAPPDATA\XeraXSDR-build",
    [ValidateSet("arm64-v8a","armeabi-v7a")][string]$Abi = "arm64-v8a",
    [ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9_-]*$')][string]$BuildDirectoryName)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'android_abi.ps1')
$taskTarget = Get-XeraXAndroidTarget $Abi
if ($BuildDirectoryName) { $taskTarget.Build = $BuildDirectoryName }
$repo = Split-Path $PSScriptRoot -Parent
$appRelease = (Get-Content (Join-Path $repo 'UPSTREAM.json') -Raw | ConvertFrom-Json).version
$toolsDir = "$env:LOCALAPPDATA\Android\Sdk\build-tools\36.0.0"
$jdkDir = (Get-ChildItem (Join-Path $BuildCache 'jdk') -Directory | Select-Object -First 1).FullName
$signingDir = "$env:LOCALAPPDATA\XeraXSDR-signing"
$key = Join-Path $signingDir 'xerax-sdr.jks'
$passwordFile = Join-Path $signingDir 'storepass.dpapi'
$unsigned = Join-Path $BuildCache ("$($taskTarget.Build)\android\android-build\dsd-neo-app.apk")
$aligned = Join-Path $BuildCache "XeraX-$Abi-aligned.apk"
$apkName = "XeraX-SDR-$appRelease-$($taskTarget.Suffix).apk"
$output = Join-Path $repo "dist\$apkName"
if (!(Test-Path $unsigned)) { throw "Missing unsigned APK: $unsigned" }
New-Item -ItemType Directory -Force -Path $signingDir, (Join-Path $repo 'dist') | Out-Null
if (!(Test-Path $passwordFile)) {
    if (Test-Path $key) { throw 'Existing key has no password record; leaving it unchanged.' }
    $random = [Security.Cryptography.RandomNumberGenerator]::GetBytes(32)
    $secure = ConvertTo-SecureString ([Convert]::ToBase64String($random)) -AsPlainText -Force
    ConvertFrom-SecureString $secure | Set-Content -LiteralPath $passwordFile -Encoding utf8
}
$secret = ConvertTo-SecureString ((Get-Content -LiteralPath $passwordFile -Raw).Trim())
$env:XERAX_STORE_PASSWORD = [Net.NetworkCredential]::new('', $secret).Password
try {
    if (!(Test-Path $key)) {
        & "$jdkDir\bin\keytool.exe" -genkeypair -keystore $key -alias xerax-sdr `
            -storepass:env XERAX_STORE_PASSWORD -keypass:env XERAX_STORE_PASSWORD `
            -keyalg RSA -keysize 4096 -validity 10000 -dname 'CN=XeraX SDR, O=XeraX'
        if ($LASTEXITCODE -ne 0) { throw 'Signing-key creation failed' }
    }
    & "$toolsDir\zipalign.exe" -f -P 16 4 $unsigned $aligned
    if ($LASTEXITCODE -ne 0) { throw 'APK alignment failed' }
    & "$jdkDir\bin\java.exe" -jar "$toolsDir\lib\apksigner.jar" sign `
        --ks $key --ks-key-alias xerax-sdr --ks-pass env:XERAX_STORE_PASSWORD `
        --key-pass env:XERAX_STORE_PASSWORD --out $output $aligned
    if ($LASTEXITCODE -ne 0) { throw 'APK signing failed' }
    & "$jdkDir\bin\java.exe" -jar "$toolsDir\lib\apksigner.jar" verify --verbose --print-certs $output
    if ($LASTEXITCODE -ne 0) { throw 'APK signature verification failed' }
    & "$toolsDir\zipalign.exe" -c -P 16 4 $output
    if ($LASTEXITCODE -ne 0) { throw 'Signed APK alignment verification failed' }
    $hash = (Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash.ToLower()
    $sumsPath = Join-Path $repo 'dist\SHA256SUMS.txt'
    $sumLines = @()
    if (Test-Path $sumsPath) {
        $sumLines = @(Get-Content $sumsPath | Where-Object { !$_.EndsWith("  $apkName") })
    }
    ($sumLines + "$hash  $apkName") | Set-Content $sumsPath -Encoding utf8
    Write-Output "Signed APK: $output"
} finally {
    Remove-Item Env:XERAX_STORE_PASSWORD -ErrorAction SilentlyContinue
}
