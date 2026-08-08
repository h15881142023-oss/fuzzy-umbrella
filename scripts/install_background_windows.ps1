# Install web + cloudflared as background (no need keep PowerShell windows open)
# Run PowerShell as Administrator once:
#   powershell -ExecutionPolicy Bypass -File .\scripts\install_background_windows.ps1

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
$runWeb = Join-Path $Root "scripts\run_web_windows.py"
$userCfDir = Join-Path $env:USERPROFILE ".cloudflared"
$sysCfDir = "C:\Windows\System32\config\systemprofile\.cloudflared"
$tunnelId = "7224a724-0471-45a8-8adc-80b0fc846b10"
$credName = "$tunnelId.json"

Write-Host "==> project: $Root"

# Require admin
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  Write-Host "[MISS] Please run this script as Administrator"
  exit 1
}

if (-not (Test-Path $venvPython)) {
  Write-Host "[MISS] venv python not found: $venvPython"
  exit 1
}
if (-not (Test-Path $runWeb)) {
  Write-Host "[MISS] launcher not found: $runWeb"
  exit 1
}
if (-not (Test-Path (Join-Path $userCfDir $credName))) {
  Write-Host ("[MISS] tunnel credentials not found: " + (Join-Path $userCfDir $credName))
  exit 1
}

# 1) Scheduled task for Flask web (at startup)
$taskName = "ChuanzangWeb5001"
Write-Host "==> register scheduled task: $taskName"
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute $venvPython -Argument "`"$runWeb`"" -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$principalTask = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principalTask -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Host "==> web task started"

# 2) cloudflared Windows service (needs config under systemprofile)
Write-Host "==> prepare cloudflared system config"
New-Item -ItemType Directory -Force -Path $sysCfDir | Out-Null

$config = @"
tunnel: $tunnelId
credentials-file: $sysCfDir\$credName

ingress:
  - hostname: 1.chuanzangyiqu.top
    service: http://127.0.0.1:5001
  - service: http_status:404
"@
Set-Content -Path (Join-Path $sysCfDir "config.yml") -Value $config -Encoding ascii
Copy-Item -Force (Join-Path $userCfDir $credName) (Join-Path $sysCfDir $credName)

$cf = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cf) {
  Write-Host "[MISS] cloudflared not in PATH"
  exit 1
}

# Stop any running interactive cloudflared first
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# Reinstall service cleanly
Write-Host "==> install cloudflared service"
try { & cloudflared service uninstall | Out-Null } catch {}
& cloudflared service install
Start-Sleep -Seconds 2
Start-Service cloudflared -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

$svc = Get-Service cloudflared -ErrorAction SilentlyContinue
if ($svc -and $svc.Status -eq "Running") {
  Write-Host "[OK] cloudflared service Running"
} else {
  Write-Host "[BAD] cloudflared service not running. Check: Get-Service cloudflared"
}

Write-Host ""
Write-Host "Done. You can close all PowerShell windows now."
Write-Host "Public URL: https://1.chuanzangyiqu.top/evaluation/xinshang"
Write-Host "Web task:   $taskName (AtStartup)"
Write-Host "Tunnel:     Windows service 'cloudflared' (Automatic)"
