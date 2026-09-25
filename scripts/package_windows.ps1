param([string]$BuildCache="$env:LOCALAPPDATA/XeraXSDR-build",[switch]$StageOnly)
$ErrorActionPreference='Stop'
$taskRepo=(Split-Path $PSScriptRoot -Parent)
$taskQt="$BuildCache/QtKits/6.11.2/mingw_64"
$taskMingw=Split-Path (Get-Command g++).Source
$taskStage="$taskRepo/dist/XeraX-SDR-4.3.0-windows.3-x64"
$taskDeps="$BuildCache/lab-installed/x64-mingw-static"
New-Item -ItemType Directory -Force $taskStage | Out-Null
Copy-Item "$BuildCache/windows-app/windows/XeraX-SDR.exe" $taskStage
Copy-Item "$BuildCache/windows-app/apps/dsd-cli/dsd-neo.exe" $taskStage
$env:Path="$taskQt/bin;$taskMingw;"+$env:Path
& "$taskQt/bin/windeployqt.exe" --release --no-translations --no-opengl-sw --qmldir "$taskRepo/upstream/dsd-neo/src/ui/qt/qml" --dir $taskStage "$taskStage/XeraX-SDR.exe"
if($LASTEXITCODE -ne 0) {throw 'Qt deployment failed'}
# Include the matching offscreen platform for the distributed software-test harness.
Copy-Item "$taskQt/plugins/platforms/qoffscreen.dll" "$taskStage/platforms"
Copy-Item "$taskDeps/bin/*.dll" $taskStage
foreach($taskName in @('libstdc++-6.dll','libgcc_s_seh-1.dll','libwinpthread-1.dll')) { Copy-Item "$taskMingw/$taskName" $taskStage }
Copy-Item "$taskRepo/LICENSE" "$taskStage/LICENSE.txt"
Copy-Item "$taskRepo/docs/WINDOWS.md" "$taskStage/START-HERE.txt"
Copy-Item "$taskRepo/docs/WINDOWS-INSTALL.txt" "$taskStage/INSTALL-NOTES.txt"
Copy-Item "$taskRepo/upstream/dsd-neo/THIRD_PARTY.md" "$taskStage/THIRD_PARTY.txt"
New-Item -ItemType Directory -Force "$taskStage/licenses" | Out-Null
foreach($taskNotice in Get-ChildItem "$taskDeps/share/*/copyright") {
    Copy-Item -LiteralPath $taskNotice.FullName -Destination "$taskStage/licenses/$($taskNotice.Directory.Name).txt"
}
Copy-Item "$taskRepo/upstream/dsd-neo/android/package/assets/doc/xerax/qt/*.txt" "$taskStage/licenses"
Copy-Item "$taskRepo/upstream/dsd-neo/android/package/assets/doc/xerax/NOTICE.txt" "$taskStage/licenses/ENGINE-NOTICE.txt"
Copy-Item "$taskRepo/docs/windows-licenses/*.txt" "$taskStage/licenses"
if(Test-Path "$taskQt/sbom") {
    New-Item -ItemType Directory -Force "$taskStage/licenses/qt-sbom" | Out-Null
    Copy-Item -Recurse -Force "$taskQt/sbom/*" "$taskStage/licenses/qt-sbom"
}
@'
[Paths]
Prefix=.
Plugins=.
QmlImports=qml
'@ | Set-Content "$taskStage/qt.conf"
if($StageOnly) {Write-Output $taskStage;return}
Compress-Archive -Path "$taskStage/*" -DestinationPath "$taskStage-portable.zip" -Force
& "$BuildCache/InnoSetup/ISCC.exe" "/DStageDir=$taskStage" "/DOutputDir=$taskRepo/dist" "$taskRepo/scripts/windows-installer.iss"
if($LASTEXITCODE -ne 0) {throw 'Windows installer compilation failed'}
Get-ChildItem "$taskRepo/dist/*windows.3*.exe","$taskStage-portable.zip" | Get-FileHash -Algorithm SHA256
