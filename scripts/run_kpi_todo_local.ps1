# Local KPI/Todo weekly report (Windows)
$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_local_common.ps1"

$Root = Get-RepoRoot
Set-Location $Root
New-Item -ItemType Directory -Force -Path "logs","data\kpi_todo_scrape","kpi_todo\output" | Out-Null
$Log = "logs\kpi_todo_local.log"

Write-LogLine $Log "start"
try {
    $py = Ensure-Venv -Root $Root
} catch {
    Write-LogLine $Log "venv fail: $_"
    exit 1
}

& $py "kpi_todo\scrape_live.py" *>> $Log
if ($LASTEXITCODE -ne 0) {
    & $py "kpi_todo\run_biweekly.py" --notify-only --message "local scrape failed, see logs/kpi_todo_local.log" *>> $Log
    Write-LogLine $Log "exit=$LASTEXITCODE (scrape fail)"
    exit $LASTEXITCODE
}

& $py "kpi_todo\run_biweekly.py" --scrape-json "data\kpi_todo_scrape\latest.json" *>> $Log
$code = $LASTEXITCODE
Write-LogLine $Log "exit=$code"
exit $code
