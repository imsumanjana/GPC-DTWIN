$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Virtual environment not found. Run setup first." }
Set-Location $RepoRoot
$env:QT_QPA_PLATFORM = "offscreen"
& $Python -m pytest
if ($LASTEXITCODE -ne 0) { throw "Test suite failed." }
& $Python -m gpc_dtwin.ui_audit --screenshots
if ($LASTEXITCODE -ne 0) { throw "Interface check failed." }
& $Python -m gpc_dtwin.app --self-check
if ($LASTEXITCODE -ne 0) { throw "Application check failed." }
Write-Host "GPC-DTwin v1.0.1 release checks passed." -ForegroundColor Green
