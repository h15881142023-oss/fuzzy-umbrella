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
$code = Invoke-PythonLogged -PythonExe $py -Arguments @("scrapers\visit_check_scrape_live.py") -LogPath $Log
if ($code -ne 0) {
    Write-LogLine $Log "exit=$code (export fail)"
    Write-Step "FAILED export. See $Log"
    if (Test-Path $Log) { Get-Content -Path $Log -Tail 40 -Encoding UTF8 | ForEach-Object { Write-Host $_ } }
    exit $code
}

Write-Step "Importing into local DB / API ..."
$pyArgs = @("scrapers\visit_check_daily.py")
if ($env:CZ_VISIT_PUSH_API -eq "1") {
    $pyArgs += "--push-api"
}
if ($args) { $pyArgs += $args }
$code = Invoke-PythonLogged -PythonExe $py -Arguments $pyArgs -LogPath $Log
Write-LogLine $Log "exit=$code"
if ($code -eq 0) {
    Write-Step "SUCCESS. See $Log"
} else {
    Write-Step "FAILED exit=$code. See $Log"
    if (Test-Path $Log) { Get-Content -Path $Log -Tail 40 -Encoding UTF8 | ForEach-Object { Write-Host $_ } }
}
exit $code
