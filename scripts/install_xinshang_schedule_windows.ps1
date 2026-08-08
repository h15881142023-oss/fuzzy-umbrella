# Install xinshang auto-sync (Tue/Fri 17:00).
# Prefer Web5001 embedded clock + Startup shortcut (no admin / Task Scheduler).
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
if (-not (Test-Path $clock)) {
  Write-Host "[MISS] $clock"
  exit 1
}

function Test-XinshangClockRunning {
  $procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and ($_.CommandLine -like "*xinshang_clock_windows.py*") }
  return [bool]$procs
}

function Start-XinshangClock {
  if (Test-XinshangClockRunning) {
    Write-Host "[OK] xinshang clock already running"
    return
  }
  # Avoid Start-Process ArgumentList quoting issues on older PowerShell
  $cmd = "cd /d `"$Root`" && start `"xinshang-clock`" /MIN `"$venvPython`" `"$clock`""
  cmd.exe /c $cmd
  Start-Sleep -Seconds 1
  if (Test-XinshangClockRunning) {
    Write-Host "[OK] started xinshang_clock_windows.py"
  } else {
    Write-Host "[BAD] failed to start xinshang clock"
    Write-Host "manual: `"$venvPython`" `"$clock`""
  }
}

function Restart-Web5001BestEffort {
  Write-Host "==> prefer: xinshang clock inside Web5001 (run_web_windows.py)"
  $task = Get-ScheduledTask -TaskName "ChuanzangWeb5001" -ErrorAction SilentlyContinue
  if (-not $task) {
    Write-Host "[INFO] ChuanzangWeb5001 not found"
    return
  }
  try {
    if (Get-Command Restart-ScheduledTask -ErrorAction SilentlyContinue) {
      Restart-ScheduledTask -TaskName "ChuanzangWeb5001" -ErrorAction Stop
      Write-Host "[OK] restarted ChuanzangWeb5001"
      return
    }
    schtasks /End /TN "ChuanzangWeb5001" 2>$null | Out-Null
    Start-Sleep -Seconds 1
    schtasks /Run /TN "ChuanzangWeb5001" 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
      Write-Host "[OK] schtasks restarted ChuanzangWeb5001"
      return
    }
  } catch {
    Write-Host "[WARN] restart Web5001 failed: $($_.Exception.Message)"
  }
  Write-Host "[INFO] please re-run start_domain_windows.ps1 if domain is down"
}

# 1) try restart web so embedded clock loads new run_web_windows.py
Restart-Web5001BestEffort

# 2) Startup shortcut (no Task Scheduler permission needed)
$startup = [Environment]::GetFolderPath("Startup")
$cmdPath = Join-Path $Root "scripts\run_xinshang_clock_windows.cmd"
@"
@echo off
cd /d "$Root"
start "xinshang-clock" /MIN ".venv\Scripts\python.exe" "scripts\xinshang_clock_windows.py"
"@ | Set-Content -Path $cmdPath -Encoding ascii

$lnkPath = Join-Path $startup "ChuanzangXinshangClock.lnk"
try {
  $w = New-Object -ComObject WScript.Shell
  $sc = $w.CreateShortcut($lnkPath)
  $sc.TargetPath = $cmdPath
  $sc.WorkingDirectory = $Root
  $sc.WindowStyle = 7
  $sc.Description = "Chuanzang xinshang Tue/Fri 17:00 clock"
  $sc.Save()
  Write-Host "[OK] Startup shortcut: $lnkPath"
} catch {
  Write-Host "[WARN] Startup shortcut failed: $($_.Exception.Message)"
}

# 3) Task Scheduler optional (often Access Denied — ignore)
$TaskName = "ChuanzangXinshangSync"
$bat = Join-Path $Root "scripts\run_xinshang_sync_windows.cmd"
@"
@echo off
cd /d "$Root"
".venv\Scripts\python.exe" "scripts\update_xinshang_dashboard.py" >> "logs\xinshang_sync.log" 2>&1
"@ | Set-Content -Path $bat -Encoding ascii

$oldEap = $ErrorActionPreference
$ErrorActionPreference = "Stop"
try {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
  $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$bat`"" -WorkingDirectory $Root
  $t1 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Tuesday -At 17:00
  $t2 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At 17:00
  $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
  $prin = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($t1, $t2) -Settings $settings -Principal $prin -Force | Out-Null
  Write-Host "[OK] scheduled task: $TaskName"
} catch {
  Write-Host "[INFO] Task Scheduler denied (ignored). Using Startup/Web clock."
} finally {
  $ErrorActionPreference = $oldEap
}

# 4) start standalone clock for current session
Start-XinshangClock

if ($RunNow) {
  Write-Host "==> run once now"
  & $venvPython $updater
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  Write-Host "[OK] dashboard refreshed"
  Write-Host "check: https://1.chuanzangyiqu.top/evaluation/xinshang"
}

Write-Host ""
Write-Host "Done. Schedule: Startup clock (+ Web5001 thread after web restart)."
Write-Host "log: $logDir\xinshang_sync.log"
