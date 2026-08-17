# Export kanban sheet PNGs via WPS/Excel COM (Windows).
# Must run in STA apartment for clipboard (use: powershell -STA -File ...)
param(
    [string]$ConfigJson = "",
    [string]$XlsxPath = "",
    [string]$OutDir = "",
    [int]$Month = 0,
    [string]$Region = "",
    [string]$Cities = "",
    [string]$SheetName = "",
    [string]$RangeAddress = "B1:R37"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$script:pngPrefix = "kanban"

if ($ConfigJson -and (Test-Path $ConfigJson)) {
    $cfg = Get-Content -LiteralPath $ConfigJson -Encoding UTF8 -Raw | ConvertFrom-Json
    $XlsxPath = [string]$cfg.xlsx
    $OutDir = [string]$cfg.outDir
    $Month = [int]$cfg.month
    $Region = [string]$cfg.region
    $Cities = [string]($cfg.cities -join ",")
    if ($cfg.sheet) { $SheetName = [string]$cfg.sheet }
    if ($cfg.range) { $RangeAddress = [string]$cfg.range }
    if ($cfg.pngPrefix) { $script:pngPrefix = [string]$cfg.pngPrefix } else { $script:pngPrefix = "kanban" }
}

if (-not $XlsxPath -or -not $OutDir -or $Month -le 0) {
    throw "Missing XlsxPath/OutDir/Month (or ConfigJson)"
}
if (-not $SheetName) {
    throw "Missing sheet name in ConfigJson"
}
if (-not $script:pngPrefix) { $script:pngPrefix = "kanban" }

function Find-EtExe {
    $patterns = @(
        "$env:LOCALAPPDATA\Kingsoft\WPS Office\*\office6\et.exe",
        "$env:ProgramFiles\Kingsoft\WPS Office\*\office6\et.exe",
        "${env:ProgramFiles(x86)}\Kingsoft\WPS Office\*\office6\et.exe"
    )
    foreach ($p in $patterns) {
        $hit = Get-Item $p -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
        if ($hit) { return $hit.FullName }
    }
    return $null
}

function Get-PeBitsLocal {
    param([string]$ExePath)
    try {
        $fs = [IO.File]::OpenRead($ExePath)
        try {
            $br = New-Object IO.BinaryReader $fs
            if ($br.ReadUInt16() -ne 0x5A4D) { return $null }
            $fs.Seek(0x3C, [IO.SeekOrigin]::Begin) | Out-Null
            $pe = $br.ReadUInt32()
            $fs.Seek($pe, [IO.SeekOrigin]::Begin) | Out-Null
            if ($br.ReadUInt32() -ne 0x4550) { return $null }
            $machine = $br.ReadUInt16()
            if ($machine -eq 0x14C) { return 32 }
            if ($machine -eq 0x8664) { return 64 }
            return $null
        } finally { $fs.Close() }
    } catch { return $null }
}

# 32-bit WPS cannot be created from 64-bit PowerShell (CLASSNOTREG / empty CLSID).
if (-not $env:LR_WPS_COM_RELAUNCHED) {
    $etBitsProbe = Find-EtExe
    $need32 = $false
    if ($etBitsProbe) {
        $pb = Get-PeBitsLocal -ExePath $etBitsProbe
        Write-Host ("et=$etBitsProbe et_bits=$pb ps_bits=" + ([IntPtr]::Size * 8))
        if ($pb -eq 32) { $need32 = $true }
    } else {
        Write-Host ("et=missing ps_bits=" + ([IntPtr]::Size * 8))
    }
    if ($need32 -and [IntPtr]::Size -eq 8) {
        $wow = Join-Path $env:SystemRoot "SysWOW64\WindowsPowerShell\v1.0\powershell.exe"
        if (Test-Path -LiteralPath $wow) {
            Write-Host "relaunch 32-bit powershell for WPS COM"
            $env:LR_WPS_COM_RELAUNCHED = "1"
            $arg = "-NoProfile -STA -ExecutionPolicy Bypass -File `"$PSCommandPath`""
            if ($ConfigJson) { $arg += " -ConfigJson `"$ConfigJson`"" }
            elseif ($XlsxPath) { $arg += " -XlsxPath `"$XlsxPath`" -OutDir `"$OutDir`" -Month $Month -Region `"$Region`" -Cities `"$Cities`" -SheetName `"$SheetName`" -RangeAddress `"$RangeAddress`"" }
            cmd.exe /c "`"$wow`" $arg"
            exit $LASTEXITCODE
        }
    }
}

function Ensure-WpsRegistered {
    $et = Find-EtExe
    if (-not $et) {
        Write-Host "et.exe not found under WPS Office paths"
        return $null
    }
    Write-Host "regserver $et"
    try {
        # Stop leftover ET that can block COM re-register (best-effort)
        Get-Process -Name "et","wps","wpp" -ErrorAction SilentlyContinue |
            Where-Object { $_.Path -and $_.Path -like "*Kingsoft*" } |
            ForEach-Object {
                try { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue } catch {}
            }
        Start-Sleep -Seconds 1
    } catch {}
    try {
        $p = Start-Process -FilePath $et -ArgumentList "/regserver" -Wait -PassThru -WindowStyle Hidden
        Write-Host ("regserver exit=" + $p.ExitCode)
    } catch {
        Write-Host ("regserver error: " + $_.Exception.Message)
    }
    Start-Sleep -Seconds 2
    return $et
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

    for ($attempt = 1; $attempt -le 4; $attempt++) {
        if ($attempt -gt 1) {
            Write-Host ("COM create retry {0}/4 after regserver..." -f $attempt)
            Ensure-WpsRegistered | Out-Null
            Start-Sleep -Seconds (2 * $attempt)
        }
        foreach ($progId in $progIds) {
            try {
                $app = New-Object -ComObject $progId
                if ($app) {
                    Write-Host "office_progid=$progId"
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
                        Write-Host "office_progid=${progId} clsid=$clsid"
                        return @{ App = $app; ProgId = "$progId/$clsid" }
                    }
                } catch {
                    $errors += ("{0}/{1}: {2}" -f $progId, $clsid, $_.Exception.Message)
                }
            }
        }
    }
    throw ("WPS/Excel COM not found. " + ($errors -join " | "))
}

function Clear-ClipboardSafe {
    Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue
    for ($i = 0; $i -lt 12; $i++) {
        try {
            [System.Windows.Forms.Clipboard]::Clear()
            return
        } catch {
            Start-Sleep -Milliseconds 250
        }
    }
}

function Export-RangePng($Worksheet, [string]$Address, [string]$PngPath) {
    if (Test-Path -LiteralPath $PngPath) { Remove-Item -LiteralPath $PngPath -Force }

    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing

    $app = $Worksheet.Application
    try { $app.Visible = $true } catch {}
    try { $app.WindowState = 1 } catch {}
    try { $Worksheet.Activate() | Out-Null } catch {}
    try { $app.ActiveWindow.Activate() | Out-Null } catch {}

    $range = $Worksheet.Range($Address)
    try { $range.Select() | Out-Null } catch {}

    $pairs = @(
        @(1, 2),
        @(1, -4147),
        @(2, 2)
    )

    $lastErr = $null
    for ($try = 1; $try -le 10; $try++) {
        $fmt = $pairs[($try - 1) % $pairs.Count]
        try {
            Clear-ClipboardSafe
            try { $app.CutCopyMode = $false } catch {}
            $range.CopyPicture($fmt[0], $fmt[1]) | Out-Null
            Start-Sleep -Milliseconds (450 + $try * 100)
            if (-not [System.Windows.Forms.Clipboard]::ContainsImage()) {
                throw "Clipboard has no image after CopyPicture (try $try fmt=$($fmt -join ','))"
            }
            $img = [System.Windows.Forms.Clipboard]::GetImage()
            if (-not $img) { throw "GetImage returned null (try $try)" }
            $img.Save($PngPath, [System.Drawing.Imaging.ImageFormat]::Png)
            $img.Dispose()
            if (-not (Test-Path -LiteralPath $PngPath)) {
                throw "PNG export failed: $PngPath"
            }
            return
        } catch {
            $lastErr = $_
            Start-Sleep -Milliseconds 400
        }
    }
    throw $lastErr
}

if (-not (Test-Path -LiteralPath $XlsxPath)) { throw "Xlsx not found: $XlsxPath" }
$xlsx = (Resolve-Path -LiteralPath $XlsxPath).Path
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$outAbs = (Resolve-Path -LiteralPath $OutDir).Path
$cityList = @($Cities.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
Write-Host "xlsx=$xlsx out=$outAbs month=$Month cities=$($cityList -join '|')"

Ensure-WpsRegistered
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
        Start-Sleep -Milliseconds 600
        $safe = ($city -replace '[\\/:*?"<>|]', '_')
        $png = Join-Path $outAbs ("{0}_{1}_{2}.png" -f $script:pngPrefix, $safe, $Month)
        Export-RangePng -Worksheet $ws -Address $RangeAddress -PngPath $png
        Write-Host "exported=$png"
    }
    $wb.Save()
    $wb.Close($true)
    Write-Host "ok count=$($cityList.Count) prog=$($office.ProgId)"
} finally {
    try { $app.Quit() } catch {}
    try { [System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null } catch {}
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
