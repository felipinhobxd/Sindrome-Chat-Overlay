#ifndef AppVersion
  #define AppVersion "1.8.4"
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
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=SindromeChatOverlay-Setup-v{#AppVersion}
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
AppMutex=SindromeChatOverlay.Singleton
DisableProgramGroupPage=yes
DisableWelcomePage=no
LicenseFile=..\LICENSE
VersionInfoVersion={#AppVersion}.0
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Setup
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}

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
Name: "{group}\Sindrome Chat Overlay"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\Sindrome Chat Overlay"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
Name: "{group}\Uninstall Sindrome Chat Overlay"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,Sindrome Chat Overlay}"; Flags: nowait postinstall skipifsilent; BeforeInstall: PrepareCleanPyInstallerLaunch

[Code]
function SetEnvironmentVariableW(lpName: string; lpValue: string): Boolean;
  external 'SetEnvironmentVariableW@kernel32.dll stdcall';

procedure PrepareCleanPyInstallerLaunch;
begin
  if not SetEnvironmentVariableW('PYINSTALLER_RESET_ENVIRONMENT', '1') then
    RaiseException('Unable to prepare a clean application launch environment.');
end;
