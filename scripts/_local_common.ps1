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

function Get-PeBits {
    param([string]$ExePath)
    try {
        $fs = [IO.File]::OpenRead($ExePath)
        try {
            $br = New-Object IO.BinaryReader $fs
            if ($br.ReadUInt16() -ne 0x5A4D) { return $null }
            $fs.Seek(0x3C, [IO.SeekOrigin]::Begin) | Out-Null
            $pe = $br.ReadUInt32()
            $fs.Seek($pe, [IO.SeekOrigin]::Begin) | Out-Null
            if ($br.ReadUInt32() -ne 0x4550) { return $null }
            $machine = $br.ReadUInt16()
            if ($machine -eq 0x14C) { return 32 }
            if ($machine -eq 0x8664) { return 64 }
            return $null
        } finally { $fs.Close() }
    } catch { return $null }
}

function Find-WpsEtExe {
    $patterns = @(
        "$env:LOCALAPPDATA\Kingsoft\WPS Office\*\office6\et.exe",
        "$env:ProgramFiles\Kingsoft\WPS Office\*\office6\et.exe",
        "${env:ProgramFiles(x86)}\Kingsoft\WPS Office\*\office6\et.exe"
    )
    foreach ($p in $patterns) {
        $hit = Get-Item $p -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
        if ($hit) { return $hit.FullName }
    }
    return $null
}

function Get-WpsMatchedPowerShell {
    <#
    .SYNOPSIS
      WPS et.exe is usually 32-bit. 64-bit powershell.exe cannot create its COM class (CLASSNOTREG).
    #>
    $sys32 = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    $wow64 = Join-Path $env:SystemRoot "SysWOW64\WindowsPowerShell\v1.0\powershell.exe"
    $et = Find-WpsEtExe
    if ($et) {
        $bits = Get-PeBits -ExePath $et
        if ($bits -eq 32 -and (Test-Path -LiteralPath $wow64)) {
            return $wow64
        }
    }
    return $sys32
}

function Notify-LrWecomText {
    param([string]$Root, [string]$Message)
    $py = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $py)) { return }
    $env:PYTHONIOENCODING = "utf-8"
    $env:PYTHONUTF8 = "1"
    & $py "lr\wecom_push.py" "--text" $Message | Out-Null
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
