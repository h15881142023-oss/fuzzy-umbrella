# 新商评外发页 — 本机无人值守日更（Power BI 月在线商家数 + Metabase + 同分群）
# 由计划任务调用，用户无需手动操作。
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\xinshang_daily_windows.ps1

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

$LogDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir ("xinshang_daily_" + (Get-Date -Format "yyyyMMdd") + ".log")

function Log([string]$msg) {
  $line = ("[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "] " + $msg)
  Add-Content -Path $LogFile -Value $line -Encoding UTF8
  Write-Host $line
}

Log "==> xinshang daily start root=$Root"

# 缺脚本时从 GitHub CDN 拉取（不依赖 git）
$need = @(
  "scripts\fetch_xinshang_tools_windows.ps1",
  "scripts\sync_xinshang_from_chuxin.py",
  "scripts\sync_peer_compare_from_chuxin.py"
)
$missing = @()
foreach ($p in $need) {
  if (-not (Test-Path (Join-Path $Root $p))) { $missing += $p }
}
if ($missing.Count -gt 0) {
  Log "==> missing tools, bootstrap from CDN Ref=main"
  $stamp = Get-Date -Format "yyyyMMddHHmmss"
  $fetchUrl = "https://fastly.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@main/scripts/fetch_xinshang_tools_windows.ps1?t=" + $stamp
  $fetchOut = Join-Path $Root "scripts\fetch_xinshang_tools_windows.ps1"
  New-Item -ItemType Directory -Force -Path (Join-Path $Root "scripts") | Out-Null
  Invoke-WebRequest -Uri $fetchUrl -OutFile $fetchOut -UseBasicParsing -TimeoutSec 120
  & powershell -NoProfile -ExecutionPolicy Bypass -File $fetchOut -Ref main
  if ($LASTEXITCODE -ne 0) {
    Log "[BAD] fetch tools failed"
    exit 1
  }
}

$python = Get-Python
if (-not $python) {
  Log "[BAD] Python not found"
  exit 1
}
Log ("python: " + $python)

& $python -m pip install -q websocket-client 2>$null

$startChrome = Join-Path $Root "scripts\start_chrome_powerbi_windows.ps1"
if (Test-Path $startChrome) {
  Log "==> ensure Chrome CDP 9222"
  & powershell -NoProfile -ExecutionPolicy Bypass -File $startChrome
}

Log "==> Power BI 月在线商家数"
& $python "scrapers\scrape_powerbi_wind_online.py"
if ($LASTEXITCODE -ne 0) {
  Log "[WARN] Power BI scrape failed; sync will use last JSON or defaults"
}

Log "==> Metabase 主看板"
& $python "scripts\sync_xinshang_from_chuxin.py"
if ($LASTEXITCODE -ne 0) {
  Log "[BAD] sync_xinshang failed"
  exit 1
}

Log "==> 同分群对比"
& $python "scripts\sync_peer_compare_from_chuxin.py"
if ($LASTEXITCODE -ne 0) {
  Log "[BAD] sync_peer_compare failed"
  exit 1
}

Log "[OK] xinshang daily done"
Log "https://1.chuanzangyiqu.top/evaluation/xinshang"
exit 0
