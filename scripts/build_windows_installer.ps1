param(
    [switch]$SkipAppBuild
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if (-not $SkipAppBuild) {
    Write-Host "[GPC-DTwin] Building validated Windows application first..." -ForegroundColor Cyan
    & (Join-Path $PSScriptRoot "build_windows.ps1")
    if ($LASTEXITCODE -ne 0) { throw "Application build failed." }
}

$DistExe = Join-Path $RepoRoot "dist\GPC-DTwin\GPC-DTwin.exe"
if (-not (Test-Path $DistExe)) {
    throw "Validated PyInstaller output not found at dist\GPC-DTwin\GPC-DTwin.exe. Run build_windows.ps1 first."
}

$CandidatePaths = @(
    (Join-Path ${env:ProgramFiles} "Inno Setup 7\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 7\ISCC.exe"),
    (Join-Path ${env:ProgramFiles} "Inno Setup 6\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe")
)

$ISCC = $null
foreach ($Candidate in $CandidatePaths) {
    if ($Candidate -and (Test-Path $Candidate)) {
        $ISCC = $Candidate
        break
    }
}
if (-not $ISCC) {
    $Command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($Command) { $ISCC = $Command.Source }
}
if (-not $ISCC) {
    throw "Inno Setup Compiler was not found. Install Inno Setup 6.3 or newer, then run this script again."
}

# Some current Inno Setup 7 ISCC.exe builds expose ProductVersion as 0.0.0
# through Windows file metadata. Treat file metadata as informational only and
# verify the feature we actually require: support for x64compatible.
$VersionInfo = (Get-Item $ISCC).VersionInfo
$InnoVersion = $null
foreach ($RawVersion in @($VersionInfo.FileVersion, $VersionInfo.ProductVersion)) {
    if ([string]::IsNullOrWhiteSpace($RawVersion)) { continue }
    $VersionMatch = [regex]::Match($RawVersion, '\d+\.\d+(?:\.\d+)?(?:\.\d+)?')
    if (-not $VersionMatch.Success) { continue }
    try {
        $CandidateVersion = [version]$VersionMatch.Value
        if ($CandidateVersion.Major -gt 0) {
            $InnoVersion = $CandidateVersion
            break
        }
    } catch {
        # Continue to the capability probe below.
    }
}

if ($InnoVersion) {
    Write-Host "[GPC-DTwin] Inno Setup metadata version: $InnoVersion" -ForegroundColor Cyan
} else {
    Write-Host "[GPC-DTwin] Inno Setup metadata version: unavailable/0.0.0" -ForegroundColor Yellow
}
Write-Host "[GPC-DTwin] Compiler: $ISCC"

# Capability probe is authoritative. It avoids false failures when ISCC.exe
# reports ProductVersion=0.0.0 while still being a modern Inno Setup 7 compiler.
$ProbeRoot = Join-Path $RepoRoot ".runtime\inno-capability-probe"
$ProbeIss = Join-Path $ProbeRoot "x64compatible-probe.iss"
New-Item -ItemType Directory -Force -Path $ProbeRoot | Out-Null
@'
[Setup]
AppName=GPC-DTwin Inno Capability Probe
AppVersion=1.0
DefaultDirName={tmp}\GPC-DTwin-Inno-Probe
Uninstallable=no
Output=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
'@ | Set-Content -Encoding UTF8 $ProbeIss

Write-Host "[GPC-DTwin] Verifying x64compatible installer support..." -ForegroundColor Cyan
$ProbeLog = & $ISCC /Q $ProbeIss 2>&1
$ProbeExitCode = $LASTEXITCODE
Remove-Item -Recurse -Force $ProbeRoot -ErrorAction SilentlyContinue

if ($ProbeExitCode -ne 0) {
    $ProbeText = ($ProbeLog | Out-String).Trim()
    throw "The installed Inno Setup compiler does not support the required x64compatible architecture mode. Install Inno Setup 6.3 or newer. Compiler: $ISCC`n$ProbeText"
}
Write-Host "[GPC-DTwin] x64compatible support verified." -ForegroundColor Green

$ReleaseDir = Join-Path $RepoRoot "release"
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
Get-ChildItem $ReleaseDir -Filter "GPC-DTwin-v*-Setup-Windows64.exe" -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem $ReleaseDir -Filter "GPC-DTwin-v*-Setup-Windows64.exe.sha256.txt" -ErrorAction SilentlyContinue | Remove-Item -Force

$IssFile = Join-Path $RepoRoot "installer\GPC-DTwin.iss"
Write-Host "[GPC-DTwin] Compiling Windows64 installer..." -ForegroundColor Cyan
& $ISCC $IssFile
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed." }

$Version = (Get-Content (Join-Path $RepoRoot "VERSION") -Raw).Trim()
$Installer = Join-Path $ReleaseDir "GPC-DTwin-v$Version-Setup-Windows64.exe"
if (-not (Test-Path $Installer)) {
    throw "Installer was not created at expected path: $Installer"
}

$Hash = (Get-FileHash -Algorithm SHA256 $Installer).Hash.ToLowerInvariant()
$ChecksumFile = "$Installer.sha256.txt"
"$Hash  $(Split-Path -Leaf $Installer)" | Set-Content -Encoding ascii $ChecksumFile

Write-Host "[GPC-DTwin] Installer created successfully." -ForegroundColor Green
Write-Host "  $Installer"
Write-Host "  SHA-256: $Hash"
Write-Host "[GPC-DTwin] Intended targets: Windows 10 1809+ x64, Windows 11 x64, Windows 11 ARM64 via x64 emulation." -ForegroundColor Green
