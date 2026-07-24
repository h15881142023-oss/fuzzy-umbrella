# Export 「看板-单城」PNG for each city via WPS / Excel COM (Windows only).
# Usage:
#   powershell -File scripts\export_lr_kanban_wps.ps1 -XlsxPath "lr\work\LR日报_2026-07-22.xlsx" -OutDir "lr\output" -Month 7 -Cities "仁寿县,南溪,叙永,彭州市,合江县"
param(
    [Parameter(Mandatory = $true)][string]$XlsxPath,
    [Parameter(Mandatory = $true)][string]$OutDir,
    [Parameter(Mandatory = $true)][int]$Month,
    [string]$Region = "川藏一区",
    [string]$Cities = "仁寿县,南溪,叙永,彭州市,合江县",
    [string]$SheetName = "看板-单城",
    [string]$RangeAddress = "B1:R37"
)

$ErrorActionPreference = "Stop"

function Get-OfficeApp {
    foreach ($progId in @("Ket.Application", "et.Application", "Excel.Application")) {
        try {
            $app = New-Object -ComObject $progId
            if ($app) {
                return @{ App = $app; ProgId = $progId }
            }
        } catch {}
    }
    throw "WPS/Excel COM not found. Install WPS and retry."
}

function Export-RangePng($Worksheet, [string]$Address, [string]$PngPath) {
    $range = $Worksheet.Range($Address)
    # xlScreen=1, xlBitmap=2
    $range.CopyPicture(1, 2) | Out-Null
    $width = [math]::Max([int]$range.Width, 800)
    $height = [math]::Max([int]$range.Height, 400)
    $chartObj = $Worksheet.ChartObjects().Add(0, 0, $width, $height)
    $chart = $chartObj.Chart
    $chart.Paste() | Out-Null
    if (Test-Path $PngPath) { Remove-Item -Force $PngPath }
    $chart.Export($PngPath, "PNG") | Out-Null
    $chartObj.Delete() | Out-Null
    if (-not (Test-Path $PngPath)) {
        throw "PNG export failed: $PngPath"
    }
}

$xlsx = (Resolve-Path $XlsxPath).Path
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$outAbs = (Resolve-Path $OutDir).Path
$cityList = @($Cities.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ })

$office = Get-OfficeApp
$app = $office.App
$app.Visible = $false
$app.DisplayAlerts = $false
try {
    # WPS/Excel: UpdateLinks=0, ReadOnly=false
    $wb = $app.Workbooks.Open($xlsx, 0, $false)
    $ws = $wb.Worksheets.Item($SheetName)
    $ws.Activate() | Out-Null
    $ws.Range("C2").Value2 = $Month
    $ws.Range("E3").Value2 = $Region

    try { $app.CalculateFullRebuild() } catch { try { $app.CalculateFull() } catch { $wb.Application.Calculate() } }

    $manifest = @()
    foreach ($city in $cityList) {
        $ws.Range("C3").Value2 = $city
        try { $app.CalculateFull() } catch { $wb.Application.Calculate() }
        Start-Sleep -Milliseconds 400
        $safe = ($city -replace '[\\/:*?"<>|]', '_')
        $png = Join-Path $outAbs ("看板-单城_{0}_{1}.png" -f $safe, $Month)
        Export-RangePng -Worksheet $ws -Address $RangeAddress -PngPath $png
        $manifest += $png
        Write-Output "exported=$png"
    }

    # Keep last city on sheet; save recalculated workbook
    $wb.Save()
    $wb.Close($true)
    Write-Output ("ok count={0} prog={1}" -f $manifest.Count, $office.ProgId)
} finally {
    try { $app.Quit() } catch {}
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
