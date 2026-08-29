# 卸载新商评日更计划任务
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\uninstall_xinshang_daily_windows.ps1

$ErrorActionPreference = "Continue"
$TaskName = "ChuanzangXinshangDaily"

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
schtasks /Delete /TN $TaskName /F 2>$null | Out-Null

Write-Host "[OK] 已卸载计划任务 $TaskName"
