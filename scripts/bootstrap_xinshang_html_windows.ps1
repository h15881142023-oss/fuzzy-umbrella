# One-shot bootstrap: download updater script + refresh dashboard HTML.
# Does NOT use git. Uses commit SHA only (jsDelivr-safe).
# Compatible with Windows PowerShell 5.1.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap_xinshang_html_windows.ps1

param(
  [string]$Ref = "12c91d4"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
New-Item -ItemType Directory -Force -Path (Join-Path $Root "scripts") | Out-Null

$stamp = Get-Date -Format "yyyyMMddHHmmss"
$ps1Url = ("https://fastly.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@{0}/scripts/update_xinshang_html_windows.ps1?t={1}" -f $Ref, $stamp)
$ps1Out = Join-Path $Root "scripts\update_xinshang_html_windows.ps1"

Write-Host ("==> download updater: " + $ps1Url)
Invoke-WebRequest -Uri $ps1Url -OutFile $ps1Out -UseBasicParsing -TimeoutSec 60

Write-Host "==> run updater"
& powershell -NoProfile -ExecutionPolicy Bypass -File $ps1Out -Ref $Ref
exit $LASTEXITCODE
