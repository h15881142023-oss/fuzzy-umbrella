# 一次性安装：新商评外发页每日自动同步（Power BI + Metabase + 同分群）
# 装好后无需再手动跑命令，与 LR 日报 / 拜访检核一样无人值守。
#
# 以管理员身份打开 PowerShell，执行：
#   cd "C:\Users\Administrator\Documents\fuzzy-umbrella"
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_xinshang_daily_windows.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  Write-Host "[MISS] 请右键「以管理员身份运行」PowerShell"
  exit 1
}

$TaskName = "ChuanzangXinshangDaily"
$Script = Join-Path $Root "scripts\xinshang_daily_windows.ps1"

if (-not (Test-Path $Script)) {
  Write-Host "==> 本机缺少脚本，先从 CDN 下载..."
  $stamp = Get-Date -Format "yyyyMMddHHmmss"
  New-Item -ItemType Directory -Force -Path (Join-Path $Root "scripts") | Out-Null
  $files = @(
    "scripts/install_xinshang_daily_windows.ps1",
    "scripts/xinshang_daily_windows.ps1",
    "scripts/fetch_xinshang_tools_windows.ps1"
  )
  foreach ($rel in $files) {
    $url = "https://fastly.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@main/" + $rel + "?t=" + $stamp
    $dest = Join-Path $Root ($rel -replace "/", "\")
    New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
    Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing -TimeoutSec 120
    Write-Host ("[OK] " + $rel)
  }
}

$psExe = (Get-Command powershell.exe).Source
$arg = "-NoProfile -ExecutionPolicy Bypass -File `"$Script`""

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute $psExe -Argument $arg -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -Daily -At "08:30"
$settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -StartWhenAvailable -RestartCount 3 `
  -RestartInterval (New-TimeSpan -Minutes 5) `
  -ExecutionTimeLimit ([TimeSpan]::Zero)
$prin = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $prin -Force | Out-Null

Write-Host ""
Write-Host "[OK] 已注册计划任务: $TaskName"
Write-Host "     每天 08:30 自动：Power BI 月在线商家数 + 初心主看板 + 同分群 117 城"
Write-Host "     日志: $Root\logs\xinshang_daily_YYYYMMDD.log"
Write-Host ""
Write-Host "可选：立即跑一次测试"
Write-Host "  powershell -NoProfile -ExecutionPolicy Bypass -File `"$Script`""
Write-Host ""
Write-Host "外发页: https://1.chuanzangyiqu.top/evaluation/xinshang"
Write-Host "需已安装: ChuanzangWeb5001 + ChuanzangTunnel（install_background_windows.ps1）"
exit 0
