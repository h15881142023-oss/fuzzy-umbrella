# Local LR daily + profit datasource (Windows)
param(
    [string]$TargetDate = ""
)

$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_local_common.ps1"

$Root = Get-RepoRoot
Set-Location $Root
New-Item -ItemType Directory -Force -Path "logs","data\lr_scrape","lr\work","lr\output" | Out-Null
$Log = "logs\lr_daily_local.log"

if (-not $TargetDate) {
    $TargetDate = (Get-Date).AddDays(-1).ToString("yyyy-MM-dd")
}

Write-Step "LR daily start target=$TargetDate. Log: $Root\$Log"
Write-LogLine $Log "start target=$TargetDate"
try {
    $py = Ensure-Venv -Root $Root
} catch {
    Write-Step "venv fail: $_"
    Write-LogLine $Log "venv fail: $_"
    exit 1
}

Write-Step "Scraping LR page for $TargetDate (may take 1-3 minutes) ..."
$code = Invoke-PythonLogged -PythonExe $py -Arguments @("lr\scrape_live.py", "--target-date", $TargetDate) -LogPath $Log
if ($code -ne 0) {
    Write-LogLine $Log "exit=$code (scrape fail)"
    Write-Step "FAILED scrape exit=$code. See $Log"
    exit $code
}

Write-Step "Filling Excel, WPS kanban screenshots, WeCom push ..."
# 若已有抓取结果，可跳过抓取只跑后半段：
#   .\.venv\Scripts\python.exe lr\run_daily.py --scrape-json data\lr_scrape\latest.json --target-date 2026-07-22
$code = Invoke-PythonLogged -PythonExe $py -Arguments @(
    "lr\run_daily.py",
    "--scrape-json", "data\lr_scrape\latest.json",
    "--target-date", $TargetDate
) -LogPath $Log
Write-LogLine $Log "exit=$code"
if ($code -eq 0) {
    Write-Step "SUCCESS. See $Log"
} else {
    Write-Step "FAILED exit=$code. See $Log (tail below)"
    if (Test-Path $Log) {
        Get-Content -Path $Log -Tail 60 -Encoding UTF8 | ForEach-Object { Write-Host $_ }
    }
    $wpsLog = Join-Path $Root "lr\output\wps_export.log"
    if (Test-Path $wpsLog) {
        Write-Step "---- lr/output/wps_export.log ----"
        Get-Content -Path $wpsLog -Tail 40 -Encoding UTF8 | ForEach-Object { Write-Host $_ }
    }
}
exit $code
