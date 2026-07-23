# 卸载全部本机 Windows 定时任务
$ErrorActionPreference = "Continue"

$names = @(
    "ChuanzangVisitCheckLocal",
    "ChuanzangStoreMorningLocal",
    "ChuanzangLrDailyLocal",
    "ChuanzangKpiTodoMonLocal",
    "ChuanzangKpiTodoThuLocal"
)

foreach ($n in $names) {
    schtasks /Delete /TN $n /F 2>$null | Out-Null
    Write-Host "已删除: $n"
}

Write-Host "全部本机 Windows 定时任务已卸载"
