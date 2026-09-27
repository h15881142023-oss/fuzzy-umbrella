# Start Chrome with CDP 9222 for Power BI (Windows PowerShell 5.1).
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_chrome_powerbi_windows.ps1

$ErrorActionPreference = "Stop"
$DebugPort = 9222
$ReportUrl = "https://app.powerbi.com/reportEmbed?reportId=1a6f7a23-0fd5-44d8-a37f-8cef116b8ad9&autoAuth=true&ctid=7c792a97-2300-4444-aa97-172fed9b0501"
$UserDataDir = Join-Path $env:LOCALAPPDATA "Google\ChromeAutomationXinshang"

function Test-Cdp {
  try {
    Invoke-WebRequest ("http://127.0.0.1:" + $DebugPort + "/json/version") -UseBasicParsing -TimeoutSec 2 | Out-Null
    return $true
  } catch {
    return $false
  }
}

if (Test-Cdp) {
  Write-Host ("[OK] Chrome CDP already on port " + $DebugPort)
  exit 0
}

$chrome = @(
  (Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe"),
  (Join-Path ${env:ProgramFiles(x86)} "Google\Chrome\Application\chrome.exe"),
  (Join-Path $env:LOCALAPPDATA "Google\Chrome\Application\chrome.exe")
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if (-not $chrome) {
  Write-Host "[BAD] Chrome not found. Install Google Chrome first."
  exit 1
}

New-Item -ItemType Directory -Force -Path $UserDataDir | Out-Null
Write-Host ("==> start Chrome CDP " + $DebugPort)
Write-Host ("==> profile: " + $UserDataDir)
Write-Host "Login if asked: qiaoxh@ppu.powerbi.bi"
Start-Process -FilePath $chrome -ArgumentList @(
  ("--remote-debugging-port=" + $DebugPort),
  "--remote-allow-origins=*",
  ("--user-data-dir=" + $UserDataDir),
  "--no-first-run",
  "--no-default-browser-check",
  $ReportUrl
)

$i = 0
while ($i -lt 30) {
  if (Test-Cdp) {
    Write-Host "[OK] Chrome CDP ready"
    Write-Host "If the report needs login, sign in in that Chrome window, then rerun scrape."
    exit 0
  }
  Start-Sleep -Seconds 1
  $i = $i + 1
}

Write-Host "[BAD] Chrome started but CDP 9222 is not ready."
exit 1
