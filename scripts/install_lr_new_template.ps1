# Copy WeChat/temp LR new workbook into repo templates. ASCII-only header.
param(
    [Parameter(Mandatory = $false)]
    [string]$Source = ""
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_local_common.ps1"
$Root = Get-RepoRoot
$Dest = Join-Path $Root "lr\templates\LR日报_新.xlsx"

if (-not $Source) {
    $Source = "D:\我的文档\xwechat_files\wxid_acpkrxuu0ted22_f987\temp\RWTemp\2026-08\f7219ce6041b6c82ef27149b5631a659\LR日报_新.xlsx"
}

if (-not (Test-Path -LiteralPath $Source)) {
    Write-Host "Source not found: $Source"
    Write-Host "Pass -Source <full path to LR日报_新.xlsx>"
    exit 1
}

New-Item -ItemType Directory -Force -Path (Split-Path $Dest) | Out-Null
Copy-Item -LiteralPath $Source -Destination $Dest -Force
Write-Host "Installed template:"
Write-Host "  $Dest"
Write-Host ("  bytes=" + (Get-Item -LiteralPath $Dest).Length)

# Drop sanitized cache so next fill uses the new file
$cache = Join-Path $Root "lr\work\_template_sanitized.xlsx"
if (Test-Path -LiteralPath $cache) {
    Remove-Item -LiteralPath $cache -Force
    Write-Host "Removed stale _template_sanitized.xlsx"
}
exit 0
