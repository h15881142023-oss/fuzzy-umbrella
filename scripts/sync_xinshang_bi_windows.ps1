# Fetch Power BI 在线商家数 + sync 初心模块数据, then rewrite local dashboard HTML.
# Windows PowerShell 5.1 compatible.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\sync_xinshang_bi_windows.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Get-Python {
  $venv = Join-Path $Root ".venv\Scripts\python.exe"
  if (Test-Path $venv) { return $venv }
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd -and $cmd.Source -notmatch "WindowsApps\\python.exe$") { return $cmd.Source }
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) { return $py.Source }
  return $null
}

$need = @(
  "scripts\sync_xinshang_from_chuxin.py",
  "scrapers\cdp_client.py",
  "scrapers\powerbi_wind_js.py",
  "scrapers\scrape_powerbi_wind_online.py"
)
$missing = @()
foreach ($p in $need) {
  if (-not (Test-Path (Join-Path $Root $p))) { $missing += $p }
}
if ($missing.Count -gt 0) {
  Write-Host "[MISS] local tools not found. Downloading..."
  $fetch = Join-Path $Root "scripts\fetch_xinshang_tools_windows.ps1"
  if (-not (Test-Path $fetch)) {
    Write-Host "Paste the download command from the agent first (本机还没有 fetch 脚本)."
    Write-Host ("missing: " + ($missing -join ", "))
    exit 1
  }
  & powershell -NoProfile -ExecutionPolicy Bypass -File $fetch
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$python = Get-Python
if (-not $python) {
  Write-Host "[BAD] Python not found."
  exit 1
}
Write-Host ("==> python: " + $python)

Write-Host "==> pip install websocket-client"
& $python -m pip install -q websocket-client
if ($LASTEXITCODE -ne 0) {
  Write-Host "[WARN] pip install websocket-client failed; scrape may fail"
}

$startChrome = Join-Path $Root "scripts\start_chrome_powerbi_windows.ps1"
if (Test-Path $startChrome) {
  Write-Host "==> ensure Chrome CDP 9222"
  & powershell -NoProfile -ExecutionPolicy Bypass -File $startChrome
}

Write-Host "==> scrape Power BI 在线商家数"
& $python "scrapers\scrape_powerbi_wind_online.py"
$scrapeOk = ($LASTEXITCODE -eq 0)
if (-not $scrapeOk) {
  Write-Host "[WARN] Power BI scrape failed. Will still sync 初心; 在线商家数 fallback to last known / default."
  Write-Host "If Chrome asked for login, sign in as qiaoxh@ppu.powerbi.bi then rerun this script."
}

Write-Host "==> sync 初心模块数据汇总表 -> HTML"
& $python "scripts\sync_xinshang_from_chuxin.py"
if ($LASTEXITCODE -ne 0) {
  Write-Host "[BAD] sync failed"
  exit 1
}

Write-Host ""
Write-Host "[OK] HTML updated."
Write-Host "Open https://1.chuanzangyiqu.top/evaluation/xinshang and Ctrl+F5"
Write-Host "If 502: powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_domain_windows.ps1"
exit 0
