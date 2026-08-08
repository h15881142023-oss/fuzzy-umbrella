# 安装「川藏一区新商评看板」自动同步计划任务：每周二、五 17:00
# 普通用户 PowerShell 即可（无需管理员）：
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

# 用 cmd 包装，便于重定向日志
$bat = Join-Path $Root "scripts\run_xinshang_sync_windows.cmd"
@"
@echo off
cd /d "$Root"
".venv\Scripts\python.exe" "scripts\update_xinshang_dashboard.py" >> "logs\xinshang_sync.log" 2>&1
"@ | Set-Content -Path $bat -Encoding ascii

$scheduled = $false
try {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

  $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$bat`"" -WorkingDirectory $Root
  $t1 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Tuesday -At 17:00
  $t2 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At 17:00
  $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
  # Limited：普通用户可注册，无需管理员
  $prin = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($t1, $t2) -Settings $settings -Principal $prin -Force | Out-Null
  $scheduled = $true
  Write-Host "[OK] scheduled task: $TaskName (Tue/Fri 17:00)"
  Write-Host "log: $logDir\xinshang_sync.log"
}
catch {
  Write-Host "[WARN] Register-ScheduledTask failed: $($_.Exception.Message)"
  Write-Host "==> fallback: schtasks (current user)"
  try {
    schtasks /Delete /TN $TaskName /F 2>$null | Out-Null
  } catch {}
  # 两个触发：周二、周五 17:00
  $tr = "`"$bat`""
  $r1 = schtasks /Create /TN $TaskName /TR $tr /SC WEEKLY /D TUE /ST 17:00 /RL LIMITED /F
  if ($LASTEXITCODE -ne 0) { throw "schtasks create failed: $r1" }
  # 第二个任务名区分周五
  $TaskFri = "${TaskName}Fri"
  try { schtasks /Delete /TN $TaskFri /F 2>$null | Out-Null } catch {}
  $r2 = schtasks /Create /TN $TaskFri /TR $tr /SC WEEKLY /D FRI /ST 17:00 /RL LIMITED /F
  if ($LASTEXITCODE -ne 0) { throw "schtasks create Fri failed: $r2" }
  $scheduled = $true
  Write-Host "[OK] schtasks: $TaskName (Tue) + $TaskFri (Fri) at 17:00"
  Write-Host "log: $logDir\xinshang_sync.log"
}

if (-not $scheduled) {
  Write-Host "[BAD] could not register schedule; will still RunNow if requested"
}

if ($RunNow) {
  Write-Host "==> run once now"
  & $venvPython $updater
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  Write-Host "[OK] dashboard refreshed"
  Write-Host "check: https://1.chuanzangyiqu.top/evaluation/xinshang"
}

Write-Host ""
Write-Host "Done. Domain page reads static HTML; after sync, refresh browser."
