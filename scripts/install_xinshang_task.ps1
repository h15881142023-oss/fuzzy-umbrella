# 新商评 — 一次性安装计划任务（对齐经营宝 install_task.ps1）
# 装好后：每周二、周五 22:00 自动 Power BI 月在线商家数 + Metabase + 同分群，结果推同一企微。
#
# 以管理员身份 PowerShell，整段复制：
#   cd "C:\Users\Administrator\Documents\fuzzy-umbrella"
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_xinshang_task.ps1
#
# 手动试跑：
#   cd "C:\Users\Administrator\Documents\fuzzy-umbrella"
#   cmd /c call .\scripts\run_xinshang_daily_push.bat
#
# 卸载：
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\uninstall_xinshang_daily_windows.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  Write-Host "[MISS] 请右键「以管理员身份运行」PowerShell"
  exit 1
}

$TaskName = "CZ1_Xinshang_WeCom_TueFriPush"
$Bat = Join-Path $Root "scripts\run_xinshang_daily_push.bat"
$OldNames = @(
  "ChuanzangXinshangDaily",
  "ChuanzangXinshangSync",
  "ChuanzangXinshangSyncFri",
  "CZ1_Xinshang_WeCom_TueFriPush"
)

function Get-RemoteFile([string]$rel, [string]$ref) {
  $stamp = Get-Date -Format "yyyyMMddHHmmss"
  $urls = @(
    ("https://ghproxy.net/https://raw.githubusercontent.com/h15881142023-oss/fuzzy-umbrella/" + $ref + "/" + $rel + "?t=" + $stamp),
    ("https://raw.githubusercontent.com/h15881142023-oss/fuzzy-umbrella/" + $ref + "/" + $rel + "?t=" + $stamp)
  )
  if ($ref -notmatch "/") {
    $urls += @(
      ("https://fastly.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@" + $ref + "/" + $rel + "?t=" + $stamp),
      ("https://cdn.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@" + $ref + "/" + $rel + "?t=" + $stamp)
    )
  }
  $tmp = Join-Path $env:TEMP ("cz1-xsp-" + $stamp + "-" + ($rel -replace "[\\/]", "_"))
  foreach ($url in $urls) {
    Write-Host ("==> try: " + $url)
    try {
      Invoke-WebRequest -Uri $url -OutFile $tmp -UseBasicParsing -TimeoutSec 120
      $bytes = [System.IO.File]::ReadAllBytes($tmp)
      if ($bytes.Length -lt 40) { continue }
      return $tmp
    } catch {
      Write-Host ("[WARN] " + $_.Exception.Message)
    }
  }
  return $null
}

$Sha = "3059d02"
$Ref = "cursor/cz1-merchant-dashboard-74a9"
$need = @(
  "scripts/xinshang_daily_push.py",
  "scripts/xinshang_wecom.py",
  "scripts/xinshang_wecom_config.json",
  "scripts/xinshang_clock_windows.py",
  "scripts/xinshang_self_update.py",
  "scripts/run_xinshang_daily_push.bat",
  "scripts/start_chrome_powerbi_windows.ps1",
  "scripts/sync_xinshang_from_chuxin.py",
  "scripts/sync_peer_compare_from_chuxin.py",
  "scrapers/scrape_powerbi_wind_online.py",
  "scrapers/cdp_client.py",
  "scrapers/powerbi_wind_js.py",
  "scrapers/__init__.py"
)
foreach ($rel in $need) {
  $dest = Join-Path $Root ($rel -replace "/", "\")
  if (Test-Path $dest) { continue }
  New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
  $tmp = Get-RemoteFile $rel $Sha
  if (-not $tmp) { $tmp = Get-RemoteFile $rel $Ref }
  if (-not $tmp) {
    Write-Host ("[BAD] 缺少 " + $rel + " 且下载失败")
    exit 1
  }
  Copy-Item $tmp $dest -Force
  Remove-Item $tmp -Force -ErrorAction SilentlyContinue
  Write-Host ("[OK] downloaded " + $rel)
}

if (-not (Test-Path $Bat)) {
  Write-Host "[BAD] 缺少 run_xinshang_daily_push.bat"
  exit 1
}

$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd -and $cmd.Source -notmatch "WindowsApps\\python.exe$") { $py = $cmd.Source }
}
if ($py) {
  Write-Host ("python=" + $py)
}

foreach ($name in $OldNames) {
  Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
  schtasks /Delete /TN $name /F 2>$null | Out-Null
}

$cmdExe = Join-Path $env:SystemRoot "System32\cmd.exe"
$arg = "/c call `"$Bat`""
$action = New-ScheduledTaskAction -Execute $cmdExe -Argument $arg -WorkingDirectory $Root
$triggerTue = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Tuesday -At "22:00"
$triggerFri = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At "22:00"
$settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -StartWhenAvailable -RestartCount 3 `
  -RestartInterval (New-TimeSpan -Minutes 5) `
  -ExecutionTimeLimit ([TimeSpan]::Zero)
$prin = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $action `
  -Trigger @($triggerTue, $triggerFri) `
  -Settings $settings `
  -Principal $prin `
  -Force | Out-Null

Write-Host ""
Write-Host "[OK] 已安装计划任务: $TaskName"
Write-Host "     每周二、周五 22:00 自动：Power BI 月在线商家数 + 主看板 + 同分群"
Write-Host "     成功/失败推同一企微（优先读桌面 经营宝订单抓取\wecom_config.json）"
Write-Host "     日志: $Root\logs\xinshang_push_YYYYMMDD.log"
Write-Host ""
Write-Host "Power BI Chrome 独立 profile，首次若弹登录：qiaoxh@ppu.powerbi.bi"
Write-Host "需 Web+隧道: install_background_windows.ps1（ChuanzangWeb5001 + ChuanzangTunnel）"
Write-Host ""
Write-Host "立即试跑（整段复制）:"
Write-Host "  cd `"$Root`""
Write-Host "  cmd /c call .\scripts\run_xinshang_daily_push.bat"
Write-Host ""
Write-Host "外发页: https://1.chuanzangyiqu.top/evaluation/xinshang"
exit 0
