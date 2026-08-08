Param(
    [string]$PythonExe = "",
    [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path,
    [string]$TaskName = "todo达成监控",
    [string]$AtTime = "14:00",
    [switch]$RunWhetherUserLoggedOn
)

$ErrorActionPreference = "Stop"

$runner = Join-Path $ProjectRoot "scripts\run_todo_achievement_monitor_task.ps1"
if (!(Test-Path $runner)) {
    throw "runner missing: $runner"
}

$logDir = "C:\Windows\Temp\todo_monitor"
if (!(Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $PythonExe = (Get-Command python -ErrorAction Stop).Source
}

$argList = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $runner,
    "-ProjectRoot", $ProjectRoot,
    "-PythonExe", $PythonExe,
    "-Headless"
)
$arg = ($argList | ForEach-Object { if ($_ -match '\s') { '"{0}"' -f $_ } else { $_ } }) -join " "

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arg -WorkingDirectory $ProjectRoot
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Wednesday,Friday -At $AtTime
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1)

if ($RunWhetherUserLoggedOn) {
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Highest
}
else {
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null

Write-Output "TASK_OK name=$TaskName days=Mon,Wed,Fri time=$AtTime python=$PythonExe root=$ProjectRoot log=$logDir\monitor.log"
if ($RunWhetherUserLoggedOn) {
    Write-Output "MODE=S4U"
}
else {
    Write-Output "MODE=INTERACTIVE"
}
