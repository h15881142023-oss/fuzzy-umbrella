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
& $py "lr\scrape_live.py" --target-date $TargetDate *>> $Log
if ($LASTEXITCODE -ne 0) {
    Write-LogLine $Log "exit=$LASTEXITCODE (scrape fail)"
    Write-Step "FAILED scrape. See $Log"
    exit $LASTEXITCODE
}

Write-Step "Filling Excel, WPS kanban screenshots, WeCom push ..."
& $py "lr\run_daily.py" --scrape-json "data\lr_scrape\latest.json" --target-date $TargetDate *>> $Log
$code = $LASTEXITCODE
Write-LogLine $Log "exit=$code"
if ($code -eq 0) { Write-Step "SUCCESS. See $Log" } else { Write-Step "FAILED exit=$code. See $Log" }
exit $code
