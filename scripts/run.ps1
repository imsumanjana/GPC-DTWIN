$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$RuntimeTemp = Join-Path $RepoRoot ".runtime\temp"
if (-not (Test-Path $Python)) { throw "Virtual environment not found. Run .\scripts\setup.ps1 first." }
New-Item -ItemType Directory -Force -Path $RuntimeTemp | Out-Null
$env:TEMP = $RuntimeTemp
$env:TMP = $RuntimeTemp
$env:TMPDIR = $RuntimeTemp
Set-Location $RepoRoot
& $Python -m gpc_dtwin
if ($LASTEXITCODE -ne 0) { throw "GPC-DTwin exited with code $LASTEXITCODE." }
