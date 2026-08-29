# 新商评日更入口（对齐代补看板 run_powerbi_subsidy_daily.sh）
# - 自动确保 Power BI Chrome CDP 9222
# - Power BI 月在线商家数 + Metabase 主看板 + 同分群 117 城
# - 写日志，失败不中断隧道/Web
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_xinshang_daily_windows.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_xinshang_daily_windows.ps1 -Once

param(
  [switch]$Once
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$LogDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir ("xinshang_daily_" + (Get-Date -Format "yyyyMMdd") + ".log")

function Log([string]$msg) {
  $line = ("[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "] " + $msg)
  Add-Content -Path $LogFile -Value $line -Encoding UTF8
  Write-Host $line
}

function Get-Python {
  $venv = Join-Path $Root ".venv\Scripts\python.exe"
  if (Test-Path $venv) { return $venv }
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd -and $cmd.Source -notmatch "WindowsApps\\python.exe$") { return $cmd.Source }
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) { return $py.Source }
  return $null
}

function Test-Cdp9222 {
  try {
    Invoke-WebRequest -Uri "http://127.0.0.1:9222/json/version" -UseBasicParsing -TimeoutSec 2 | Out-Null
    return $true
  } catch {
    return $false
  }
}

function Ensure-ChromePowerBi {
  if (Test-Cdp9222) {
    Log "CDP 9222 已就绪"
    return $true
  }
  $startChrome = Join-Path $Root "scripts\start_chrome_powerbi_windows.ps1"
  if (-not (Test-Path $startChrome)) {
    Log "[WARN] 缺少 start_chrome_powerbi_windows.ps1"
    return $false
  }
  Log "启动 Power BI Chrome（独立 profile，一般只需登录一次）"
  & powershell -NoProfile -ExecutionPolicy Bypass -File $startChrome
  if (Test-Cdp9222) { return $true }
  Log "[WARN] Chrome 已开但 CDP 未就绪；若弹出登录请用 qiaoxh@ppu.powerbi.bi 登录后等下次计划任务"
  return $false
}

function Ensure-Tools {
  $need = @(
    "scripts\sync_xinshang_from_chuxin.py",
    "scripts\sync_peer_compare_from_chuxin.py",
    "scrapers\scrape_powerbi_wind_online.py"
  )
  $missing = @()
  foreach ($p in $need) {
    if (-not (Test-Path (Join-Path $Root $p))) { $missing += $p }
  }
  if ($missing.Count -eq 0) { return $true }

  Log "缺少脚本，从 CDN 拉取（无需 git）"
  $fetch = Join-Path $Root "scripts\fetch_xinshang_tools_windows.ps1"
  if (-not (Test-Path $fetch)) {
    $stamp = Get-Date -Format "yyyyMMddHHmmss"
    $url = "https://fastly.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@60c2a53/scripts/fetch_xinshang_tools_windows.ps1?t=" + $stamp
    New-Item -ItemType Directory -Force -Path (Join-Path $Root "scripts") | Out-Null
    Invoke-WebRequest -Uri $url -OutFile $fetch -UseBasicParsing -TimeoutSec 120
  }
  & powershell -NoProfile -ExecutionPolicy Bypass -File $fetch -Ref 60c2a53
  return ($LASTEXITCODE -eq 0)
}

Log "==== start ===="
Log ("root=" + $Root)

if (-not (Ensure-Tools)) {
  Log "[BAD] 工具下载失败"
  exit 1
}

$python = Get-Python
if (-not $python) {
  Log "[BAD] 未找到 Python"
  exit 1
}
Log ("python=" + $python)
& $python -m pip install -q websocket-client 2>$null

# 确保 Chrome（与代补看板一样：CDP 起不来就等 10 分钟重试，除非 -Once）
while ($true) {
  if (Ensure-ChromePowerBi) { break }
  if ($Once) { break }
  Log "10 分钟后重试启动 Chrome…"
  Start-Sleep -Seconds 600
}

Log "==> Power BI 月在线商家数"
& $python "scrapers\scrape_powerbi_wind_online.py"
if ($LASTEXITCODE -ne 0) {
  Log "[WARN] Power BI 抓取失败，主看板将沿用上次 JSON/默认值"
}

Log "==> Metabase 主看板"
& $python "scripts\sync_xinshang_from_chuxin.py"
if ($LASTEXITCODE -ne 0) {
  Log "[BAD] sync_xinshang 失败"
  exit 1
}

Log "==> 同分群对比"
& $python "scripts\sync_peer_compare_from_chuxin.py"
if ($LASTEXITCODE -ne 0) {
  Log "[BAD] sync_peer_compare 失败"
  exit 1
}

Log "[OK] 新商评日更完成"
Log "https://1.chuanzangyiqu.top/evaluation/xinshang"
Log "==== end ===="
exit 0
