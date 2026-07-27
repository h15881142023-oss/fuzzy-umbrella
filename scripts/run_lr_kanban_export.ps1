# 直接调用 WPS/Excel COM 导出五城看板 PNG（必须在 STA 线程，供 profit-fill 调用）
# 用法：
#   powershell -STA -ExecutionPolicy Bypass -File scripts\run_lr_kanban_export.ps1 -Xlsx lr\work\LR日报_2026-07-25.xlsx -TargetDate 2026-07-25
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

Write-Step "Kanban export STA: xlsx=$xlsxAbs month=$($dt.Month)"
$exportPs1 = Join-Path $PSScriptRoot "export_lr_kanban_wps.ps1"
try {
    & $exportPs1 -ConfigJson $cfgPath *>&1 | Tee-Object -FilePath $logPath -Append
    $code = $LASTEXITCODE
    if ($null -eq $code -or $code -eq 0) { $code = 0 }
} catch {
    $_ | Out-String | Add-Content -LiteralPath $logPath -Encoding UTF8
    Write-Step "Kanban export failed: $_"
    exit 1
}

foreach ($city in $cities) {
    $safe = ($city -replace '[\\/:*?"<>|]', '_')
    $png = Join-Path $outAbs ("看板-单城_{0}_{1}.png" -f $safe, $dt.Month)
    if (-not (Test-Path -LiteralPath $png)) {
        Write-Step "MISSING png after export: $png"
        if (Test-Path $logPath) { Get-Content $logPath -Tail 40 -Encoding UTF8 | ForEach-Object { Write-Host $_ } }
        exit 1
    }
}
Write-Step "Kanban export OK ($($cities.Count) pngs)"
exit 0
