# 本机：LR 日报 / 日利润数据源端到端（Windows）
$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_local_common.ps1"

$Root = Get-RepoRoot
Set-Location $Root
New-Item -ItemType Directory -Force -Path "logs","data\lr_scrape","lr\work","lr\output" | Out-Null
$Log = "logs\lr_daily_local.log"

Write-LogLine $Log "start"
try {
    $py = Ensure-Venv -Root $Root
} catch {
    Write-LogLine $Log "venv fail: $_"
    exit 1
}

& $py "lr\scrape_live.py" *>> $Log
if ($LASTEXITCODE -ne 0) {
    Write-LogLine $Log "exit=$LASTEXITCODE (scrape fail)"
    exit $LASTEXITCODE
}

& $py "lr\run_daily.py" --scrape-json "data\lr_scrape\latest.json" *>> $Log
$code = $LASTEXITCODE
Write-LogLine $Log "exit=$code"
exit $code
