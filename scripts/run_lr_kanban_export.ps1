# Export LR kanban PNGs in STA PowerShell. ASCII-only script body.
param(
    [Parameter(Mandatory = $true)][string]$Xlsx,
    [Parameter(Mandatory = $true)][string]$TargetDate,
    [string]$OutDir = "lr\output"
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_local_common.ps1"
$Root = Get-RepoRoot
Set-Location $Root

if (-not (Test-Path -LiteralPath $Xlsx)) {
    Write-Step "MISSING xlsx: $Xlsx"
    exit 1
}

try {
    $null = [datetime]::ParseExact($TargetDate, "yyyy-MM-dd", $null)
} catch {
    Write-Step "Invalid TargetDate: $TargetDate"
    exit 1
}

$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $py)) {
    Write-Step "MISSING venv python: $py"
    exit 1
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$outAbs = (Resolve-Path -LiteralPath $OutDir).Path
$cfgPath = Join-Path $outAbs "_export_kanban_cfg.json"
$logPath = Join-Path $outAbs "wps_export.log"

$xlsxAbs = (Resolve-Path -LiteralPath $Xlsx).Path
& $py "lr\write_kanban_export_cfg.py" "--xlsx" $xlsxAbs "--target-date" $TargetDate "--out-dir" $outAbs "--config" $cfgPath
if ($LASTEXITCODE -ne 0) {
    Write-Step "write_kanban_export_cfg failed"
    exit 1
}

Write-Step ("Kanban export STA: xlsx={0} date={1}" -f $xlsxAbs, $TargetDate)
$exportPs1 = Join-Path $PSScriptRoot "export_lr_kanban_wps.ps1"

try {
    & $exportPs1 -ConfigJson $cfgPath 2>&1 | Tee-Object -FilePath $logPath -Append | Out-Null
    $code = $LASTEXITCODE
    if ($null -eq $code) { $code = 0 }
    if ($code -ne 0) {
        Write-Step "export_lr_kanban_wps.ps1 failed"
        exit $code
    }
} catch {
    ($_ | Out-String) | Add-Content -LiteralPath $logPath -Encoding UTF8
    Write-Step ("Kanban export failed: {0}" -f $_.Exception.Message)
    exit 1
}

& $py "lr\verify_kanban_pngs.py" "--config" $cfgPath
if ($LASTEXITCODE -ne 0) {
    if (Test-Path -LiteralPath $logPath) {
        Get-Content -LiteralPath $logPath -Tail 40 -Encoding UTF8 | ForEach-Object { Write-Host $_ }
    }
    exit 1
}

Write-Step "Kanban export OK"
exit 0
