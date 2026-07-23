# Local KPI/Todo weekly report (Windows)
$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_local_common.ps1"

$Root = Get-RepoRoot
Set-Location $Root
New-Item -ItemType Directory -Force -Path "logs","data\kpi_todo_scrape","kpi_todo\output" | Out-Null
$Log = "logs\kpi_todo_local.log"

Write-Step "KPI Todo start. Log: $Root\$Log"
Write-LogLine $Log "start"
try {
    $py = Ensure-Venv -Root $Root
} catch {
    Write-Step "venv fail: $_"
    Write-LogLine $Log "venv fail: $_"
    exit 1
}

Write-Step "Scraping admin page (may take 1-3 minutes) ..."
& $py "kpi_todo\scrape_live.py" *>> $Log
if ($LASTEXITCODE -ne 0) {
    Write-Step "Scrape failed, sending notify-only WeCom message ..."
    & $py "kpi_todo\run_biweekly.py" --notify-only --message "local scrape failed, see logs/kpi_todo_local.log" *>> $Log
    Write-LogLine $Log "exit=$LASTEXITCODE (scrape fail)"
    Write-Step "Done with error. See $Log"
    exit $LASTEXITCODE
}

Write-Step "Building image and pushing WeCom ..."
& $py "kpi_todo\run_biweekly.py" --scrape-json "data\kpi_todo_scrape\latest.json" *>> $Log
$code = $LASTEXITCODE
Write-LogLine $Log "exit=$code"
if ($code -eq 0) {
    Write-Step "SUCCESS. See $Log"
} else {
    Write-Step "FAILED exit=$code. See $Log"
}
exit $code
