# Download LR push hotfix files as UTF-8 (ASCII-safe bootstrap). Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\sync_lr_push_hotfix.ps1
param(
    [string]$Commit = "HEAD"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

$sha = "8e20be0"
if ($Commit -ne "HEAD" -and $Commit.Length -ge 7) { $sha = $Commit.Substring(0, 7) }
$base = "https://cdn.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@$sha"

$files = @(
    "lr/write_kanban_export_cfg.py",
    "lr/verify_kanban_pngs.py",
    "lr/run_daily.py",
    "scripts/_local_common.ps1",
    "scripts/export_lr_kanban_wps.ps1",
    "scripts/run_lr_kanban_export.ps1",
    "scripts/run_lr_kanban_push_existing.ps1"
)

foreach ($rel in $files) {
    $url = "$base/$rel"
    $out = Join-Path $Root ($rel -replace "/", [IO.Path]::DirectorySeparatorChar)
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $out) | Out-Null
    Write-Host "GET $url"
    $text = (Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 120).Content
    if (-not $text -or $text.Length -lt 20) { throw "Download too short: $rel" }
    $enc = New-Object System.Text.UTF8Encoding $true
    [IO.File]::WriteAllText($out, $text, $enc)
    Write-Host "OK  $out ($($text.Length) bytes UTF8-BOM)"
}

Write-Host ""
Write-Host "Next (push filled workbook for t-1):"
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\run_lr_kanban_push_existing.ps1 -TargetDate 2026-07-26"
