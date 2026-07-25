# 仅用已填好的 LR 日报 xlsx：WPS/PowerShell 导出五城图 + 企微推送（跳过抓取填表）
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts\run_lr_kanban_push_existing.ps1 -TargetDate 2026-07-24
#   powershell -ExecutionPolicy Bypass -File scripts\run_lr_kanban_push_existing.ps1 -Xlsx "lr\work\LR日报_2026-07-24.xlsx" -TargetDate 2026-07-24
param(
    [string]$TargetDate = "",
    [string]$Xlsx = ""
)

$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_local_common.ps1"

$Root = Get-RepoRoot
Set-Location $Root
New-Item -ItemType Directory -Force -Path "logs","lr\work","lr\output" | Out-Null
$Log = "logs\lr_profit_fill_local.log"

if (-not $TargetDate) {
    $TargetDate = (Get-Date).AddDays(-1).ToString("yyyy-MM-dd")
}
if (-not $Xlsx) {
    $Xlsx = "lr\work\LR日报_$TargetDate.xlsx"
}
if (-not (Test-Path -LiteralPath $Xlsx)) {
    Write-Step "MISSING xlsx: $Xlsx"
    Write-LogLine $Log "missing filled xlsx: $Xlsx"
    exit 1
}

Write-Step "LR kanban export+push from existing xlsx=$Xlsx target=$TargetDate"
Write-LogLine $Log "start kanban-push-existing xlsx=$Xlsx target=$TargetDate"
try {
    $py = Ensure-Venv -Root $Root
} catch {
    Write-Step "venv fail: $_"
    Write-LogLine $Log "venv fail: $_"
    exit 1
}

# Prefer PowerShell COM path (works when Python ProgID fails with 无效的类字符串)
$env:LR_KANBAN_EXPORT = "ps1,com"

$code = Invoke-PythonLogged -PythonExe $py -Arguments @(
    "lr\run_daily.py",
    "--filled-xlsx", $Xlsx,
    "--target-date", $TargetDate
) -LogPath $Log
Write-LogLine $Log "exit=$code"
if ($code -eq 0) {
    Write-Step "SUCCESS kanban+push. See $Log"
} else {
    Write-Step "FAILED exit=$code. See $Log"
    if (Test-Path $Log) { Get-Content -Path $Log -Tail 80 -Encoding UTF8 | ForEach-Object { Write-Host $_ } }
    Write-Step "Also run: powershell -ExecutionPolicy Bypass -File scripts\diagnose_wps_com.ps1"
}
exit $code
