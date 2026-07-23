# 安装全部本机自动化到 Windows 任务计划程序
# 用法（在仓库根目录）：
#   powershell -ExecutionPolicy Bypass -File scripts\install_local_automations_windows.ps1

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_local_common.ps1"
$Root = Get-RepoRoot

function Register-CzTask {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$ScriptRel,
        [Parameter(Mandatory = $true)][ValidateSet("DAILY", "WEEKLY")][string]$Schedule,
        [Parameter(Mandatory = $true)][string]$StartTime,
        [string]$DayOfWeek = ""
    )
    $scriptPath = Join-Path $Root $ScriptRel
    if (-not (Test-Path $scriptPath)) {
        throw "脚本不存在: $scriptPath"
    }

    $tr = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""
    schtasks /Delete /TN $Name /F 2>$null | Out-Null

    if ($Schedule -eq "DAILY") {
        $out = schtasks /Create /TN $Name /TR $tr /SC DAILY /ST $StartTime /F 2>&1
    } else {
        $out = schtasks /Create /TN $Name /TR $tr /SC WEEKLY /D $DayOfWeek /ST $StartTime /F 2>&1
    }
    $out | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "创建任务失败: $Name；输出: $out"
    }
    Write-Host "已安装: $Name ($Schedule $StartTime$(if ($DayOfWeek) { " $DayOfWeek" }))"
}

Register-CzTask -Name "ChuanzangVisitCheckLocal" `
    -ScriptRel "scripts\run_visit_check_local.ps1" `
    -Schedule DAILY -StartTime "09:00"

Register-CzTask -Name "ChuanzangStoreMorningLocal" `
    -ScriptRel "scripts\run_store_morning_monitor_local.ps1" `
    -Schedule DAILY -StartTime "08:30"

Register-CzTask -Name "ChuanzangLrDailyLocal" `
    -ScriptRel "scripts\run_lr_daily_local.ps1" `
    -Schedule DAILY -StartTime "23:30"

Register-CzTask -Name "ChuanzangKpiTodoMonLocal" `
    -ScriptRel "scripts\run_kpi_todo_local.ps1" `
    -Schedule WEEKLY -DayOfWeek MON -StartTime "14:00"

Register-CzTask -Name "ChuanzangKpiTodoThuLocal" `
    -ScriptRel "scripts\run_kpi_todo_local.ps1" `
    -Schedule WEEKLY -DayOfWeek THU -StartTime "14:00"

Write-Host ""
Write-Host "全部 Windows 定时任务已安装。"
Write-Host "请确认 Automations 面板里那 5 个 Cloud 任务已停用，避免重复执行。"
Write-Host "手动试跑："
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\run_kpi_todo_local.ps1"
Write-Host "卸载："
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\uninstall_local_automations_windows.ps1"
Write-Host "说明：scripts\LOCAL_AUTOMATIONS.md"
