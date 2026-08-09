$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Virtual environment not found. Run setup first." }
Set-Location $RepoRoot
$env:QT_QPA_PLATFORM = "offscreen"
$env:PYTHONFAULTHANDLER = "1"
$env:QT_OPENGL = "software"
$env:QT_QUICK_BACKEND = "software"
$env:OMP_NUM_THREADS = "1"
$env:OPENBLAS_NUM_THREADS = "1"
$env:MKL_NUM_THREADS = "1"
$env:NUMEXPR_NUM_THREADS = "1"
& $Python -m pytest
if ($LASTEXITCODE -ne 0) { throw "Test suite failed." }
& $Python -m gpc_dtwin.ui_audit --screenshots
if ($LASTEXITCODE -ne 0) { throw "Interface check failed." }
& $Python -m gpc_dtwin.app --self-check
if ($LASTEXITCODE -ne 0) { throw "Application check failed." }
$Version = (Get-Content (Join-Path $RepoRoot "VERSION") -Raw).Trim()
Write-Host "GPC-DTwin v$Version release checks passed." -ForegroundColor Green
