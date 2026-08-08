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
    throw "运行器不存在: $runner"
}

$logDir = "C:\Windows\Temp\zpei_monitor"
if (!(Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $PythonExe = (Get-Command python -ErrorAction Stop).Source
}

$headlessFlag = ""
if ($Headless -or $RunWhetherUserLoggedOn) {
    $headlessFlag = " -Headless"
}

# 用 powershell 直接跑 runner，避免 cmd 重定向在无人登录下失效
$arg = @(
    "-NoProfile"
    "-ExecutionPolicy Bypass"
    "-File `"$runner`""
    "-ProjectRoot `"$ProjectRoot`""
    "-PythonExe `"$PythonExe`""
    $headlessFlag
) -join " "

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument $arg.Trim() `
    -WorkingDirectory $ProjectRoot

$trigger = New-ScheduledTaskTrigger -Daily -At $DailyTime
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

if ($RunWhetherUserLoggedOn) {
    # 无人登录也运行：需要当前用户有权限，且建议配合 -Headless
    $principal = New-ScheduledTaskPrincipal `
        -UserId "$env:USERDOMAIN\$env:USERNAME" `
        -LogonType S4U `
        -RunLevel Highest
}
else {
    $principal = New-ScheduledTaskPrincipal `
        -UserId "$env:USERDOMAIN\$env:USERNAME" `
        -LogonType Interactive `
        -RunLevel Limited
}

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Force | Out-Null

Write-Output "任务安装完成: $TaskName"
Write-Output "执行时间: 每天 $DailyTime"
Write-Output "Python: $PythonExe"
Write-Output "项目目录: $ProjectRoot"
Write-Output "日志: $logDir\monitor.log"
if ($RunWhetherUserLoggedOn) {
    Write-Output "模式: 无人登录也运行 + 无头浏览器"
}
else {
    Write-Output "模式: 仅用户登录时运行"
}
