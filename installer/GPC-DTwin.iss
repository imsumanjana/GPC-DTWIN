#define MyAppName "GPC-DTwin"
#define MyAppVersion "1.1.5"
#define MyAppPublisher "Dr. Suman Jana"
#define MyAppExeName "GPC-DTwin.exe"
#define MyAppURL "https://orcid.org/0000-0002-9850-2169"
#define MyAppCopyright "Copyright © 2026 Dr. Suman Jana. All rights reserved."

[Setup]
; Never change this AppId in future versions.
AppId={{D9B89B2F-9B2E-47CF-B55A-45783F3C4F8E}

AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}

AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

DefaultDirName={autopf}\GPC-DTwin
DefaultGroupName=GPC-DTwin
DisableProgramGroupPage=yes
AllowNoIcons=yes

; 64-bit installer.
SetupArchitecture=x64
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

PrivilegesRequired=admin
MinVersion=10.0

OutputDir=..\release
OutputBaseFilename=GPC-DTwin-v1.1.5-Setup-x64

; Installer, uninstaller and Apps & Features icons.
SetupIconFile=..\resources\GPC-DTwin.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName=GPC-DTwin v{#MyAppVersion}

; Modern adaptive installer.
WizardStyle=modern dynamic polar includetitlebar hidebevels
WizardResizable=yes
WizardSizePercent=125,120
DisableWelcomePage=no
DisableReadyPage=no
DisableFinishedPage=no

; Use the logo-only PNG in the installer header.
WizardSmallImageFile=..\resources\GPC-DTwin.png
WizardSmallImageFileDynamicDark=..\resources\GPC-DTwin.png

Compression=lzma2/max
SolidCompression=yes

CloseApplications=yes
RestartApplications=no
UsePreviousAppDir=yes
SetupLogging=yes

VersionInfoVersion=1.1.5.0
VersionInfoProductVersion=1.1.5.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoProductName={#MyAppName}
VersionInfoDescription=Materials analytics and digital-twin platform
VersionInfoCopyright={#MyAppCopyright}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; \
    Description: "Create a desktop shortcut"; \
    GroupDescription: "Additional shortcuts:"; \
    Flags: unchecked

[Files]
; Install the complete PyInstaller one-folder package.
Source: "..\dist\GPC-DTwin\*"; \
    DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\GPC-DTwin"; \
    Filename: "{app}\{#MyAppExeName}"; \
    WorkingDir: "{app}"; \
    IconFilename: "{app}\{#MyAppExeName}"

Name: "{autodesktop}\GPC-DTwin"; \
    Filename: "{app}\{#MyAppExeName}"; \
    WorkingDir: "{app}"; \
    IconFilename: "{app}\{#MyAppExeName}"; \
    Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; \
    Description: "Launch GPC-DTwin"; \
    WorkingDir: "{app}"; \
    Flags: nowait postinstall skipifsilent
