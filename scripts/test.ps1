$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$RuntimeRoot = Join-Path $RepoRoot ".runtime"
$RuntimeTemp = Join-Path $RuntimeRoot "temp"
$PytestTemp = Join-Path $RuntimeRoot "pytest"
if (-not (Test-Path $Python)) { throw "Virtual environment not found. Run .\scripts\setup.ps1 first." }
Set-Location $RepoRoot
New-Item -ItemType Directory -Force -Path $RuntimeTemp | Out-Null
if (Test-Path $PytestTemp) {
    try { Remove-Item -Recurse -Force $PytestTemp }
    catch { $PytestTemp = Join-Path $RuntimeRoot ("pytest-" + $PID) }
}
New-Item -ItemType Directory -Force -Path $PytestTemp | Out-Null
$env:TEMP = $RuntimeTemp
$env:TMP = $RuntimeTemp
$env:TMPDIR = $RuntimeTemp
$env:QT_QPA_PLATFORM = "offscreen"
& $Python -m pytest --basetemp="$PytestTemp"
if ($LASTEXITCODE -ne 0) { throw "Test suite failed." }
& $Python -m gpc_dtwin.ui_audit
if ($LASTEXITCODE -ne 0) { throw "Interface check failed." }
Write-Host "[GPC-DTwin] All tests and interface checks passed." -ForegroundColor Green
