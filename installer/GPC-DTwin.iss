#define MyAppName "GPC-DTwin"
#define MyAppVersion "1.2.6"
#define MyAppPublisher "Dr. Suman Jana"
#define MyAppExeName "GPC-DTwin.exe"
#define MyAppURL "https://orcid.org/0000-0002-9850-2169"
#define MyAppCopyright "Copyright © 2026 Dr. Suman Jana. All rights reserved."

[Setup]
; ============================================================
; GPC-DTwin Windows Installer
;
; Build requirement: Inno Setup 6.3 or newer.
;
; Target systems for this x64 application build:
;   - Windows 10 version 1809 or later, x64
;   - Windows 11, x64
;   - Windows 11 on ARM64 where Windows x64 emulation is available
;
; Home / Pro / Education / Enterprise editions use the same package.
;
; IMPORTANT: Never change this AppId in future versions.
; ============================================================

AppId={{D9B89B2F-9B2E-47CF-B55A-45783F3C4F8E}

AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}

AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; In 64-bit install mode {autopf} resolves to the native Program Files folder.
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
AllowNoIcons=yes

; x64compatible is deliberate. It accepts native x64 Windows and Windows 11
; ARM64 systems that can execute x64 applications through Windows emulation.
; Do not change this back to the deprecated x64/x64os restriction.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

PrivilegesRequired=admin

; Qt 6.11 supports Windows 10 1809+ and Windows 11.
MinVersion=10.0.17763

OutputDir=..\release
OutputBaseFilename={#MyAppName}-v{#MyAppVersion}-Setup-Windows64

SetupIconFile=..\resources\GPC-DTwin.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} v{#MyAppVersion}

; Compatible with Inno Setup 6.3+ while retaining the modern wizard.
WizardStyle=modern
DisableWelcomePage=no
DisableReadyPage=no
DisableFinishedPage=no

Compression=lzma2/max
SolidCompression=yes

CloseApplications=yes
RestartApplications=no
UsePreviousAppDir=yes
SetupLogging=yes

VersionInfoVersion={#MyAppVersion}.0
VersionInfoProductVersion={#MyAppVersion}.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoProductName={#MyAppName}
VersionInfoDescription=Materials analytics and digital-twin platform
VersionInfoCopyright={#MyAppCopyright}


[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"


[Messages]
WindowsVersionNotSupported={#MyAppName} requires Windows 10 version 1809 or later on an x64 PC, or Windows 11 on ARM64 with x64 application emulation.


[Tasks]
Name: "desktopicon"; \
    Description: "Create a desktop shortcut"; \
    GroupDescription: "Additional shortcuts:"; \
    Flags: unchecked


[InstallDelete]
; Remove the old PyInstaller runtime before an in-place upgrade so stale
; DLLs, Qt plugins, or Python modules cannot survive between releases.
Type: filesandordirs; Name: "{app}\_internal"


[Files]
; Install the complete validated PyInstaller one-folder package.
Source: "..\dist\GPC-DTwin\*"; \
    DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs


[Icons]
Name: "{group}\{#MyAppName}"; \
    Filename: "{app}\{#MyAppExeName}"; \
    WorkingDir: "{app}"; \
    IconFilename: "{app}\{#MyAppExeName}"

Name: "{commondesktop}\{#MyAppName}"; \
    Filename: "{app}\{#MyAppExeName}"; \
    WorkingDir: "{app}"; \
    IconFilename: "{app}\{#MyAppExeName}"; \
    Tasks: desktopicon


[Run]
Filename: "{app}\{#MyAppExeName}"; \
    Description: "Launch {#MyAppName}"; \
    WorkingDir: "{app}"; \
    Flags: nowait postinstall skipifsilent
