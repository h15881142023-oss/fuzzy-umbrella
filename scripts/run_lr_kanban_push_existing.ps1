# Push filled LR workbook: STA kanban export + WeCom (5 png + xlsx). ASCII-only.
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

Write-Step "LR kanban export+push xlsx=$Xlsx target=$TargetDate"
Write-LogLine $Log "start kanban-push-existing xlsx=$Xlsx target=$TargetDate"
try {
    $null = Ensure-Venv -Root $Root
} catch {
    Write-Step "venv fail: $_"
    Write-LogLine $Log "venv fail: $_"
    exit 1
}
$py = [string](Join-Path $Root ".venv\Scripts\python.exe")

$exportPs1 = Join-Path $PSScriptRoot "run_lr_kanban_export.ps1"
$psExe = Get-WpsMatchedPowerShell
Write-Step ("kanban powershell=" + $psExe)
& $psExe -NoProfile -STA -ExecutionPolicy Bypass -File $exportPs1 -Xlsx $Xlsx -TargetDate $TargetDate
$code = $LASTEXITCODE
if ($code -ne 0) {
    Write-LogLine $Log "exit=$code (kanban export fail)"
    Write-Step "FAILED kanban export exit=$code"
    if (Test-Path "lr\output\wps_export.log") {
        Get-Content "lr\output\wps_export.log" -Tail 50 -Encoding UTF8 | ForEach-Object { Write-Host $_ }
    }
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
}
exit $code
