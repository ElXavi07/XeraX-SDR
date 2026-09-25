#ifndef StageDir
  #error StageDir must be the validated portable application directory.
#endif
[Setup]
#ifdef TestInstall
; Validation uses a separate uninstall identity; never replace an existing user's registration.
AppId=XeraX-SDR-Installer-Validation
DefaultGroupName=XeraX SDR Installer Validation
#else
AppId={{729E7604-9468-4C09-BDD7-155E4538FA46}
DefaultGroupName=XeraX SDR
#endif
AppName=XeraX SDR
AppVersion=4.3.0-windows.3
AppPublisher=XeraX SDR community
AppPublisherURL=https://github.com/ElXavi07/XeraX-SDR
DefaultDirName={localappdata}\Programs\XeraX SDR
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename=XeraX-SDR-4.3.0-windows.3-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\upstream\dsd-neo\windows\XeraX-SDR.ico
LicenseFile={#StageDir}\LICENSE.txt
InfoBeforeFile={#StageDir}\INSTALL-NOTES.txt
UninstallDisplayIcon={app}\XeraX-SDR.exe
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\XeraX SDR"; Filename: "{app}\XeraX-SDR.exe"; AppUserModelID: "XeraX.SDR.Desktop"
Name: "{autodesktop}\XeraX SDR"; Filename: "{app}\XeraX-SDR.exe"; Tasks: desktopicon; AppUserModelID: "XeraX.SDR.Desktop"
[Run]
Filename: "{app}\XeraX-SDR.exe"; Description: "{cm:LaunchProgram,XeraX SDR}"; Flags: nowait postinstall skipifsilent
