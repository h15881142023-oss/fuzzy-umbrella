# Local store morning monitor (Windows)
$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_local_common.ps1"

$Root = Get-RepoRoot
Set-Location $Root
New-Item -ItemType Directory -Force -Path "logs" | Out-Null
$Log = "logs\store_morning_monitor_local.log"

Write-Step "Store morning start. Log: $Root\$Log"
Write-LogLine $Log "start"
try {
    $py = Ensure-Venv -Root $Root
} catch {
    Write-Step "venv fail: $_"
    Write-LogLine $Log "venv fail: $_"
    exit 1
}

Write-Step "Running morning monitor ..."
if ($env:CZ_STORE_MORNING_CMD) {
    cmd /c $env:CZ_STORE_MORNING_CMD *>> $Log
} else {
    & $py "scrapers\powerbi_subsidy_daily.py" --once *>> $Log
}
$code = $LASTEXITCODE
Write-LogLine $Log "exit=$code"
if ($code -eq 0) { Write-Step "SUCCESS. See $Log" } else { Write-Step "FAILED exit=$code. See $Log" }
exit $code
