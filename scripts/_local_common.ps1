# Shared helpers for Windows local automations
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Write-Step {
    param([string]$Message)
    $ts = Get-Date -Format "HH:mm:ss"
    Write-Host "[$ts] $Message"
}

function Ensure-Venv {
    param([string]$Root)
    Set-Location $Root
    New-Item -ItemType Directory -Force -Path "logs" | Out-Null

    $python = $null
    foreach ($cand in @("python", "py")) {
        try {
            $ver = & $cand --version 2>&1
            if ($LASTEXITCODE -eq 0 -or $ver -match "Python") {
                $python = $cand
                break
            }
        } catch {}
    }
    if (-not $python) {
        throw "Python not found. Install Python 3 and check Add python.exe to PATH."
    }

    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        Write-Step "Creating .venv ..."
        if ($python -eq "py") {
            & py -3 -m venv .venv
        } else {
            & python -m venv .venv
        }
    }

    $venvPy = Join-Path $Root ".venv\Scripts\python.exe"
    Write-Step "Installing Python packages (first run may take several minutes) ..."
    & $venvPy -m pip install -q -r requirements.txt
    Write-Step "Installing Playwright Chromium (first run may take several minutes) ..."
    & $venvPy -m playwright install chromium
    Write-Step "Environment ready."
    return $venvPy
}

function Write-LogLine {
    param([string]$LogPath, [string]$Message)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogPath -Value "==== $ts $Message ====" -Encoding UTF8
}
