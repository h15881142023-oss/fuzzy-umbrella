# One-shot bootstrap: download updater script + refresh dashboard HTML.
# Does NOT use git. Uses commit SHA only (jsDelivr-safe).
#
#   powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_xinshang_html_windows.ps1

param(
  [string]$Ref = "4ee4db6"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
New-Item -ItemType Directory -Force -Path (Join-Path $Root "scripts") | Out-Null

$stamp = [int][double]::Parse((Get-Date -UFormat %s))
$ps1Url = "https://cdn.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@" + $Ref + "/scripts/update_xinshang_html_windows.ps1?t=" + $stamp
$ps1Out = Join-Path $Root "scripts\update_xinshang_html_windows.ps1"

Write-Host ("==> download updater: " + $ps1Url)
Invoke-WebRequest -Uri $ps1Url -OutFile $ps1Out -UseBasicParsing -TimeoutSec 60

Write-Host "==> run updater"
& powershell -NoProfile -ExecutionPolicy Bypass -File $ps1Out -Ref $Ref
exit $LASTEXITCODE
