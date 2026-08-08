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

function Write-LogLine {
    param([string]$LogPath, [string]$Message)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogPath -Value "==== $ts $Message ====" -Encoding UTF8
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
    # Must Out-Null: otherwise caller `$py = Ensure-Venv` captures pip/playwright stdout as Object[]
    & $venvPy -m pip install -q -r requirements.txt 2>&1 | Out-Null
    Write-Step "Installing Playwright Chromium (first run may take several minutes) ..."
    & $venvPy -m playwright install chromium 2>&1 | Out-Null
    Write-Step "Environment ready."
    # Explicit string return only (no pipeline pollution)
    return ,([string]$venvPy)
}

function Resolve-LrFilledXlsx {
    <#
    .SYNOPSIS
      Locate filled LR workbook for a date without hardcoding Chinese in PS1 (GBK mojibake).
      Uses lr/work/last_filled.json from Python, else newest *_{date}.xlsx in lr/work.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$TargetDate
    )
    $marker = Join-Path $Root "lr\work\last_filled.json"
    if (Test-Path -LiteralPath $marker) {
        try {
            $j = Get-Content -LiteralPath $marker -Encoding UTF8 -Raw | ConvertFrom-Json
            if ($j.target_date -eq $TargetDate -and $j.xlsx) {
                $p = [string]$j.xlsx
                if (Test-Path -LiteralPath $p) {
                    return (Resolve-Path -LiteralPath $p).Path
                }
            }
        } catch {}
    }
    $work = Join-Path $Root "lr\work"
    if (-not (Test-Path -LiteralPath $work)) { return $null }
    $hits = @(Get-ChildItem -LiteralPath $work -Filter "*_$TargetDate.xlsx" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending)
    if ($hits.Count -gt 0) { return $hits[0].FullName }
    return $null
}

function Invoke-PythonLogged {
    <#
    .SYNOPSIS
      Run python with args; append stdout/stderr to log via cmd.exe.
      Avoids PowerShell *>> / 2>&1 NativeCommandError + _readerthread crashes on GBK consoles.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$PythonExe,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$LogPath
    )

    $env:PYTHONIOENCODING = "utf-8"
    $env:PYTHONUTF8 = "1"
    $env:PYTHONUNBUFFERED = "1"

    $argLine = ($Arguments | ForEach-Object {
        $a = [string]$_
        if ($a -match '[\s"]') { '"' + ($a -replace '"', '\"') + '"' } else { $a }
    }) -join " "

    $logAbs = $LogPath
    if (-not [System.IO.Path]::IsPathRooted($logAbs)) {
        $logAbs = Join-Path (Get-Location) $LogPath
    }

    Write-LogLine $logAbs ("run: " + $PythonExe + " " + $argLine)
    # cmd redirection keeps binary pipes out of PowerShell's stream reader
    $cmdline = '"' + $PythonExe + '" ' + $argLine + ' >> "' + $logAbs + '" 2>&1'
    cmd.exe /c $cmdline | Out-Null
    $code = $LASTEXITCODE
    if ($null -eq $code) { $code = 0 }
    return [int]$code
}
