# Uninstall all local Windows scheduled tasks
$ErrorActionPreference = "Continue"

$names = @(
    "ChuanzangVisitCheckLocal",
    "ChuanzangStoreMorningLocal",
    "ChuanzangLrDailyLocal",
    "ChuanzangLrDatasourceLocal",
    "ChuanzangLrProfitFillLocal",
    "ChuanzangKpiTodoMonLocal",
    "ChuanzangKpiTodoThuLocal"
)

foreach ($n in $names) {
    & schtasks.exe /Delete /TN $n /F 2>$null | Out-Null
    Write-Host "Removed: $n"
}

Write-Host "All local Windows scheduled tasks uninstalled."
