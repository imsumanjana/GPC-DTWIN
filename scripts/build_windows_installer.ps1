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

$ProductVersion = (Get-Item $ISCC).VersionInfo.ProductVersion
$VersionMatch = [regex]::Match($ProductVersion, '\d+\.\d+(?:\.\d+)?')
if (-not $VersionMatch.Success) {
    throw "Could not determine Inno Setup version from $ISCC (reported '$ProductVersion')."
}
$InnoVersion = [version]$VersionMatch.Value
Write-Host "[GPC-DTwin] Inno Setup: $InnoVersion" -ForegroundColor Cyan
Write-Host "[GPC-DTwin] Compiler:   $ISCC"

if ($InnoVersion -lt [version]"6.3.0") {
    throw "Inno Setup $InnoVersion is too old for x64compatible installers. Upgrade to Inno Setup 6.3 or newer. Older compilers restrict the installer to native x64 Windows and can reject Windows 11 ARM64."
}

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
