# LR datasource push (NOT profit-fill). Scrape -> raw Excel -> WeCom. ASCII-only header.
# Default schedule: daily 23:15
param(
    [string]$TargetDate = ""
)

$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_local_common.ps1"

$Root = Get-RepoRoot
Set-Location $Root
New-Item -ItemType Directory -Force -Path "logs","data\lr_scrape","lr\work\datasource" | Out-Null
$Log = "logs\lr_datasource_local.log"

if (-not $TargetDate) {
    $TargetDate = (Get-Date).AddDays(-1).ToString("yyyy-MM-dd")
}

Write-Step "LR DATASOURCE push start target=$TargetDate. Log: $Root\$Log"
Write-LogLine $Log "start datasource target=$TargetDate"
try {
    $py = Ensure-Venv -Root $Root
} catch {
    Write-Step "venv fail: $_"
    Write-LogLine $Log "venv fail: $_"
    exit 1
}

Write-Step "Scraping LR page for $TargetDate ..."
$code = Invoke-PythonLogged -PythonExe $py -Arguments @("lr\scrape_live.py", "--target-date", $TargetDate) -LogPath $Log
if ($code -ne 0) {
    Write-LogLine $Log "exit=$code (scrape fail)"
    Write-Step "FAILED scrape exit=$code. See $Log"
    exit $code
}

Write-Step "Export raw datasource Excel and push WeCom ..."
$code = Invoke-PythonLogged -PythonExe $py -Arguments @(
    "lr\run_datasource_push.py",
    "--scrape-json", "data\lr_scrape\latest.json",
    "--target-date", $TargetDate
) -LogPath $Log
Write-LogLine $Log "exit=$code"
if ($code -eq 0) {
    Write-Step "SUCCESS datasource. See $Log"
} else {
    Write-Step "FAILED datasource exit=$code. See $Log"
    if (Test-Path $Log) { Get-Content -Path $Log -Tail 60 -Encoding UTF8 | ForEach-Object { Write-Host $_ } }
}
exit $code
