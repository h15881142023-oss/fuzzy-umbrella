# 一次性：把本机 Web 换成带新商评时钟的代码，并重启 ChuanzangWeb5001。
# 页面保持外发；重启后周二/周五 22:00 会自动跑。
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\refresh_web_clock_windows.ps1

param(
  [string]$Ref = "83be1d1"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$files = @(
  "app.py",
  "scripts/run_web_windows.py",
  "scripts/xinshang_clock_windows.py",
  "scripts/xinshang_self_update.py",
  "scripts/xinshang_daily_push.py",
  "scripts/xinshang_wecom.py",
  "scripts/xinshang_wecom_config.json",
  "scripts/sync_xinshang_from_chuxin.py",
  "scripts/sync_peer_compare_from_chuxin.py",
  "scripts/start_chrome_powerbi_windows.ps1",
  "scrapers/__init__.py",
  "scrapers/cdp_client.py",
  "scrapers/powerbi_wind_js.py",
  "scrapers/scrape_powerbi_wind_online.py"
)

function Get-RemoteFile([string]$rel) {
  $stamp = Get-Date -Format "yyyyMMddHHmmss"
  $urls = @(
    ("https://fastly.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@" + $Ref + "/" + $rel + "?t=" + $stamp),
    ("https://cdn.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@" + $Ref + "/" + $rel + "?t=" + $stamp),
    ("https://ghproxy.net/https://raw.githubusercontent.com/h15881142023-oss/fuzzy-umbrella/" + $Ref + "/" + $rel + "?t=" + $stamp),
    ("https://raw.githubusercontent.com/h15881142023-oss/fuzzy-umbrella/" + $Ref + "/" + $rel + "?t=" + $stamp)
  )
  $tmp = Join-Path $env:TEMP ("cz1-web-" + $stamp + "-" + ($rel -replace "[\\/]", "_"))
  foreach ($url in $urls) {
    Write-Host ("==> " + $rel)
    try {
      Invoke-WebRequest -Uri $url -OutFile $tmp -UseBasicParsing -TimeoutSec 120
      if ((Get-Item $tmp).Length -gt 40) { return $tmp }
    } catch {
      Write-Host ("[WARN] " + $_.Exception.Message)
    }
  }
  return $null
}

$bad = @()
foreach ($rel in $files) {
  $dest = Join-Path $Root ($rel -replace "/", "\")
  New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
  $tmp = Get-RemoteFile $rel
  if (-not $tmp) {
    $bad += $rel
    continue
  }
  Copy-Item $tmp $dest -Force
  Remove-Item $tmp -Force -ErrorAction SilentlyContinue
  Write-Host ("[OK] " + $rel)
}

if ($bad.Count -gt 0) {
  Write-Host ("[BAD] download failed: " + ($bad -join ", "))
  exit 1
}

function Stop-Port5001 {
  $conns = Get-NetTCPConnection -LocalPort 5001 -State Listen -ErrorAction SilentlyContinue
  foreach ($c in $conns) {
    if ($c.OwningProcess -and $c.OwningProcess -gt 0) {
      Write-Host ("==> stop pid " + $c.OwningProcess + " on :5001")
      Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
    }
  }
}

Write-Host "==> restart web"
try { Stop-ScheduledTask -TaskName "ChuanzangWeb5001" -ErrorAction SilentlyContinue } catch {}
Stop-Port5001
Start-Sleep -Seconds 2

$started = $false
try {
  Start-ScheduledTask -TaskName "ChuanzangWeb5001" -ErrorAction Stop
  $started = $true
  Write-Host "[OK] started ChuanzangWeb5001"
} catch {
  Write-Host ("[WARN] scheduled task: " + $_.Exception.Message)
}

if (-not $started) {
  $py = Join-Path $Root ".venv\Scripts\python.exe"
  $runWeb = Join-Path $Root "scripts\run_web_windows.py"
  if (-not (Test-Path $py)) {
    Write-Host "[BAD] missing .venv\Scripts\python.exe"
    exit 1
  }
  Start-Process -FilePath $py -ArgumentList "`"$runWeb`"" -WorkingDirectory $Root -WindowStyle Minimized
  Write-Host "[OK] started run_web_windows.py"
}

try { Start-ScheduledTask -TaskName "ChuanzangTunnel" -ErrorAction SilentlyContinue } catch {}

$ok = $false
for ($i = 0; $i -lt 20; $i++) {
  Start-Sleep -Seconds 1
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:5001/evaluation/xinshang" -UseBasicParsing -TimeoutSec 5
    if ($r.StatusCode -eq 200) { $ok = $true; break }
  } catch {}
}

if ($ok) {
  Write-Host "[OK] local dashboard 200"
} else {
  Write-Host "[BAD] local dashboard not ready"
}

try {
  $h = Invoke-WebRequest -Uri "http://127.0.0.1:5001/api/xinshang/health" -UseBasicParsing -TimeoutSec 5
  Write-Host ("[OK] clock health: " + $h.Content)
} catch {
  Write-Host "[MISS] /api/xinshang/health not ready (old process still up?)"
}

Write-Host "page: https://1.chuanzangyiqu.top/evaluation/xinshang"
exit 0
