# Download xinshang sync files into this folder (no git required).
# Uses commit SHA (jsDelivr / raw mirror safe).
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\fetch_xinshang_tools_windows.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\fetch_xinshang_tools_windows.ps1 -Ref ab277ab

param(
  [string]$Ref = "cursor/cz1-merchant-dashboard-74a9"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$relPaths = @(
  "scripts/xinshang_daily_push.py",
  "scripts/xinshang_wecom.py",
  "scripts/xinshang_wecom_config.json",
  "scripts/run_xinshang_daily_push.bat",
  "scripts/install_xinshang_task.ps1",
  "scripts/install_xinshang_task.bat",
  "scripts/update_xinshang_html_windows.ps1",
  "scripts/bootstrap_xinshang_html_windows.ps1",
  "scripts/sync_xinshang_full_windows.ps1",
  "scripts/sync_xinshang_bi_windows.ps1",
  "scripts/sync_peer_compare_windows.ps1",
  "scripts/sync_xinshang_from_chuxin.py",
  "scripts/sync_peer_compare_from_chuxin.py",
  "scripts/start_chrome_powerbi_windows.ps1",
  "scrapers/__init__.py",
  "scrapers/cdp_client.py",
  "scrapers/powerbi_wind_js.py",
  "scrapers/scrape_powerbi_wind_online.py"
)

function Get-RemoteFile([string]$rel) {
  $stamp = Get-Date -Format "yyyyMMddHHmmss"
  $urls = @(
    ("https://ghproxy.net/https://raw.githubusercontent.com/h15881142023-oss/fuzzy-umbrella/" + $Ref + "/" + $rel + "?t=" + $stamp),
    ("https://raw.githubusercontent.com/h15881142023-oss/fuzzy-umbrella/" + $Ref + "/" + $rel + "?t=" + $stamp)
  )
  if ($Ref -notmatch "/") {
    $urls += @(
      ("https://fastly.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@" + $Ref + "/" + $rel + "?t=" + $stamp),
      ("https://cdn.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@" + $Ref + "/" + $rel + "?t=" + $stamp)
    )
  }
  $tmp = Join-Path $env:TEMP ("cz1-" + $stamp + "-" + ($rel -replace "[\\/]", "_"))
  foreach ($url in $urls) {
    Write-Host ("==> try: " + $url)
    try {
      Invoke-WebRequest -Uri $url -OutFile $tmp -UseBasicParsing -TimeoutSec 120
      $bytes = [System.IO.File]::ReadAllBytes($tmp)
      if ($bytes.Length -lt 40) {
        Write-Host ("[WARN] too small: " + $bytes.Length)
        continue
      }
      return $tmp
    } catch {
      Write-Host ("[WARN] failed: " + $_.Exception.Message)
    }
  }
  return $null
}

$okAll = $true
foreach ($rel in $relPaths) {
  $winRel = $rel -replace "/", "\"
  $dest = Join-Path $Root $winRel
  New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
  $tmp = Get-RemoteFile $rel
  if (-not $tmp) {
    Write-Host ("[BAD] missing: " + $rel)
    $okAll = $false
    continue
  }
  Copy-Item $tmp $dest -Force
  Remove-Item $tmp -Force -ErrorAction SilentlyContinue
  Write-Host ("[OK] " + $winRel)
}

if (-not $okAll) {
  Write-Host "[BAD] some files failed. Check network / GitHub access."
  exit 1
}

Write-Host ""
Write-Host "[OK] tools ready. Next:"
Write-Host "  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_xinshang_task.ps1"
exit 0
