# 本机：拜访检核日更端到端（Windows）
$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_local_common.ps1"

$Root = Get-RepoRoot
Set-Location $Root
New-Item -ItemType Directory -Force -Path "logs","data\visit_exports" | Out-Null
$Log = "logs\visit_check_local.log"

Write-LogLine $Log "start"
try {
    $py = Ensure-Venv -Root $Root
} catch {
    Write-LogLine $Log "venv fail: $_"
    exit 1
}

& $py "scrapers\visit_check_scrape_live.py" *>> $Log
if ($LASTEXITCODE -ne 0) {
    Write-LogLine $Log "exit=$LASTEXITCODE (export fail)"
    exit $LASTEXITCODE
}

if ($env:CZ_VISIT_PUSH_API -eq "1") {
    & $py "scrapers\visit_check_daily.py" --push-api @args *>> $Log
} else {
    & $py "scrapers\visit_check_daily.py" @args *>> $Log
}
$code = $LASTEXITCODE
Write-LogLine $Log "exit=$code"
exit $code
