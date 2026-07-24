# Install all local automations into Windows Task Scheduler
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\install_local_automations_windows.ps1

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_local_common.ps1"
$Root = Get-RepoRoot

function Invoke-SchtasksQuiet {
    param([Parameter(Mandatory = $true)][string[]]$Args)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $out = & schtasks.exe @Args 2>&1
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    return @{ Code = $code; Output = $out }
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
    if (-not (Test-Path $scriptPath)) {
        throw "Script not found: $scriptPath"
    }

    $tr = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""

    [void](Invoke-SchtasksQuiet -Args @("/Delete", "/TN", $Name, "/F"))

    if ($Schedule -eq "DAILY") {
        $res = Invoke-SchtasksQuiet -Args @("/Create", "/TN", $Name, "/TR", $tr, "/SC", "DAILY", "/ST", $StartTime, "/F")
    } else {
        $res = Invoke-SchtasksQuiet -Args @("/Create", "/TN", $Name, "/TR", $tr, "/SC", "WEEKLY", "/D", $DayOfWeek, "/ST", $StartTime, "/F")
    }
    if ($res.Output) { $res.Output | Out-Host }
    if ($res.Code -ne 0) {
        throw "Failed to create task: $Name ; exit=$($res.Code) ; output=$($res.Output)"
    }
    $extra = ""
    if ($DayOfWeek) { $extra = " $DayOfWeek" }
    Write-Host "Installed: $Name ($Schedule $StartTime$extra)"
}

Register-CzTask -Name "ChuanzangVisitCheckLocal" `
    -ScriptRel "scripts\run_visit_check_local.ps1" `
    -Schedule DAILY -StartTime "09:00"

Register-CzTask -Name "ChuanzangStoreMorningLocal" `
    -ScriptRel "scripts\run_store_morning_monitor_local.ps1" `
    -Schedule DAILY -StartTime "08:30"

# 两个 LR 任务必须分开，禁止合并
Register-CzTask -Name "ChuanzangLrDatasourceLocal" `
    -ScriptRel "scripts\run_lr_datasource_local.ps1" `
    -Schedule DAILY -StartTime "23:15"

Register-CzTask -Name "ChuanzangLrProfitFillLocal" `
    -ScriptRel "scripts\run_lr_profit_fill_local.ps1" `
    -Schedule DAILY -StartTime "23:30"

# 清理旧的合并任务名（若存在）
[void](Invoke-SchtasksQuiet -Args @("/Delete", "/TN", "ChuanzangLrDailyLocal", "/F"))

Register-CzTask -Name "ChuanzangKpiTodoMonLocal" `
    -ScriptRel "scripts\run_kpi_todo_local.ps1" `
    -Schedule WEEKLY -DayOfWeek MON -StartTime "14:00"

Register-CzTask -Name "ChuanzangKpiTodoThuLocal" `
    -ScriptRel "scripts\run_kpi_todo_local.ps1" `
    -Schedule WEEKLY -DayOfWeek THU -StartTime "14:00"

Write-Host ""
Write-Host "All Windows scheduled tasks installed."
Write-Host "LR tasks (separate):"
Write-Host "  ChuanzangLrDatasourceLocal  23:15  利润数据源推送"
Write-Host "  ChuanzangLrProfitFillLocal  23:30  利润填写推送"
Write-Host "Disable Cloud Automations to avoid duplicates."
Write-Host "Docs: scripts\LOCAL_AUTOMATIONS.md"
