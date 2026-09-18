# Use Scheduled Tasks for both web + cloudflared (more reliable than Windows service on this PC)
# Run PowerShell as Administrator:
#   powershell -ExecutionPolicy Bypass -File .\scripts\install_background_windows.ps1

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
$runWeb = Join-Path $Root "scripts\run_web_windows.py"
$userCfDir = Join-Path $env:USERPROFILE ".cloudflared"
$tunnelId = "7224a724-0471-45a8-8adc-80b0fc846b10"
$credName = "$tunnelId.json"
$userConfig = Join-Path $userCfDir "config.yml"
$cfExe = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cfExe) {
  $guess = @(
    "${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe",
    "$env:ProgramFiles\cloudflared\cloudflared.exe"
  ) | Where-Object { Test-Path $_ } | Select-Object -First 1
  $cfExe = $guess
}

Write-Host "==> project: $Root"

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  Write-Host "[MISS] Please run this script as Administrator"
  exit 1
}

if (-not (Test-Path $venvPython)) { Write-Host "[MISS] $venvPython"; exit 1 }
if (-not (Test-Path $runWeb)) { Write-Host "[MISS] $runWeb"; exit 1 }
if (-not (Test-Path (Join-Path $userCfDir $credName))) { Write-Host "[MISS] credentials"; exit 1 }
if (-not $cfExe) { Write-Host "[MISS] cloudflared.exe"; exit 1 }

# Ensure user config exists
New-Item -ItemType Directory -Force -Path $userCfDir | Out-Null
@"
tunnel: $tunnelId
credentials-file: $userCfDir\$credName

ingress:
  - hostname: 1.chuanzangyiqu.top
    service: http://127.0.0.1:5001
  - service: http_status:404
"@ | Set-Content -Path $userConfig -Encoding ascii

# Stop broken Windows service if present (optional, keep AUTO but unused)
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
try { Stop-Service cloudflared -Force -ErrorAction SilentlyContinue } catch {}
try { & cloudflared service uninstall | Out-Null } catch {}

function Register-BgTask {
  param(
    [string]$TaskName,
    [string]$Execute,
    [string]$Argument,
    [string]$WorkDir
  )
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
  $action = New-ScheduledTaskAction -Execute $Execute -Argument $Argument -WorkingDirectory $WorkDir
  $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
  $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
  $prin = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $prin -Force | Out-Null
  Start-ScheduledTask -TaskName $TaskName
  Write-Host ("[OK] task started: " + $TaskName)
}

Write-Host "==> register web task"
Register-BgTask -TaskName "ChuanzangWeb5001" -Execute $venvPython -Argument "`"$runWeb`"" -WorkDir $Root

Write-Host "==> register tunnel task"
$cfArgs = "tunnel --config `"$userConfig`" run chuanzang-win"
Register-BgTask -TaskName "ChuanzangTunnel" -Execute $cfExe -Argument $cfArgs -WorkDir $userCfDir

Start-Sleep -Seconds 4

# Checks
$listen = netstat -ano | Select-String ":5001\s+.*LISTENING"
if ($listen) { Write-Host "[OK] port 5001 listening" } else { Write-Host "[BAD] port 5001 not listening" }

$cfProc = Get-Process cloudflared -ErrorAction SilentlyContinue
if ($cfProc) { Write-Host ("[OK] cloudflared process running pid=" + ($cfProc.Id -join ",")) } else { Write-Host "[BAD] cloudflared process not running" }

Write-Host ""
Write-Host "Done. Close PowerShell windows and test:"
Write-Host "  https://1.chuanzangyiqu.top/evaluation/xinshang"
Write-Host "Tasks: ChuanzangWeb5001 + ChuanzangTunnel (AtLogOn, auto restart)"
