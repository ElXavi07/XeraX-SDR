$ErrorActionPreference='Stop'
$taskRepo=Split-Path $PSScriptRoot -Parent
$taskCache=Join-Path $env:USERPROFILE '.gradle/caches/modules-2/files-2.1'
$taskJava=Get-ChildItem "$env:LOCALAPPDATA/XeraXSDR-build/jdk/*/bin/java.exe" | Select-Object -First 1 -ExpandProperty FullName
function Get-TaskJar($group,$artifact,$version) {
    $taskFile=Get-ChildItem "$taskCache/$group/$artifact/$version/*/*.jar" | Select-Object -First 1 -ExpandProperty FullName
    if(!$taskFile) { throw "Missing cached compiler dependency $artifact $version" }
    return $taskFile
}
$taskStdlib=Get-TaskJar 'org.jetbrains.kotlin' 'kotlin-stdlib' '2.2.10'
$taskJars=@(
    (Get-TaskJar 'org.jetbrains.kotlin' 'kotlin-compiler-embeddable' '2.2.10'),
    $taskStdlib,
    (Get-TaskJar 'org.jetbrains.kotlin' 'kotlin-script-runtime' '2.2.10'),
    (Get-TaskJar 'org.jetbrains.kotlin' 'kotlin-reflect' '1.6.10'),
    (Get-TaskJar 'org.jetbrains.kotlin' 'kotlin-daemon-embeddable' '2.2.10'),
    (Get-TaskJar 'org.jetbrains.kotlinx' 'kotlinx-coroutines-core-jvm' '1.8.0'),
    (Get-TaskJar 'org.jetbrains' 'annotations' '13.0')
)
$taskOutput=Join-Path $taskRepo 'build/audio-focus-check.jar'
& $taskJava -cp ($taskJars -join ';') org.jetbrains.kotlin.cli.jvm.K2JVMCompiler -no-stdlib -no-reflect -classpath $taskStdlib `
    (Join-Path $taskRepo 'upstream/dsd-neo/android/package/src/io/github/arancormonk/dsdneo/AudioFocusLease.kt') `
    (Join-Path $taskRepo 'checks/AudioFocusLeaseCheck.kt') -d $taskOutput
if($LASTEXITCODE -ne 0) { throw 'Audio focus compilation failed' }
& $taskJava -cp "$taskOutput;$taskStdlib" AudioFocusLeaseCheckKt
if($LASTEXITCODE -ne 0) { throw 'Audio focus regression failed' }
