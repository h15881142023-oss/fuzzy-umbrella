# Local store morning monitor (Windows) — 自配门店早间监控
# Schedule: daily 08:30 (ChuanzangStoreMorningLocal)
# Needs: Google Chrome + ChromeAutomation profile logged into Power BI (CDP 9222)
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
    $starterLog = Join-Path $Root "logs\chrome_powerbi_start.log"
    cmd.exe /c ("powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"" + $starter + "`" >> `"" + $starterLog + "`" 2>&1") | Out-Null
    # 冷启动 + 登录态恢复可能较慢
    for ($i=1; $i -le 60; $i++) {
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
    cmd.exe /c ($env:CZ_STORE_MORNING_CMD + " >> `"" + (Join-Path $Root $Log) + "`" 2>&1") | Out-Null
    $code = $LASTEXITCODE
} else {
    $code = Invoke-PythonLogged -PythonExe $py -Arguments @("scrapers\powerbi_subsidy_daily.py", "--once") -LogPath $Log
}
Write-LogLine $Log "exit=$code"
if ($code -eq 0) {
    Write-Step "SUCCESS. See $Log"
} else {
    Write-Step "FAILED exit=$code. See $Log"
    Write-Step "If Chrome opened: login Power BI there, keep the ChromeAutomation window, then re-run."
    if (Test-Path $Log) { Get-Content -Path $Log -Tail 40 -Encoding UTF8 | ForEach-Object { Write-Host $_ } }
}
exit $code
