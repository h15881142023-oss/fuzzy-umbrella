# 安装「川藏一区新商评看板」自动同步计划任务：每周二、五 17:00
# 建议以管理员 PowerShell 运行：
#   powershell -ExecutionPolicy Bypass -File .\scripts\install_xinshang_schedule_windows.ps1
# 也可加 -RunNow 立刻跑一次：
#   powershell -ExecutionPolicy Bypass -File .\scripts\install_xinshang_schedule_windows.ps1 -RunNow

param(
  [switch]$RunNow
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$TaskName = "ChuanzangXinshangSync"
$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
$updater = Join-Path $Root "scripts\update_xinshang_dashboard.py"
$logDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (-not (Test-Path $venvPython)) {
  Write-Host "[MISS] $venvPython"
  Write-Host "先执行: python -m venv .venv ; .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
  exit 1
}
if (-not (Test-Path $updater)) {
  Write-Host "[MISS] $updater"
  exit 1
}

# 用 cmd 包装，便于重定向日志（计划任务对重定向支持差）
$bat = Join-Path $Root "scripts\run_xinshang_sync_windows.cmd"
@"
@echo off
cd /d "$Root"
".venv\Scripts\python.exe" "scripts\update_xinshang_dashboard.py" >> "logs\xinshang_sync.log" 2>&1
"@ | Set-Content -Path $bat -Encoding ascii

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute $bat -WorkingDirectory $Root
$t1 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Tuesday -At 17:00
$t2 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At 17:00
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
$prin = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($t1, $t2) -Settings $settings -Principal $prin -Force | Out-Null
Write-Host "[OK] scheduled task: $TaskName (Tue/Fri 17:00)"
Write-Host "log: $logDir\xinshang_sync.log"

if ($RunNow) {
  Write-Host "==> run once now"
  & $venvPython $updater
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  Write-Host "[OK] dashboard refreshed"
  Write-Host "check: https://1.chuanzangyiqu.top/evaluation/xinshang"
}

Write-Host ""
Write-Host "Done. Domain page reads static HTML; after sync, refresh browser."
