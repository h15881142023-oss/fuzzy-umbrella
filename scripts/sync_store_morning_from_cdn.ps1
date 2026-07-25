# Sync store-morning Power BI scraper without git (when GitHub fetch resets).
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\sync_store_morning_from_cdn.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\sync_store_morning_from_cdn.ps1 -Commit <full_or_short_sha>
param(
    [string]$Commit = ""
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

if (-not $Commit) {
    # Prefer branch tip via raw; CDN pin set after each hotfix commit.
    $Commit = "cursor/automations-to-local-7100"
}

$short = if ($Commit.Length -ge 7 -and $Commit -notmatch "/") { $Commit.Substring(0, 7) } else { $Commit }
$urls = @(
    "https://cdn.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@$short",
    "https://raw.githubusercontent.com/h15881142023-oss/fuzzy-umbrella/$Commit",
    "https://ghproxy.net/https://raw.githubusercontent.com/h15881142023-oss/fuzzy-umbrella/$Commit"
)

$files = @(
    "scrapers/powerbi_subsidy_daily.py",
    "scrapers/powerbi_page_js.py",
    "scrapers/cdp_client.py",
    "scripts/run_store_morning_monitor_local.ps1",
    "scripts/start_chrome_powerbi.ps1",
    "scripts/_local_common.ps1"
)

function Get-RemoteText([string]$Url) {
    $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 60
    return $resp.Content
}

foreach ($rel in $files) {
    $ok = $false
    foreach ($base in $urls) {
        $url = "$base/$rel"
        try {
            Write-Host "GET $url"
            $text = Get-RemoteText $url
            if (-not $text -or $text.Length -lt 50) { throw "too short" }
            $out = Join-Path $Root ($rel -replace "/", [IO.Path]::DirectorySeparatorChar)
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $out) | Out-Null
            [IO.File]::WriteAllText($out, $text, [Text.UTF8Encoding]::new($false))
            Write-Host "OK  $rel ($($text.Length) bytes)"
            $ok = $true
            break
        } catch {
            Write-Host "FAIL $url -> $($_.Exception.Message)"
        }
    }
    if (-not $ok) { throw "Cannot download $rel from any mirror" }
}

Write-Host ""
Write-Host "Store-morning files synced ($Commit)."
Write-Host "Next:"
Write-Host "  1) Open ChromeAutomation and ensure Power BI report is visible (补贴监测)"
Write-Host "  2) powershell -ExecutionPolicy Bypass -File scripts\run_store_morning_monitor_local.ps1"
