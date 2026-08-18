#define MyAppName "GPC-DTwin"
#define MyAppVersion "1.2.6"
#define MyAppPublisher "Dr. Suman Jana"
#define MyAppExeName "GPC-DTwin.exe"
#define MyAppURL "https://orcid.org/0000-0002-9850-2169"
#define MyAppCopyright "Copyright © 2026 Dr. Suman Jana. All rights reserved."

[Setup]
; ============================================================
; GPC-DTwin Windows Installer
; Compatible with Inno Setup 5.5 / 5.6
;
; IMPORTANT:
; Never change this AppId in future GPC-DTwin versions.
; ============================================================

AppId={{D9B89B2F-9B2E-47CF-B55A-45783F3C4F8E}

AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}

AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; ------------------------------------------------------------
; Installation location
;
; In 64-bit install mode {pf} resolves to the native
; 64-bit Program Files directory.
; ------------------------------------------------------------

DefaultDirName={pf}\{#MyAppName}
DefaultGroupName={#MyAppName}

DisableProgramGroupPage=yes
AllowNoIcons=yes

; ------------------------------------------------------------
; Architecture
;
; GPC-DTwin is built by PyInstaller as Windows x64.
;
; Use "x64", NOT "x64compatible", because x64compatible
; belongs to newer Inno Setup versions.
; ------------------------------------------------------------

ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

PrivilegesRequired=admin

; Windows 10 or later
MinVersion=10.0

; ------------------------------------------------------------
; Installer output
; ------------------------------------------------------------

OutputDir=..\release
OutputBaseFilename={#MyAppName}-v{#MyAppVersion}-Setup-x64

; ------------------------------------------------------------
; Installer icon / Apps & Features
; ------------------------------------------------------------

SetupIconFile=..\resources\GPC-DTwin.ico

UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} v{#MyAppVersion}

; ------------------------------------------------------------
; IMPORTANT:
;
; No WizardStyle directive here.
; No WizardSizePercent.
; No DynamicDark.
; No SetupArchitecture.
;
; These require newer versions of Inno Setup.
; The compiler will use its native/default wizard appearance.
; ------------------------------------------------------------

DisableWelcomePage=no
DisableReadyPage=no
DisableFinishedPage=no

; ------------------------------------------------------------
; Compression
; ------------------------------------------------------------

Compression=lzma2/max
SolidCompression=yes

; ------------------------------------------------------------
; Upgrade behaviour
;
; Restart Manager support exists in Inno Setup 5.5+.
; ------------------------------------------------------------

CloseApplications=yes
RestartApplications=no

UsePreviousAppDir=yes

; ------------------------------------------------------------
; Version metadata
; ------------------------------------------------------------

VersionInfoVersion={#MyAppVersion}.0
VersionInfoProductVersion={#MyAppVersion}.0
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


[InstallDelete]

; ============================================================
; Remove the previous PyInstaller runtime during upgrades.
;
; GPC-DTwin is a PyInstaller one-folder application.
; Most Python packages, Qt files, DLLs and scientific libraries
; are located in _internal.
;
; Cleaning this directory prevents obsolete runtime files from
; older releases remaining after an in-place upgrade.
; ============================================================

Type: filesandordirs; Name: "{app}\_internal"


[Files]

; ============================================================
; Install the COMPLETE PyInstaller one-folder application.
;
; Expected structure:
;
; dist\
;   GPC-DTwin\
;       GPC-DTwin.exe
;       _internal\
;       ...
;
; Everything in dist\GPC-DTwin is copied recursively.
; ============================================================

Source: "..\dist\GPC-DTwin\*"; \
    DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs


[Icons]

; ------------------------------------------------------------
; Start Menu shortcut
; ------------------------------------------------------------

Name: "{group}\{#MyAppName}"; \
    Filename: "{app}\{#MyAppExeName}"; \
    WorkingDir: "{app}"; \
    IconFilename: "{app}\{#MyAppExeName}"


; ------------------------------------------------------------
; Optional desktop shortcut
; ------------------------------------------------------------

Name: "{commondesktop}\{#MyAppName}"; \
    Filename: "{app}\{#MyAppExeName}"; \
    WorkingDir: "{app}"; \
    IconFilename: "{app}\{#MyAppExeName}"; \
    Tasks: desktopicon


[Run]

; ------------------------------------------------------------
; Offer to launch GPC-DTwin after installation.
; Not executed during silent installation.
; ------------------------------------------------------------

Filename: "{app}\{#MyAppExeName}"; \
    Description: "Launch {#MyAppName}"; \
    WorkingDir: "{app}"; \
    Flags: nowait postinstall skipifsilent