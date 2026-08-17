# Export LR kanban PNGs in STA PowerShell. ASCII-only script body.
# CONTRACT: Python/openpyxl writes C2/C3/E3; WPS only screenshots.
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
$cityCfgPath = Join-Path $outAbs "_export_kanban_city.json"
$logPath = Join-Path $outAbs "wps_export.log"

$xlsxAbs = (Resolve-Path -LiteralPath $Xlsx).Path
& $py "lr\write_kanban_export_cfg.py" "--xlsx" $xlsxAbs "--target-date" $TargetDate "--out-dir" $outAbs "--config" $cfgPath
if ($LASTEXITCODE -ne 0) {
    Write-Step "write_kanban_export_cfg failed"
    exit 1
}

$fullCfg = Get-Content -LiteralPath $cfgPath -Encoding UTF8 -Raw | ConvertFrom-Json
$cityCount = @($fullCfg.cities).Count
if ($cityCount -le 0) {
    Write-Step "no cities in export cfg"
    exit 1
}

Write-Step ("Kanban export STA: xlsx={0} date={1} cities={2}" -f $xlsxAbs, $TargetDate, $cityCount)
$exportPs1 = Join-Path $PSScriptRoot "export_lr_kanban_wps.ps1"
$psExe = Get-WpsMatchedPowerShell
Write-Step ("export powershell=" + $psExe)

function Invoke-WpsCityExport {
    param([string]$CityCfg, [int]$Attempt)
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $output = & $psExe -NoProfile -STA -ExecutionPolicy Bypass -File $exportPs1 -ConfigJson $CityCfg 2>&1
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prevEap
    if ($output) {
        $output | ForEach-Object { "$_" } | Tee-Object -FilePath $logPath -Append | ForEach-Object { Write-Host $_ }
    }
    if ($null -eq $code) { $code = 0 }
    return $code
}

for ($idx = 0; $idx -lt $cityCount; $idx++) {
    Write-Step ("prepare+export city {0}/{1}" -f ($idx + 1), $cityCount)
    $prep = @("lr\prepare_kanban_city.py", "--config", $cfgPath, "--index", "$idx")
    if ($idx -gt 0) { $prep += "--skip-register" }
    & $py @prep
    if ($LASTEXITCODE -ne 0) {
        Write-Step "prepare_kanban_city failed index=$idx"
        exit 1
    }
    if (-not (Test-Path -LiteralPath $cityCfgPath)) {
        Write-Step "MISSING city cfg"
        exit 1
    }

    $okCity = $false
    $lastErr = $null
    for ($i = 1; $i -le 3; $i++) {
        Write-Step ("export city {0} attempt {1}/3" -f ($idx + 1), $i)
        try {
            $code = Invoke-WpsCityExport -CityCfg $cityCfgPath -Attempt $i
            if ($code -eq 0) {
                $okCity = $true
                break
            }
            $lastErr = "export_lr_kanban_wps.ps1 exit=$code"
            Write-Step $lastErr
            Start-Sleep -Seconds (3 * $i)
        } catch {
            $lastErr = $_.Exception.Message
            ($_ | Out-String) | Add-Content -LiteralPath $logPath -Encoding UTF8
            Write-Step ("Kanban export failed attempt {0}: {1}" -f $i, $lastErr)
            Start-Sleep -Seconds (3 * $i)
        }
    }
    if (-not $okCity) {
        Write-Step ("Kanban export failed after retries: {0}" -f $lastErr)
        if (Test-Path -LiteralPath $logPath) {
            Get-Content -LiteralPath $logPath -Tail 40 -Encoding UTF8 | ForEach-Object { Write-Host $_ }
        }
        exit 1
    }
    Start-Sleep -Seconds 2
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
