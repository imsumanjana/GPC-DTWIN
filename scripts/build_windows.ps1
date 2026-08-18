$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Virtual environment not found. Run setup first." }
Set-Location $RepoRoot

Write-Host "[GPC-DTwin] Checking release Python architecture..." -ForegroundColor Cyan
$PythonPlatform = (& $Python -c "import sysconfig; print(sysconfig.get_platform())").Trim().ToLowerInvariant()
$PythonBits = (& $Python -c "import struct; print(struct.calcsize('P') * 8)").Trim()
$PythonVersion = (& $Python -c "import platform; print(platform.python_version())").Trim()
Write-Host "  Python:       $PythonVersion"
Write-Host "  Platform tag: $PythonPlatform"
Write-Host "  Bitness:      $PythonBits-bit"

# The distributable Windows package is intentionally AMD64/x64. Windows 11
# on ARM64 can run this user-mode x64 application through Windows emulation.
# Building with ARM64 or 32-bit Python would produce a different binary and
# therefore must not be allowed accidentally.
if ($PythonBits -ne "64") {
    throw "Windows release build requires a 64-bit Python interpreter."
}
if ($PythonPlatform -ne "win-amd64") {
    throw "Windows release build requires x64/AMD64 Python (expected win-amd64, found '$PythonPlatform'). Install Python 3.12 x64 and recreate .venv."
}

Write-Host "[GPC-DTwin] Verifying installed dependencies..." -ForegroundColor Cyan
& $Python -m pip check
if ($LASTEXITCODE -ne 0) { throw "Dependency verification failed." }

Write-Host "[GPC-DTwin] Running release checks..." -ForegroundColor Cyan
& $Python -m pytest -m "not gui"
if ($LASTEXITCODE -ne 0) { throw "Service checks failed." }

$env:QT_QPA_PLATFORM = "offscreen"
$env:QT_OPENGL = "software"
$env:QT_QUICK_BACKEND = "software"
& $Python -m gpc_dtwin.ui_audit
if ($LASTEXITCODE -ne 0) { throw "Interface check failed." }
Remove-Item Env:\QT_QPA_PLATFORM -ErrorAction SilentlyContinue

Write-Host "[GPC-DTwin] Removing previous PyInstaller output..." -ForegroundColor Cyan
Remove-Item -Recurse -Force (Join-Path $RepoRoot "build") -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force (Join-Path $RepoRoot "dist") -ErrorAction SilentlyContinue
Remove-Item -Force (Join-Path $RepoRoot "GPC-DTwin.spec") -ErrorAction SilentlyContinue

Write-Host "[GPC-DTwin] Creating Windows x64 build..." -ForegroundColor Cyan
& $Python -m PyInstaller --noconfirm --clean --windowed --name "GPC-DTwin" `
    --icon "resources\GPC-DTwin.ico" `
    --version-file "resources\version_info.txt" `
    --paths "src" `
    --add-data "data\reference;data\reference" `
    --add-data "data\templates;data\templates" `
    --add-data "resources;resources" `
    --add-data "docs;docs" `
    --add-data "COPYRIGHT.txt;." `
    --add-data "LICENSE-NOTICE.txt;." `
    --collect-all matplotlib `
    --collect-all sklearn `
    --collect-submodules scipy `
    src\gpc_dtwin\app.py
if ($LASTEXITCODE -ne 0) { throw "Windows build failed." }

$Dist = Join-Path $RepoRoot "dist\GPC-DTwin"
$FrozenExe = Join-Path $Dist "GPC-DTwin.exe"
if (-not (Test-Path $FrozenExe)) { throw "Frozen executable was not created." }

Write-Host "[GPC-DTwin] Verifying PE machine type..." -ForegroundColor Cyan
$PeProbe = @'
import pathlib, struct, sys
path = pathlib.Path(sys.argv[1])
with path.open('rb') as fh:
    if fh.read(2) != b'MZ':
        raise SystemExit('Not a Windows PE executable')
    fh.seek(0x3C)
    pe_offset = struct.unpack('<I', fh.read(4))[0]
    fh.seek(pe_offset)
    if fh.read(4) != b'PE\0\0':
        raise SystemExit('Invalid PE signature')
    machine = struct.unpack('<H', fh.read(2))[0]
names = {0x014C: 'x86', 0x8664: 'AMD64/x64', 0xAA64: 'ARM64'}
print(f'PE machine: {names.get(machine, hex(machine))}')
raise SystemExit(0 if machine == 0x8664 else 3)
'@
& $Python -c $PeProbe $FrozenExe
if ($LASTEXITCODE -ne 0) { throw "Frozen executable is not AMD64/x64." }

Write-Host "[GPC-DTwin] Checking bundled resources and Qt runtime..." -ForegroundColor Cyan
if (-not (Get-ChildItem -Path $Dist -Recurse -Filter "GPC_Reference_Dataset.csv" | Select-Object -First 1)) { throw "Bundled reference dataset is missing." }
if (-not (Get-ChildItem -Path $Dist -Recurse -Filter "GPC_Dataset_Template.csv" | Select-Object -First 1)) { throw "Bundled CSV template is missing." }
if (-not (Get-ChildItem -Path $Dist -Recurse -Filter "qwindows.dll" | Select-Object -First 1)) { throw "Qt Windows platform plugin qwindows.dll is missing." }

Write-Host "[GPC-DTwin] Running frozen application self-check..." -ForegroundColor Cyan
$env:QT_QPA_PLATFORM = "offscreen"
$env:QT_OPENGL = "software"
$env:QT_QUICK_BACKEND = "software"
& $FrozenExe --self-check
if ($LASTEXITCODE -ne 0) { throw "Frozen application self-check failed." }
Remove-Item Env:\QT_QPA_PLATFORM -ErrorAction SilentlyContinue

Copy-Item README.md, RELEASE_NOTES.md, COPYRIGHT.txt, LICENSE-NOTICE.txt -Destination $Dist -Force

$ExeHash = (Get-FileHash -Algorithm SHA256 $FrozenExe).Hash
Write-Host "[GPC-DTwin] Build created and validated in dist\GPC-DTwin" -ForegroundColor Green
Write-Host "[GPC-DTwin] Executable SHA-256: $ExeHash" -ForegroundColor Green
Write-Host "[GPC-DTwin] Target compatibility: Windows 10 1809+ x64; Windows 11 x64; Windows 11 ARM64 via x64 emulation." -ForegroundColor Green
