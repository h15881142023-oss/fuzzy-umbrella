Param(
    [string]$PythonExe = "python",
    [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path,
    [string]$TaskName = "SelfDeliveryMonitor",
    [string]$DailyTime = "09:30",
    [switch]$Headless
)

$scriptPath = Join-Path $ProjectRoot "scripts\self_delivery_monitor_windows.py"
if (!(Test-Path $scriptPath)) {
    throw "脚本不存在: $scriptPath"
}

$logDir = "C:\Windows\Temp\zpei_monitor"
if (!(Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

$headlessArg = ""
if ($Headless) {
    $headlessArg = " --headless"
}

$runCmd = "`"$PythonExe`" `"$scriptPath`"$headlessArg >> `"$logDir\monitor.log`" 2>&1"
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c $runCmd"
$trigger = New-ScheduledTaskTrigger -Daily -At $DailyTime
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Force | Out-Null

Write-Output "任务安装完成: $TaskName（每日 $DailyTime）"
