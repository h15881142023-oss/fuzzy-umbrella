# 新商评外发页 — 一次性安装计划任务（对齐代补看板 install_powerbi_daily_launchd.sh）
# 装好后：每天自动 Power BI 月在线商家数 + Metabase + 同分群，无需再手动操作。
#
# 以管理员身份 PowerShell：
#   cd "C:\Users\Administrator\Documents\fuzzy-umbrella"
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_xinshang_daily_windows.ps1
#
# 手动试跑：
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_xinshang_daily_windows.ps1 -Once
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

$TaskName = "ChuanzangXinshangDaily"
$RunScript = Join-Path $Root "scripts\run_xinshang_daily_windows.ps1"

function Download-IfMissing([string]$rel, [string]$ref) {
  $dest = Join-Path $Root ($rel -replace "/", "\")
  if (Test-Path $dest) { return }
  New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
  $stamp = Get-Date -Format "yyyyMMddHHmmss"
  $url = "https://fastly.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@" + $ref + "/" + $rel + "?t=" + $stamp
  Write-Host ("==> download " + $rel)
  Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing -TimeoutSec 120
}

$Ref = "60c2a53"
foreach ($f in @(
  "scripts/run_xinshang_daily_windows.ps1",
  "scripts/fetch_xinshang_tools_windows.ps1",
  "scripts/start_chrome_powerbi_windows.ps1",
  "scripts/sync_xinshang_from_chuxin.py",
  "scripts/sync_peer_compare_from_chuxin.py",
  "scrapers/scrape_powerbi_wind_online.py",
  "scrapers/cdp_client.py",
  "scrapers/powerbi_wind_js.py",
  "scrapers/__init__.py"
)) {
  Download-IfMissing $f $Ref
}

if (-not (Test-Path $RunScript)) {
  Write-Host "[BAD] 缺少 run_xinshang_daily_windows.ps1"
  exit 1
}

$psExe = (Get-Command powershell.exe).Source
$arg = "-NoProfile -ExecutionPolicy Bypass -File `"$RunScript`""

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute $psExe -Argument $arg -WorkingDirectory $Root
$triggerDaily = New-ScheduledTaskTrigger -Daily -At "08:30"
$settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -StartWhenAvailable -RestartCount 3 `
  -RestartInterval (New-TimeSpan -Minutes 5) `
  -ExecutionTimeLimit ([TimeSpan]::Zero)
$prin = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggerDaily -Settings $settings -Principal $prin -Force | Out-Null

Write-Host ""
Write-Host "[OK] 已安装计划任务: $TaskName"
Write-Host "     每天 08:30 自动：Power BI 月在线商家数 + 主看板 + 同分群 117 城"
Write-Host "     日志: $Root\logs\xinshang_daily_YYYYMMDD.log"
Write-Host ""
Write-Host "Power BI Chrome 独立 profile，首次若弹登录：qiaoxh@ppu.powerbi.bi"
Write-Host ""
Write-Host "立即试跑:"
Write-Host "  powershell -NoProfile -ExecutionPolicy Bypass -File `"$RunScript`" -Once"
Write-Host ""
Write-Host "外发页: https://1.chuanzangyiqu.top/evaluation/xinshang"
Write-Host "需 Web+隧道: install_background_windows.ps1（ChuanzangWeb5001 + ChuanzangTunnel）"
exit 0
