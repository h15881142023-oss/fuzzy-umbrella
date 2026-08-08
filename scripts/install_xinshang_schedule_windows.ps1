# 安装「川藏一区新商评看板」自动同步（每周二、五 17:00）
# 本机若禁止创建计划任务，会改挂到 Web 常驻进程 / 启动文件夹，无需管理员。
#
#   powershell -ExecutionPolicy Bypass -File .\scripts\install_xinshang_schedule_windows.ps1 -RunNow

param(
  [switch]$RunNow
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
$updater = Join-Path $Root "scripts\update_xinshang_dashboard.py"
$clock = Join-Path $Root "scripts\xinshang_clock_windows.py"
$logDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (-not (Test-Path $venvPython)) {
  Write-Host "[MISS] $venvPython"
  exit 1
}
if (-not (Test-Path $updater)) {
  Write-Host "[MISS] $updater"
  exit 1
}

# 1) 首选：挂到已有 Web 常驻（ChuanzangWeb5001 跑 run_web_windows.py，内嵌时钟）
Write-Host "==> prefer: xinshang clock inside Web5001 (run_web_windows.py)"
$webTask = Get-ScheduledTask -TaskName "ChuanzangWeb5001" -ErrorAction SilentlyContinue
if ($webTask) {
  try {
    Restart-ScheduledTask -TaskName "ChuanzangWeb5001" -ErrorAction Stop
    Write-Host "[OK] restarted ChuanzangWeb5001 — Tue/Fri 17:00 sync is embedded"
  } catch {
    Write-Host "[WARN] cannot restart ChuanzangWeb5001: $($_.Exception.Message)"
    Write-Host "请手动结束占用 5001 的 python 后，再启动:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\start_domain_windows.ps1"
  }
} else {
  Write-Host "[INFO] ChuanzangWeb5001 not found; will use Startup folder clock"
}

# 2) 备用：当前用户 Startup 启动独立时钟（不需要计划任务权限）
$startup = [Environment]::GetFolderPath("Startup")
$cmdPath = Join-Path $Root "scripts\run_xinshang_clock_windows.cmd"
@"
@echo off
cd /d "$Root"
start "" /MIN ".venv\Scripts\python.exe" "scripts\xinshang_clock_windows.py"
"@ | Set-Content -Path $cmdPath -Encoding ascii

$lnkPath = Join-Path $startup "ChuanzangXinshangClock.lnk"
try {
  $w = New-Object -ComObject WScript.Shell
  $sc = $w.CreateShortcut($lnkPath)
  $sc.TargetPath = $cmdPath
  $sc.WorkingDirectory = $Root
  $sc.WindowStyle = 7
  $sc.Description = "川藏一区新商评 周二/五 17:00 同步时钟"
  $sc.Save()
  Write-Host "[OK] Startup shortcut: $lnkPath"
} catch {
  Write-Host "[WARN] Startup shortcut failed: $($_.Exception.Message)"
}

# 3) 尝试计划任务（多数环境会拒绝访问，失败可忽略）
$TaskName = "ChuanzangXinshangSync"
$bat = Join-Path $Root "scripts\run_xinshang_sync_windows.cmd"
@"
@echo off
cd /d "$Root"
".venv\Scripts\python.exe" "scripts\update_xinshang_dashboard.py" >> "logs\xinshang_sync.log" 2>&1
"@ | Set-Content -Path $bat -Encoding ascii

try {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
  $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$bat`"" -WorkingDirectory $Root
  $t1 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Tuesday -At 17:00
  $t2 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At 17:00
  $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
  $prin = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($t1, $t2) -Settings $settings -Principal $prin -Force | Out-Null
  Write-Host "[OK] scheduled task: $TaskName (Tue/Fri 17:00)"
} catch {
  Write-Host "[INFO] Task Scheduler denied (ignored). Using Web/Startup clock instead."
}

# 4) 立刻拉起一次独立时钟进程（当前会话，关机前有效；登录后靠 Startup）
$clockProc = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -and $_.CommandLine -like "*xinshang_clock_windows.py*" }
if (-not $clockProc) {
  Start-Process -FilePath $venvPython -ArgumentList "`"$clock`"" -WorkingDirectory $Root -WindowStyle Minimized
  Write-Host "[OK] started xinshang_clock_windows.py (minimized)"
} else {
  Write-Host "[OK] xinshang clock already running"
}

if ($RunNow) {
  Write-Host "==> run once now"
  & $venvPython $updater
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  Write-Host "[OK] dashboard refreshed"
  Write-Host "check: https://1.chuanzangyiqu.top/evaluation/xinshang"
}

Write-Host ""
Write-Host "Done. Schedule path: Web5001 thread + Startup clock (no admin needed)."
Write-Host "log: $logDir\xinshang_sync.log"
