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
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

function Get-OfficeApp {
    $errors = @()
    foreach ($progId in @("Ket.Application", "et.Application", "Kwps.Application", "Excel.Application")) {
        try {
            $app = New-Object -ComObject $progId
            if ($app) {
                Write-Output "office_progid=$progId"
                return @{ App = $app; ProgId = $progId }
            }
        } catch {
            $errors += ("{0}: {1}" -f $progId, $_.Exception.Message)
        }
    }
    throw ("WPS/Excel COM not found. Tried: " + ($errors -join " | "))
}

function Export-RangePng($Worksheet, [string]$Address, [string]$PngPath) {
    $range = $Worksheet.Range($Address)
    if (Test-Path $PngPath) { Remove-Item -Force $PngPath }

    # Method 1: ChartObjects.Export (Excel / some WPS)
    try {
        $range.CopyPicture(1, 2) | Out-Null  # xlScreen, xlBitmap
        Start-Sleep -Milliseconds 200
        $width = [math]::Max([int]$range.Width, 800)
        $height = [math]::Max([int]$range.Height, 400)
        $chartObj = $Worksheet.ChartObjects().Add(0, 0, $width, $height)
        $chart = $chartObj.Chart
        $chart.Paste() | Out-Null
        $chart.Export($PngPath, "PNG") | Out-Null
        $chartObj.Delete() | Out-Null
        if (Test-Path $PngPath) { return }
    } catch {
        Write-Output ("chart_export_warn={0}" -f $_.Exception.Message)
        try { $Worksheet.ChartObjects() | ForEach-Object { $_.Delete() } } catch {}
    }

    # Method 2: Clipboard bitmap via System.Drawing
    try {
        Add-Type -AssemblyName System.Windows.Forms
        Add-Type -AssemblyName System.Drawing
        $range.CopyPicture(1, 2) | Out-Null
        Start-Sleep -Milliseconds 300
        if (-not [System.Windows.Forms.Clipboard]::ContainsImage()) {
            throw "Clipboard has no image after CopyPicture"
        }
        $img = [System.Windows.Forms.Clipboard]::GetImage()
        $img.Save($PngPath, [System.Drawing.Imaging.ImageFormat]::Png)
        $img.Dispose()
        if (Test-Path $PngPath) { return }
    } catch {
        Write-Output ("clipboard_export_warn={0}" -f $_.Exception.Message)
    }

    throw "PNG export failed: $PngPath"
}

if (-not (Test-Path $XlsxPath)) {
    throw "Xlsx not found: $XlsxPath"
}
$xlsx = (Resolve-Path $XlsxPath).Path
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$outAbs = (Resolve-Path $OutDir).Path
$cityList = @($Cities.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
Write-Output ("xlsx=$xlsx out=$outAbs cities=$($cityList -join '|')")

$office = Get-OfficeApp
$app = $office.App
# WPS CopyPicture 在隐藏窗口上常失败，短暂可见更稳
try { $app.Visible = $true } catch {}
try { $app.DisplayAlerts = $false } catch {}
try { $app.ScreenUpdating = $true } catch {}

try {
    $wb = $app.Workbooks.Open($xlsx, 0, $false)
    $ws = $null
    try {
        $ws = $wb.Worksheets.Item($SheetName)
    } catch {
        throw ("Sheet not found: {0}; sheets={1}" -f $SheetName, (($wb.Worksheets | ForEach-Object { $_.Name }) -join ","))
    }
    $ws.Activate() | Out-Null
    $ws.Range("C2").Value2 = $Month
    $ws.Range("E3").Value2 = $Region

    try { $app.CalculateFullRebuild() } catch {
        try { $app.CalculateFull() } catch {
            try { $wb.Application.Calculate() } catch {}
        }
    }

    $manifest = @()
    foreach ($city in $cityList) {
        $ws.Range("C3").Value2 = $city
        try { $app.CalculateFull() } catch {
            try { $wb.Application.Calculate() } catch {}
        }
        Start-Sleep -Milliseconds 500
        $safe = ($city -replace '[\\/:*?"<>|]', '_')
        $png = Join-Path $outAbs ("看板-单城_{0}_{1}.png" -f $safe, $Month)
        Export-RangePng -Worksheet $ws -Address $RangeAddress -PngPath $png
        $manifest += $png
        Write-Output "exported=$png"
    }

    $wb.Save()
    $wb.Close($true)
    Write-Output ("ok count={0} prog={1}" -f $manifest.Count, $office.ProgId)
} finally {
    try { $app.Quit() } catch {}
    try {
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null
    } catch {}
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
