$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Virtual environment not found. Run setup first." }
Set-Location $RepoRoot
$env:QT_QPA_PLATFORM = "offscreen"
& $Python -m gpc_dtwin.ui_audit --screenshots
if ($LASTEXITCODE -ne 0) { throw "Interface check failed." }
Write-Host "Interface check completed. Results are in the writable ui-check folder." -ForegroundColor Green
