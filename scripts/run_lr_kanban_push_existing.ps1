# 仅用已填好的 LR 日报 xlsx：WPS/PowerShell STA 导出五城图 + 企微推送（跳过抓取填表）
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
    $Xlsx = Resolve-LrFilledXlsx -Root $Root -TargetDate $TargetDate
}
if (-not $Xlsx) {
    Write-Step "MISSING xlsx for $TargetDate (run fill first or pass -Xlsx)"
    Write-LogLine $Log "missing filled xlsx for target=$TargetDate"
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

$exportPs1 = Join-Path $PSScriptRoot "run_lr_kanban_export.ps1"
& powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File $exportPs1 -Xlsx $Xlsx -TargetDate $TargetDate
$code = $LASTEXITCODE
if ($code -ne 0) {
    Write-LogLine $Log "exit=$code (kanban export fail)"
    Write-Step "FAILED kanban export exit=$code"
    exit $code
}

$code = Invoke-PythonLogged -PythonExe $py -Arguments @(
    "lr\run_daily.py",
    "--filled-xlsx", $Xlsx,
    "--target-date", $TargetDate,
    "--push-only"
) -LogPath $Log
Write-LogLine $Log "exit=$code"
if ($code -eq 0) {
    Write-Step "SUCCESS kanban+push. See $Log"
} else {
    Write-Step "FAILED exit=$code. See $Log"
    if (Test-Path $Log) { Get-Content -Path $Log -Tail 80 -Encoding UTF8 | ForEach-Object { Write-Host $_ } }
    Write-Step "Also run: powershell -STA -ExecutionPolicy Bypass -File scripts\diagnose_wps_com.ps1"
}
exit $code
