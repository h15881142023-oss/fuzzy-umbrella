# Update critical Windows local-automation files without git pull
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "scrapers"))) {
  $Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}
Set-Location $Root

$branch = "cursor/automations-to-local-7100"
$relFiles = @(
  "scrapers/visit_check_scrape_live.py",
  "scrapers/powerbi_subsidy_daily.py",
  "scrapers/powerbi_page_js.py",
  "scrapers/cdp_client.py",
  "scripts/start_chrome_powerbi.ps1",
  "scripts/run_store_morning_monitor_local.ps1",
  "scripts/_local_common.ps1",
  "scripts/run_visit_check_local.ps1"
)

$mirrors = @(
  "https://raw.githubusercontent.com/h15881142023-oss/fuzzy-umbrella/$branch",
  "https://ghproxy.net/https://raw.githubusercontent.com/h15881142023-oss/fuzzy-umbrella/$branch",
  "https://mirror.ghproxy.com/https://raw.githubusercontent.com/h15881142023-oss/fuzzy-umbrella/$branch"
)

function Get-FileBytes([string]$url) {
  try {
    $wc = New-Object System.Net.WebClient
    $wc.Headers.Add("User-Agent", "Mozilla/5.0")
    return $wc.DownloadData($url)
  } catch {
    return $null
  }
}

foreach ($rel in $relFiles) {
  $ok = $false
  foreach ($base in $mirrors) {
    $url = "$base/$rel"
    Write-Host "Trying $url"
    $bytes = Get-FileBytes $url
    if ($bytes -and $bytes.Length -gt 50) {
      $out = Join-Path $Root ($rel -replace "/", "\")
      $dir = Split-Path -Parent $out
      New-Item -ItemType Directory -Force -Path $dir | Out-Null
      [System.IO.File]::WriteAllBytes($out, $bytes)
      Write-Host "OK -> $out ($($bytes.Length) bytes)"
      $ok = $true
      break
    }
  }
  if (-not $ok) {
    throw "Failed to download $rel from all mirrors"
  }
}

Write-Host ""
Write-Host "Update done. Next:"
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\run_visit_check_local.ps1"
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\run_store_morning_monitor_local.ps1"
