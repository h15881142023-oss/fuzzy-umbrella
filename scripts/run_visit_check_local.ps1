# Local visit-check daily (Windows)
$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_local_common.ps1"

$Root = Get-RepoRoot
Set-Location $Root
New-Item -ItemType Directory -Force -Path "logs","data\visit_exports" | Out-Null
$Log = "logs\visit_check_local.log"

Write-Step "Visit check start. Log: $Root\$Log"
Write-LogLine $Log "start"
try {
    $py = Ensure-Venv -Root $Root
} catch {
    Write-Step "venv fail: $_"
    Write-LogLine $Log "venv fail: $_"
    exit 1
}

Write-Step "Exporting visit Excel (may take 2-4 minutes) ..."
& $py "scrapers\visit_check_scrape_live.py" *>> $Log
if ($LASTEXITCODE -ne 0) {
    Write-LogLine $Log "exit=$LASTEXITCODE (export fail)"
    Write-Step "FAILED export. See $Log"
    exit $LASTEXITCODE
}

Write-Step "Importing into local DB / API ..."
if ($env:CZ_VISIT_PUSH_API -eq "1") {
    & $py "scrapers\visit_check_daily.py" --push-api @args *>> $Log
} else {
    & $py "scrapers\visit_check_daily.py" @args *>> $Log
}
$code = $LASTEXITCODE
Write-LogLine $Log "exit=$code"
if ($code -eq 0) { Write-Step "SUCCESS. See $Log" } else { Write-Step "FAILED exit=$code. See $Log" }
exit $code
