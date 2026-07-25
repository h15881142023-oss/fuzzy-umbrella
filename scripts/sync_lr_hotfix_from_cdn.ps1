# Sync LR kanban export hotfix without git (when GitHub fetch resets).
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\sync_lr_hotfix_from_cdn.ps1
param(
    [string]$Commit = "e7d0d63e622f717896acd538121b1b95ac9033a3"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

$short = $Commit.Substring(0, [Math]::Min(7, $Commit.Length))
$urls = @(
    "https://cdn.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@$short",
    "https://raw.githubusercontent.com/h15881142023-oss/fuzzy-umbrella/$Commit"
)

$files = @(
    "lr/export_kanban_com.py",
    "lr/kanban_image.py",
    "lr/run_daily.py",
    "scripts/export_lr_kanban_wps.ps1",
    "scripts/run_lr_profit_fill_local.ps1",
    "scripts/run_lr_kanban_push_existing.ps1",
    "scripts/diagnose_wps_com.ps1",
    "requirements.txt"
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
            $out = Join-Path $Root ($rel -replace "/", [IO.Path]::DirectorySeparatorChar)
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $out) | Out-Null
            # UTF-8 no BOM for .py; BOM for ps1 is fine too via utf8
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

$py = Join-Path $Root ".venv\Scripts\python.exe"
if (Test-Path $py) {
    Write-Host "Installing pywin32 ..."
    & $py -m pip install -q "pywin32>=306"
} else {
    Write-Host "WARN: .venv not found; create venv then pip install pywin32"
}

Write-Host ""
Write-Host "Hotfix files synced to commit $short."
Write-Host "Next:"
Write-Host "  .\.venv\Scripts\python.exe lr\run_daily.py --scrape-json data\lr_scrape\latest.json --target-date 2026-07-22"
