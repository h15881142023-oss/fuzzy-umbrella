# 卸载新商评日更计划任务（含经营宝同款新任务名与旧名）
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\uninstall_xinshang_daily_windows.ps1

$ErrorActionPreference = "Continue"
$names = @(
  "CZ1_Xinshang_WeCom_TueFriPush",
  "ChuanzangXinshangDaily",
  "ChuanzangXinshangSync",
  "ChuanzangXinshangSyncFri"
)
foreach ($TaskName in $names) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
  schtasks /Delete /TN $TaskName /F 2>$null | Out-Null
}

Write-Host "[OK] 已卸载计划任务: $($names -join ', ')"
