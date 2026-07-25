# Export kanban sheet PNGs via WPS/Excel COM (Windows).
# Prefer: python lr/export_kanban_com.py path (called from Python).
# This script accepts -ConfigJson to avoid Chinese args on the command line.
param(
    [string]$ConfigJson = "",
    [string]$XlsxPath = "",
    [string]$OutDir = "",
    [int]$Month = 0,
    [string]$Region = "",
    [string]$Cities = "",
    [string]$SheetName = "看板-单城",
    [string]$RangeAddress = "B1:R37"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

if ($ConfigJson -and (Test-Path $ConfigJson)) {
    $cfg = Get-Content -LiteralPath $ConfigJson -Encoding UTF8 -Raw | ConvertFrom-Json
    $XlsxPath = [string]$cfg.xlsx
    $OutDir = [string]$cfg.outDir
    $Month = [int]$cfg.month
    $Region = [string]$cfg.region
    $Cities = [string]($cfg.cities -join ",")
    if ($cfg.sheet) { $SheetName = [string]$cfg.sheet }
    if ($cfg.range) { $RangeAddress = [string]$cfg.range }
}

if (-not $XlsxPath -or -not $OutDir -or $Month -le 0) {
    throw "Missing XlsxPath/OutDir/Month (or ConfigJson)"
}

function Get-ClsidForProgId([string]$ProgId) {
    $paths = @(
        "Registry::HKEY_CLASSES_ROOT\$ProgId\CLSID",
        "Registry::HKEY_CLASSES_ROOT\WOW6432Node\$ProgId\CLSID",
        "Registry::HKEY_LOCAL_MACHINE\Software\Classes\$ProgId\CLSID",
        "Registry::HKEY_LOCAL_MACHINE\Software\Classes\WOW6432Node\$ProgId\CLSID"
    )
    foreach ($p in $paths) {
        try {
            $v = (Get-ItemProperty -LiteralPath $p -ErrorAction Stop).'(default)'
            if ($v -and $v -match '^\{.+\}$') { return [string]$v }
        } catch {}
    }
    return $null
}

function Get-OfficeApp {
    $errors = @()
    $progIds = @(
        "KET.Application", "Ket.Application", "KET.Application.9", "Ket.Application.9",
        "Excel.Application", "Excel.Application.12", "Excel.Application.11",
        "et.Application", "et.Application.9"
    )
    # Also pick up whatever is registered
    try {
        Get-ChildItem Registry::HKEY_CLASSES_ROOT -ErrorAction SilentlyContinue |
            Where-Object {
                $_.PSChildName -like "Ket.Application*" -or
                $_.PSChildName -like "KET.Application*" -or
                $_.PSChildName -like "et.Application*" -or
                $_.PSChildName -like "Excel.Application*"
            } | ForEach-Object { $progIds += $_.PSChildName }
    } catch {}
    $progIds = $progIds | Select-Object -Unique

    foreach ($progId in $progIds) {
        try {
            $app = New-Object -ComObject $progId
            if ($app) {
                Write-Output "office_progid=$progId"
                return @{ App = $app; ProgId = $progId }
            }
        } catch {
            $errors += ("{0}: {1}" -f $progId, $_.Exception.Message)
        }
        $clsid = Get-ClsidForProgId $progId
        if ($clsid) {
            try {
                $app = [Activator]::CreateInstance([Type]::GetTypeFromCLSID($clsid))
                if ($app) {
                    Write-Output ("office_progid={0} clsid={1}" -f $progId, $clsid)
                    return @{ App = $app; ProgId = "$progId/$clsid" }
                }
            } catch {
                $errors += ("{0}/{1}: {2}" -f $progId, $clsid, $_.Exception.Message)
            }
        }
    }
    throw ("WPS/Excel COM not found. " + ($errors -join " | "))
}

function Export-RangePng($Worksheet, [string]$Address, [string]$PngPath) {
    $range = $Worksheet.Range($Address)
    if (Test-Path -LiteralPath $PngPath) { Remove-Item -LiteralPath $PngPath -Force }

    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $range.CopyPicture(1, 2) | Out-Null
    Start-Sleep -Milliseconds 400
    if (-not [System.Windows.Forms.Clipboard]::ContainsImage()) {
        throw "Clipboard has no image after CopyPicture"
    }
    $img = [System.Windows.Forms.Clipboard]::GetImage()
    $img.Save($PngPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $img.Dispose()
    if (-not (Test-Path -LiteralPath $PngPath)) {
        throw "PNG export failed: $PngPath"
    }
}

if (-not (Test-Path -LiteralPath $XlsxPath)) { throw "Xlsx not found: $XlsxPath" }
$xlsx = (Resolve-Path -LiteralPath $XlsxPath).Path
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$outAbs = (Resolve-Path -LiteralPath $OutDir).Path
$cityList = @($Cities.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
Write-Output ("xlsx=$xlsx out=$outAbs month=$Month cities=$($cityList -join '|')")

$office = Get-OfficeApp
$app = $office.App
try { $app.Visible = $true } catch {}
try { $app.DisplayAlerts = $false } catch {}

try {
    $wb = $app.Workbooks.Open($xlsx, 0, $false)
    $ws = $wb.Worksheets.Item($SheetName)
    $ws.Activate() | Out-Null
    $ws.Range("C2").Value2 = $Month
    $ws.Range("E3").Value2 = $Region
    try { $app.CalculateFullRebuild() } catch {
        try { $app.CalculateFull() } catch { try { $wb.Application.Calculate() } catch {} }
    }

    foreach ($city in $cityList) {
        $ws.Range("C3").Value2 = $city
        try { $app.CalculateFull() } catch { try { $wb.Application.Calculate() } catch {} }
        Start-Sleep -Milliseconds 500
        $safe = ($city -replace '[\\/:*?"<>|]', '_')
        $png = Join-Path $outAbs ("看板-单城_{0}_{1}.png" -f $safe, $Month)
        Export-RangePng -Worksheet $ws -Address $RangeAddress -PngPath $png
        Write-Output "exported=$png"
    }
    $wb.Save()
    $wb.Close($true)
    Write-Output ("ok count={0} prog={1}" -f $cityList.Count, $office.ProgId)
} finally {
    try { $app.Quit() } catch {}
    try { [System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null } catch {}
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
