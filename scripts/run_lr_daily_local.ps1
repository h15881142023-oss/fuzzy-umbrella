# 兼容旧入口：转发到「利润填写推送」
# 请优先使用 scripts\run_lr_profit_fill_local.ps1
param(
    [string]$TargetDate = ""
)
$ErrorActionPreference = "Continue"
Write-Host "[compat] run_lr_daily_local.ps1 -> run_lr_profit_fill_local.ps1 (利润填写推送)"
if ($TargetDate) {
    & "$PSScriptRoot\run_lr_profit_fill_local.ps1" -TargetDate $TargetDate
} else {
    & "$PSScriptRoot\run_lr_profit_fill_local.ps1"
}
exit $LASTEXITCODE
