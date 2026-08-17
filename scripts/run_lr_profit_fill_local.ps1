# LR profit fill push: scrape -> fill template -> WPS kanban png -> WeCom. ASCII header.
# Default schedule: daily 23:30
param(
    [string]$TargetDate = ""
)

$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_local_common.ps1"

$Root = Get-RepoRoot
Set-Location $Root
New-Item -ItemType Directory -Force -Path "logs","data\lr_scrape","lr\work","lr\output" | Out-Null
$Log = "logs\lr_profit_fill_local.log"

if (-not $TargetDate) {
    $TargetDate = (Get-Date).AddDays(-1).ToString("yyyy-MM-dd")
}

Write-Step "LR PROFIT FILL start target=$TargetDate. Log: $Root\$Log"
Write-LogLine $Log "start profit-fill target=$TargetDate"
try {
    $null = Ensure-Venv -Root $Root
} catch {
    Write-Step "venv fail: $_"
    Write-LogLine $Log "venv fail: $_"
    Notify-LrWecomText -Root $Root -Message ("利润填写失败 target=$TargetDate venv: " + $_)
    exit 1
}
$py = [string](Join-Path $Root ".venv\Scripts\python.exe")
if (-not (Test-Path -LiteralPath $py)) {
    Write-Step "python missing: $py"
    Notify-LrWecomText -Root $Root -Message "利润填写失败：找不到 .venv python"
    exit 1
}

Write-Step "Scraping LR page for $TargetDate ..."
$code = Invoke-PythonLogged -PythonExe $py -Arguments @("lr\scrape_live.py", "--target-date", $TargetDate) -LogPath $Log
if ($code -ne 0) {
    Write-LogLine $Log "exit=$code (scrape fail)"
    Write-Step "FAILED scrape exit=$code. See $Log"
    Notify-LrWecomText -Root $Root -Message "利润填写失败 target=$TargetDate：抓取失败 exit=$code，见 logs\lr_profit_fill_local.log"
    exit $code
}

Write-Step "Fill template (fill-only). Large xlsx: often 1-5 min; progress only in log."
Write-Step "Watch: Get-Content $Log -Wait -Tail 30 -Encoding UTF8"
$code = Invoke-PythonLogged -PythonExe $py -Arguments @(
    "lr\run_daily.py",
    "--scrape-json", "data\lr_scrape\latest.json",
    "--target-date", $TargetDate,
    "--fill-only"
) -LogPath $Log
if ($code -ne 0) {
    Write-LogLine $Log "exit=$code (fill fail)"
    Write-Step "FAILED fill exit=$code. See $Log"
    if (Test-Path $Log) { Get-Content -Path $Log -Tail 40 -Encoding UTF8 | ForEach-Object { Write-Host $_ } }
    Notify-LrWecomText -Root $Root -Message "利润填写失败 target=$TargetDate：填表失败 exit=$code"
    exit $code
}
Write-Step "Fill template done."
$Xlsx = Resolve-LrFilledXlsx -Root $Root -TargetDate $TargetDate
if (-not $Xlsx) {
    Write-LogLine $Log "missing xlsx after fill for target=$TargetDate"
    Write-Step "MISSING filled xlsx for $TargetDate (see lr\work\last_filled.json)"
    Notify-LrWecomText -Root $Root -Message "利润填写失败 target=$TargetDate：填表后找不到 xlsx"
    exit 1
}
Write-Step "Filled xlsx: $Xlsx"

Write-Step "WPS kanban export (PowerShell STA COM) ..."
$exportPs1 = Join-Path $PSScriptRoot "run_lr_kanban_export.ps1"
$psExe = Get-WpsMatchedPowerShell
Write-Step ("kanban powershell=" + $psExe)
& $psExe -NoProfile -STA -ExecutionPolicy Bypass -File $exportPs1 -Xlsx $Xlsx -TargetDate $TargetDate
$code = $LASTEXITCODE
if ($code -ne 0) {
    Write-LogLine $Log "exit=$code (kanban export fail)"
    Write-Step "FAILED kanban export exit=$code. See lr\output\wps_export.log"
    if (Test-Path "lr\output\wps_export.log") {
        Get-Content "lr\output\wps_export.log" -Tail 50 -Encoding UTF8 | ForEach-Object { Write-Host $_ }
    }
    Notify-LrWecomText -Root $Root -Message "利润填写失败 target=$TargetDate：WPS看板导出失败(CLASSNOTREG/COM)。表已填好。见 lr\output\wps_export.log"
    exit $code
}

Write-Step "WeCom push (5 images + excel) ..."
$code = Invoke-PythonLogged -PythonExe $py -Arguments @(
    "lr\run_daily.py",
    "--filled-xlsx", $Xlsx,
    "--target-date", $TargetDate,
    "--push-only"
) -LogPath $Log
Write-LogLine $Log "exit=$code"
if ($code -eq 0) {
    Write-Step "SUCCESS profit-fill. See $Log"
} else {
    Write-Step "FAILED profit-fill exit=$code. See $Log"
    Notify-LrWecomText -Root $Root -Message "利润填写失败 target=$TargetDate：企微推送失败 exit=$code"
    if (Test-Path $Log) { Get-Content -Path $Log -Tail 60 -Encoding UTF8 | ForEach-Object { Write-Host $_ } }
}
exit $code
