# Install all local automations into Windows Task Scheduler
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\install_local_automations_windows.ps1
# Must run elevated (script will try UAC self-elevation).

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_local_common.ps1"
$Root = Get-RepoRoot

function Test-IsAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($id)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdmin)) {
    Write-Host ""
    Write-Host "需要管理员权限才能写入「任务计划程序」。"
    Write-Host "正在弹出 UAC，请点击「是」..."
    Write-Host ""
    $self = if ($PSCommandPath) { $PSCommandPath } else { $MyInvocation.MyCommand.Path }
    $arg = "-NoProfile -ExecutionPolicy Bypass -File `"$self`""
    try {
        $p = Start-Process -FilePath "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
            -Verb RunAs -ArgumentList $arg -Wait -PassThru
        exit $p.ExitCode
    } catch {
        Write-Host "自动提权失败。请手动："
        Write-Host "  1. 开始菜单搜索 PowerShell → 右键「以管理员身份运行」"
        Write-Host "  2. cd `"$Root`""
        Write-Host "  3. powershell -ExecutionPolicy Bypass -File scripts\install_local_automations_windows.ps1"
        throw
    }
}

Write-Host "Admin OK. Repo: $Root"

function Remove-CzTaskQuiet {
    param([string]$Name)
    try {
        Unregister-ScheduledTask -TaskName $Name -Confirm:$false -ErrorAction SilentlyContinue
    } catch {}
    # also try schtasks for old registrations
    cmd.exe /c "schtasks /Delete /TN `"$Name`" /F >NUL 2>&1" | Out-Null
}

function Register-CzTask {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$ScriptRel,
        [Parameter(Mandatory = $true)][ValidateSet("DAILY", "WEEKLY")][string]$Schedule,
        [Parameter(Mandatory = $true)][string]$StartTime,
        [string]$DayOfWeek = ""
    )
    $scriptPath = Join-Path $Root $ScriptRel
    if (-not (Test-Path -LiteralPath $scriptPath)) {
        throw "Script not found: $scriptPath"
    }

    $psExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    $arg = "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""
    $action = New-ScheduledTaskAction -Execute $psExe -Argument $arg -WorkingDirectory $Root

    # HH:mm
    $parts = $StartTime.Split(":")
    $at = Get-Date -Hour ([int]$parts[0]) -Minute ([int]$parts[1]) -Second 0

    if ($Schedule -eq "DAILY") {
        $trigger = New-ScheduledTaskTrigger -Daily -At $at
    } else {
        $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $DayOfWeek -At $at
    }

    # Interactive：登录桌面时运行（WPS 截图需要）
    $principal = New-ScheduledTaskPrincipal `
        -UserId $env:USERNAME `
        -LogonType Interactive `
        -RunLevel Highest

    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew

    Remove-CzTaskQuiet -Name $Name
    Register-ScheduledTask `
        -TaskName $Name `
        -Action $action `
        -Trigger $trigger `
        -Principal $principal `
        -Settings $settings `
        -Force | Out-Null

    $extra = ""
    if ($DayOfWeek) { $extra = " $DayOfWeek" }
    Write-Host "Installed: $Name ($Schedule $StartTime$extra)"
}

Remove-CzTaskQuiet -Name "ChuanzangLrDailyLocal"

Register-CzTask -Name "ChuanzangVisitCheckLocal" `
    -ScriptRel "scripts\run_visit_check_local.ps1" `
    -Schedule DAILY -StartTime "09:00"

Register-CzTask -Name "ChuanzangStoreMorningLocal" `
    -ScriptRel "scripts\run_store_morning_monitor_local.ps1" `
    -Schedule DAILY -StartTime "08:30"

Register-CzTask -Name "ChuanzangLrDatasourceLocal" `
    -ScriptRel "scripts\run_lr_datasource_local.ps1" `
    -Schedule DAILY -StartTime "23:15"

Register-CzTask -Name "ChuanzangLrProfitFillLocal" `
    -ScriptRel "scripts\run_lr_profit_fill_local.ps1" `
    -Schedule DAILY -StartTime "23:30"

Register-CzTask -Name "ChuanzangKpiTodoMonLocal" `
    -ScriptRel "scripts\run_kpi_todo_local.ps1" `
    -Schedule WEEKLY -DayOfWeek Monday -StartTime "14:00"

Register-CzTask -Name "ChuanzangKpiTodoThuLocal" `
    -ScriptRel "scripts\run_kpi_todo_local.ps1" `
    -Schedule WEEKLY -DayOfWeek Thursday -StartTime "14:00"

Write-Host ""
Write-Host "All Windows scheduled tasks installed."
Write-Host "LR tasks (separate):"
Write-Host "  ChuanzangLrDatasourceLocal  23:15  利润数据源推送"
Write-Host "  ChuanzangLrProfitFillLocal  23:30  利润填写推送"
Write-Host "Verify:"
Write-Host "  Get-ScheduledTask -TaskName ChuanzangLr*"
Write-Host "Docs: scripts\LOCAL_AUTOMATIONS.md"
