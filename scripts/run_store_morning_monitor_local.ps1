# Local store morning monitor (Windows)
$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_local_common.ps1"

$Root = Get-RepoRoot
Set-Location $Root
New-Item -ItemType Directory -Force -Path "logs" | Out-Null
$Log = "logs\store_morning_monitor_local.log"

function Test-Cdp {
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:9222/json/version" -TimeoutSec 2 -UseBasicParsing
    return ($r.StatusCode -eq 200)
  } catch {
    return $false
  }
}

Write-Step "Store morning start. Log: $Root\$Log"
Write-LogLine $Log "start"
try {
    $py = Ensure-Venv -Root $Root
} catch {
    Write-Step "venv fail: $_"
    Write-LogLine $Log "venv fail: $_"
    exit 1
}

Write-Step "Checking Chrome CDP 9222 ..."
if (-not (Test-Cdp)) {
    $starter = Join-Path $Root "scripts\start_chrome_powerbi.ps1"
    if (-not (Test-Path $starter)) {
        Write-Step "MISSING scripts\start_chrome_powerbi.ps1 - please update files first"
        Write-LogLine $Log "missing start_chrome_powerbi.ps1"
        exit 1
    }
    Write-Step "Starting ChromeAutomation for Power BI ..."
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $starter *>> $Log
    for ($i=1; $i -le 20; $i++) {
        if (Test-Cdp) { break }
        Start-Sleep -Seconds 1
    }
}

if (-not (Test-Cdp)) {
    Write-Step "FAILED: Chrome CDP 9222 not available."
    Write-Step "Install Google Chrome, then re-run. First time login Power BI in the opened window."
    Write-LogLine $Log "cdp-unavailable"
    exit 1
}

Write-Step "CDP OK. Running powerbi_subsidy_daily.py --once ..."
if ($env:CZ_STORE_MORNING_CMD) {
    cmd /c $env:CZ_STORE_MORNING_CMD *>> $Log
} else {
    & $py "scrapers\powerbi_subsidy_daily.py" --once *>> $Log
}
$code = $LASTEXITCODE
Write-LogLine $Log "exit=$code"
if ($code -eq 0) {
    Write-Step "SUCCESS. See $Log"
} else {
    Write-Step "FAILED exit=$code. See $Log"
    Write-Step "If Chrome opened: login Power BI there, keep window open, then re-run this script."
}
exit $code
