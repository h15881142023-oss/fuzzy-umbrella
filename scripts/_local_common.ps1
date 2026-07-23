# 本机自动化公共函数（Windows PowerShell）
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
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
        throw "未找到 Python。请先安装 Python 3，并勾选 Add python.exe to PATH。"
    }

    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        if ($python -eq "py") {
            & py -3 -m venv .venv
        } else {
            & python -m venv .venv
        }
    }

    $venvPy = Join-Path $Root ".venv\Scripts\python.exe"
    & $venvPy -m pip install -q -r requirements.txt
    & $venvPy -m playwright install chromium 2>$null | Out-Null
    return $venvPy
}

function Write-LogLine {
    param([string]$LogPath, [string]$Message)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogPath -Value "==== $ts $Message ====" -Encoding UTF8
}
