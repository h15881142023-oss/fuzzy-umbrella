# One-shot test of the same LR profit-fill task (scrape+fill+WPS+WeCom).
# Default: today 15:30 local time, then the task expires (does not repeat).
# Usage (admin PowerShell, or this script will UAC-elevate):
#   powershell -ExecutionPolicy Bypass -File scripts\install_lr_profit_fill_once.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\install_lr_profit_fill_once.ps1 -AtTime 15:30
param(
    [string]$AtTime = "15:30"
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_local_common.ps1"
$Root = Get-RepoRoot
$TaskName = "ChuanzangLrProfitFillOnce"

function Test-IsAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($id)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdmin)) {
    Write-Host "Need admin to write Task Scheduler. UAC prompt next; click Yes."
    $self = if ($PSCommandPath) { $PSCommandPath } else { $MyInvocation.MyCommand.Path }
    $arg = "-NoProfile -ExecutionPolicy Bypass -File `"$self`" -AtTime `"$AtTime`""
    $p = Start-Process -FilePath "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
        -Verb RunAs -ArgumentList $arg -Wait -PassThru
    exit $p.ExitCode
}

$scriptPath = Join-Path $Root "scripts\run_lr_profit_fill_local.ps1"
if (-not (Test-Path -LiteralPath $scriptPath)) {
    throw "missing $scriptPath"
}

try {
    $parts = $AtTime.Split(":")
    $hh = [int]$parts[0]
    $mm = [int]$parts[1]
} catch {
    throw "AtTime must be HH:mm, got $AtTime"
}

$at = Get-Date -Hour $hh -Minute $mm -Second 0
$now = Get-Date
if ($at -le $now.AddMinutes(1)) {
    $at = $now.AddMinutes(3)
    $at = Get-Date -Year $at.Year -Month $at.Month -Day $at.Day -Hour $at.Hour -Minute $at.Minute -Second 0
    Write-Host ("Requested time already passed or too soon. Using {0:HH:mm} instead." -f $at)
}

$psExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$arg = "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""
$action = New-ScheduledTaskAction -Execute $psExe -Argument $arg -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -Once -At $at
$trigger.EndBoundary = $at.AddHours(2).ToString("s")

$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

$settings = $null
try {
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -WakeToRun `
        -MultipleInstances IgnoreNew `
        -DeleteExpiredTaskAfter (New-TimeSpan -Minutes 10)
} catch {
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -WakeToRun `
        -MultipleInstances IgnoreNew
}

try { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue } catch {}
cmd.exe /c "schtasks /Delete /TN `"$TaskName`" /F >NUL 2>&1" | Out-Null

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Force | Out-Null

Write-Host ("Installed one-shot: {0} at {1:yyyy-MM-dd HH:mm} (local)" -f $TaskName, $at)
Write-Host "Same runner as 23:30: scripts\run_lr_profit_fill_local.ps1 (target=yesterday)"
Write-Host "Stay logged in at the desktop. Do not lock/log off."
Write-Host "Watch:"
Write-Host "  schtasks /Query /TN ChuanzangLrProfitFillOnce /V /FO LIST"
Write-Host "  Get-Content logs\lr_profit_fill_local.log -Wait -Tail 40 -Encoding UTF8"
