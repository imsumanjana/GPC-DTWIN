$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$RuntimeRoot = Join-Path $RepoRoot ".runtime"
$RuntimeTemp = Join-Path $RuntimeRoot "temp"
$CrashLog = Join-Path $RuntimeRoot "native-crash.log"

if (-not (Test-Path $Python)) {
    throw "Virtual environment not found. Run .\scripts\setup.ps1 first."
}

New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
New-Item -ItemType Directory -Force -Path $RuntimeTemp | Out-Null

$env:TEMP = $RuntimeTemp
$env:TMP = $RuntimeTemp
$env:TMPDIR = $RuntimeTemp
$env:PYTHONFAULTHANDLER = "1"
$env:QT_OPENGL = "software"
$env:QT_QUICK_BACKEND = "software"
$env:QTWEBENGINE_CHROMIUM_FLAGS = "--disable-gpu"
$env:OMP_NUM_THREADS = "1"
$env:OPENBLAS_NUM_THREADS = "1"
$env:MKL_NUM_THREADS = "1"
$env:NUMEXPR_NUM_THREADS = "1"

Set-Location $RepoRoot

"[$(Get-Date -Format o)] Starting GPC-DTwin" | Out-File -FilePath $CrashLog -Append -Encoding utf8
& $Python -X faulthandler -m gpc_dtwin 2>> $CrashLog
$ExitCode = $LASTEXITCODE

if ($ExitCode -eq -1073741819 -or $ExitCode -eq 3221225477) {
    throw "GPC-DTwin encountered a native Windows access violation. Software rendering and native diagnostics were enabled. Review $CrashLog and run .\scripts\release_check.ps1."
}
if ($ExitCode -ne 0) {
    throw "GPC-DTwin exited with code $ExitCode. Diagnostic log: $CrashLog"
}
