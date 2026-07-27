# Export LR kanban PNGs in STA PowerShell (Windows).
# Keep this script ASCII-only to avoid GBK mojibake parser issues.
param(
    [Parameter(Mandatory = $true)][string]$Xlsx,
    [Parameter(Mandatory = $true)][string]$TargetDate,
    [string]$OutDir = "lr\output",
    [string]$Region = "川藏一区"
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
    $dt = [datetime]::ParseExact($TargetDate, "yyyy-MM-dd", $null)
} catch {
    Write-Step "Invalid TargetDate: $TargetDate"
    exit 1
}

$cities = @("仁寿县", "南溪", "叙永", "彭州市", "合江县")
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$outAbs = (Resolve-Path -LiteralPath $OutDir).Path
$xlsxAbs = (Resolve-Path -LiteralPath $Xlsx).Path
$logPath = Join-Path $outAbs "wps_export.log"
$cfgPath = Join-Path $outAbs "_export_kanban_cfg.json"

$cfg = @{
    xlsx   = $xlsxAbs
    outDir = $outAbs
    month  = [int]$dt.Month
    region = $Region
    cities = $cities
    sheet  = "看板-单城"
    range  = "B1:R37"
}
$cfg | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $cfgPath -Encoding UTF8

Write-Step ("Kanban export STA: xlsx={0} month={1}" -f $xlsxAbs, $dt.Month)
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

foreach ($city in $cities) {
    $safe = ($city -replace '[\\/:*?"<>|]', '_')
    $png = Join-Path $outAbs ("看板-单城_{0}_{1}.png" -f $safe, $dt.Month)
    if (-not (Test-Path -LiteralPath $png)) {
        Write-Step ("MISSING png after export: {0}" -f $png)
        if (Test-Path -LiteralPath $logPath) {
            Get-Content -LiteralPath $logPath -Tail 40 -Encoding UTF8 | ForEach-Object { Write-Host $_ }
        }
        exit 1
    }
}

Write-Step ("Kanban export OK ({0} pngs)" -f $cities.Count)
exit 0
