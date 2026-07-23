# Local store morning monitor (Windows)
$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_local_common.ps1"

$Root = Get-RepoRoot
Set-Location $Root
New-Item -ItemType Directory -Force -Path "logs" | Out-Null
$Log = "logs\store_morning_monitor_local.log"

Write-Step "Store morning start. Log: $Root\$Log"
Write-LogLine $Log "start"
try {
    $py = Ensure-Venv -Root $Root
} catch {
    Write-Step "venv fail: $_"
    Write-LogLine $Log "venv fail: $_"
    exit 1
}

# Ensure Chrome CDP 9222 is up (Power BI scrape needs it)
Write-Step "Ensuring Chrome CDP on 9222 ..."
$cdpOk = $false
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:9222/json/version" -TimeoutSec 2 -UseBasicParsing
    if ($resp.StatusCode -eq 200) { $cdpOk = $true }
} catch {}

if (-not $cdpOk) {
    Write-Step "Starting Chrome via scripts\start_chrome_powerbi.ps1 ..."
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\start_chrome_powerbi.ps1") *>> $Log
    Start-Sleep -Seconds 3
}

Write-Step "Running morning monitor (powerbi --once) ..."
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
    Write-Step "If first run: login Power BI in the ChromeAutomation window, then re-run this script."
}
exit $code
