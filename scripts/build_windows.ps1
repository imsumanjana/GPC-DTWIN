$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Virtual environment not found. Run setup first." }
Set-Location $RepoRoot
& $Python -m PyInstaller --noconfirm --clean --windowed --name "GPC-DTwin" `
    --add-data "data\reference;data\reference" `
    --add-data "data\templates;data\templates" `
    --collect-all matplotlib `
    src\gpc_dtwin\app.py
if ($LASTEXITCODE -ne 0) { throw "Windows build failed." }
New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot "dist\GPC-DTwin\models\trained") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot "dist\GPC-DTwin\models\twins") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot "dist\GPC-DTwin\models\ndt") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot "dist\GPC-DTwin\models\durability") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot "dist\GPC-DTwin\models\optimizations") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot "dist\GPC-DTwin\models\active_learning") | Out-Null
Write-Host "Build created in dist\GPC-DTwin" -ForegroundColor Green
