#ifndef AppVersion
  #define AppVersion "1.8.0"
#endif

#define AppName "Sindrome Chat Overlay"
#define AppExeName "SindromeChatOverlay.exe"
#define AppPublisher "Sindrome Games"
#define AppUrl "https://github.com/felipinhobxd/Sindrome-Chat-Overlay"

[Setup]
AppId={{E90213A4-73D5-4A35-85DD-F00BD0766535}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
AppUpdatesURL={#AppUrl}/releases/latest
DefaultDirName={localappdata}\Programs\Sindrome Chat Overlay
DefaultGroupName=Sindrome Chat Overlay
DisableProgramGroupPage=yes
OutputDir=..\release
OutputBaseFilename=SindromeChatOverlay-Setup-v{#AppVersion}
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
VersionInfoVersion={#AppVersion}.0
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} installer
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
VersionInfoCopyright=Copyright (c) 2026 Sindrome Games

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\SindromeChatOverlay.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Sindrome Chat Overlay"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{group}\Uninstall Sindrome Chat Overlay"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Sindrome Chat Overlay"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,Sindrome Chat Overlay}"; Flags: nowait postinstall skipifsilent; BeforeInstall: PrepareCleanPyInstallerLaunch

[Code]
function SetEnvironmentVariable(Name: string; Value: string): Boolean;
  external 'SetEnvironmentVariableW@kernel32.dll stdcall';

procedure PrepareCleanPyInstallerLaunch;
begin
  if SetEnvironmentVariable('PYINSTALLER_RESET_ENVIRONMENT', '1') then
    Log('Prepared clean PyInstaller environment for the post-install launch.')
  else
    Log('Warning: unable to set PYINSTALLER_RESET_ENVIRONMENT for the post-install launch.');
end;
