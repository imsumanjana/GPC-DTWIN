$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Virtual environment not found. Run setup first." }
Set-Location $RepoRoot

Write-Host "[GPC-DTwin] Running release checks..." -ForegroundColor Cyan
& $Python -m pytest -m "not gui"
if ($LASTEXITCODE -ne 0) { throw "Service checks failed." }
$env:QT_QPA_PLATFORM = "offscreen"
& $Python -m gpc_dtwin.ui_audit
if ($LASTEXITCODE -ne 0) { throw "Interface check failed." }

Write-Host "[GPC-DTwin] Creating Windows build..." -ForegroundColor Cyan
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
$env:QT_QPA_PLATFORM = "offscreen"
& $FrozenExe --self-check
if ($LASTEXITCODE -ne 0) { throw "Frozen application self-check failed." }
if (-not (Get-ChildItem -Path $Dist -Recurse -Filter "GPC_Reference_Dataset.csv" | Select-Object -First 1)) { throw "Bundled reference dataset is missing." }
if (-not (Get-ChildItem -Path $Dist -Recurse -Filter "GPC_Dataset_Template.csv" | Select-Object -First 1)) { throw "Bundled CSV template is missing." }
Copy-Item README.md, RELEASE_NOTES.md, COPYRIGHT.txt, LICENSE-NOTICE.txt -Destination $Dist -Force
Write-Host "Build created and validated in dist\GPC-DTwin" -ForegroundColor Green
