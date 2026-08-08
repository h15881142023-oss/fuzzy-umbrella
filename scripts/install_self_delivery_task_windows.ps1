Param(
    [string]$PythonExe = "",
    [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path,
    [string]$TaskName = "自配上线播报",
    [string]$DailyTime = "10:00",
    [switch]$Headless,
    [switch]$RunWhetherUserLoggedOn
)

$ErrorActionPreference = "Stop"

$runner = Join-Path $ProjectRoot "scripts\run_self_delivery_monitor_task.ps1"
if (!(Test-Path $runner)) {
    throw "runner missing: $runner"
}

$logDir = "C:\Windows\Temp\zpei_monitor"
if (!(Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $PythonExe = (Get-Command python -ErrorAction Stop).Source
}

$argList = New-Object System.Collections.Generic.List[string]
$argList.Add("-NoProfile")
$argList.Add("-ExecutionPolicy")
$argList.Add("Bypass")
$argList.Add("-File")
$argList.Add($runner)
$argList.Add("-ProjectRoot")
$argList.Add($ProjectRoot)
$argList.Add("-PythonExe")
$argList.Add($PythonExe)
if ($Headless -or $RunWhetherUserLoggedOn) {
    $argList.Add("-Headless")
}

$arg = ($argList | ForEach-Object {
    if ($_ -match '\s') { '"{0}"' -f $_ } else { $_ }
}) -join " "

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arg -WorkingDirectory $ProjectRoot
$trigger = New-ScheduledTaskTrigger -Daily -At $DailyTime
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2)

if ($RunWhetherUserLoggedOn) {
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Highest
}
else {
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null

Write-Output "TASK_OK name=$TaskName time=$DailyTime python=$PythonExe root=$ProjectRoot log=$logDir\monitor.log"
if ($RunWhetherUserLoggedOn) {
    Write-Output "MODE=S4U_HEADLESS"
}
else {
    Write-Output "MODE=INTERACTIVE"
}
