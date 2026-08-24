# Copy new LR workbook to ASCII alias lr\templates\LR_DAILY_NEW.xlsx
# Avoid Chinese filenames inside .ps1 (GBK mojibake on Windows).
param(
    [Parameter(Mandatory = $false)]
    [string]$Source = ""
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_local_common.ps1"
$Root = Get-RepoRoot
$Dir = Join-Path $Root "lr\templates"
$Dest = Join-Path $Dir "LR_DAILY_NEW.xlsx"

New-Item -ItemType Directory -Force -Path $Dir | Out-Null

if ($Source) {
    if (-not (Test-Path -LiteralPath $Source)) {
        Write-Host "Source not found: $Source"
        exit 1
    }
    Copy-Item -LiteralPath $Source -Destination $Dest -Force
} else {
    $cand = Get-ChildItem -LiteralPath $Dir -Filter "*.xlsx" -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notlike "*5.4*" -and $_.Name -notlike "~$*" -and $_.Name -ne "LR_DAILY_NEW.xlsx" } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $cand) {
        Write-Host "No non-5.4 xlsx found in $Dir"
        Write-Host "Pass -Source <full path>"
        exit 1
    }
    Copy-Item -LiteralPath $cand.FullName -Destination $Dest -Force
    Write-Host ("Source: " + $cand.FullName)
}

Write-Host "Installed ASCII alias:"
Write-Host "  $Dest"
Write-Host ("  bytes=" + (Get-Item -LiteralPath $Dest).Length)

$cache = Join-Path $Root "lr\work\_template_sanitized.xlsx"
if (Test-Path -LiteralPath $cache) {
    Remove-Item -LiteralPath $cache -Force
    Write-Host "Removed stale _template_sanitized.xlsx"
}
exit 0
