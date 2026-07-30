$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$VenvPath = Join-Path $RepoRoot ".venv"
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
$RuntimeRoot = Join-Path $RepoRoot ".runtime"
$RuntimeTemp = Join-Path $RuntimeRoot "temp"
$PytestTemp = Join-Path $RuntimeRoot "pytest"

function Initialize-LocalRuntime {
    New-Item -ItemType Directory -Force -Path $RuntimeTemp | Out-Null
    if (Test-Path $PytestTemp) {
        try { Remove-Item -Recurse -Force $PytestTemp }
        catch { $script:PytestTemp = Join-Path $RuntimeRoot ("pytest-" + $PID) }
    }
    New-Item -ItemType Directory -Force -Path $PytestTemp | Out-Null
    $env:TEMP = $RuntimeTemp
    $env:TMP = $RuntimeTemp
    $env:TMPDIR = $RuntimeTemp
}

function Test-PythonCandidate {
    param([string]$Command, [string[]]$PrefixArgs)
    $old = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        $probe = "import sys; print('.'.join(map(str,sys.version_info[:3]))); raise SystemExit(0 if (3,11) <= sys.version_info[:2] < (3,14) else 2)"
        $args = @($PrefixArgs) + @("-c", $probe)
        $output = & $Command @args 2>$null
        $code = $LASTEXITCODE
    } catch { $output = $null; $code = 1 }
    finally { $ErrorActionPreference = $old }
    if ($code -eq 0) {
        return [PSCustomObject]@{ Command=$Command; PrefixArgs=@($PrefixArgs); Version=($output | Select-Object -Last 1) }
    }
    return $null
}

function Find-Python {
    $candidates = @()
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $candidates += [PSCustomObject]@{Command="py"; PrefixArgs=@("-3.12")}
        $candidates += [PSCustomObject]@{Command="py"; PrefixArgs=@("-3.13")}
        $candidates += [PSCustomObject]@{Command="py"; PrefixArgs=@("-3.11")}
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $candidates += [PSCustomObject]@{Command="python"; PrefixArgs=@()}
    }
    foreach ($candidate in $candidates) {
        $result = Test-PythonCandidate $candidate.Command $candidate.PrefixArgs
        if ($null -ne $result) { return $result }
    }
    return $null
}

Write-Host "[GPC-DTwin] Folder: $RepoRoot" -ForegroundColor Cyan
Initialize-LocalRuntime

if ((Test-Path $VenvPath) -and -not (Test-Path $VenvPython)) {
    Remove-Item -Recurse -Force $VenvPath
}

if (-not (Test-Path $VenvPython)) {
    $selected = Find-Python
    if ($null -eq $selected) {
        Write-Host "No supported Python runtime was found." -ForegroundColor Red
        Write-Host "Install Python 3.12 and run setup again:" -ForegroundColor Yellow
        Write-Host "    py install 3.12"
        exit 1
    }
    Write-Host "[GPC-DTwin] Using Python $($selected.Version)" -ForegroundColor Green
    $args = @($selected.PrefixArgs) + @("-m", "venv", $VenvPath)
    & $selected.Command @args
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VenvPython)) {
        throw "Virtual-environment creation failed."
    }
}

Write-Host "[GPC-DTwin] Updating packaging tools..." -ForegroundColor Cyan
& $VenvPython -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) { throw "Packaging-tool update failed." }

Write-Host "[GPC-DTwin] Installing application dependencies..." -ForegroundColor Cyan
& $VenvPython -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }

Write-Host "[GPC-DTwin] Running service tests..." -ForegroundColor Cyan
& $VenvPython -m pytest -m "not gui" --basetemp="$PytestTemp"
if ($LASTEXITCODE -ne 0) { throw "Service tests failed." }

Write-Host "[GPC-DTwin] Setup completed successfully." -ForegroundColor Green
Write-Host "Run: powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1"
