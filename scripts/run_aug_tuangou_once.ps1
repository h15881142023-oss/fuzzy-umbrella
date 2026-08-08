# One-shot: ensure new template -> hotfix -> fill 2026-08-01..06 -> WeCom once.
# ASCII-only. Run from anywhere.
param(
    [string]$FromDate = "2026-08-01",
    [string]$ToDate = "2026-08-06",
    [string]$HotfixSha = "HEAD",
    [string]$TemplateSource = ""
)

$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_local_common.ps1"
$Root = Get-RepoRoot
Set-Location $Root

$Dest = Join-Path $Root "lr\templates\LR日报_新.xlsx"
Write-Step "Repo: $Root"

# 1) template must exist
if (-not (Test-Path -LiteralPath $Dest)) {
    if ($TemplateSource -and (Test-Path -LiteralPath $TemplateSource)) {
        New-Item -ItemType Directory -Force -Path (Split-Path $Dest) | Out-Null
        Copy-Item -LiteralPath $TemplateSource -Destination $Dest -Force
        Write-Step "Copied template from Source -> $Dest"
    } else {
        Write-Step "MISSING: $Dest"
        Write-Step "Put LR日报_新.xlsx into lr\templates\ first, or pass -TemplateSource <fullpath>"
        Write-Step "Current templates folder:"
        if (Test-Path (Join-Path $Root "lr\templates")) {
            Get-ChildItem -LiteralPath (Join-Path $Root "lr\templates") | ForEach-Object { Write-Host ("  " + $_.Name + "  " + $_.Length) }
        }
        exit 1
    }
} else {
    Write-Step ("Template OK: " + $Dest + " bytes=" + (Get-Item -LiteralPath $Dest).Length)
}

# drop sanitized cache so new template is used
$cache = Join-Path $Root "lr\work\_template_sanitized.xlsx"
if (Test-Path -LiteralPath $cache) {
    Remove-Item -LiteralPath $cache -Force
    Write-Step "removed _template_sanitized.xlsx"
}

# 2) hotfix (optional sha)
$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    try { $null = Ensure-Venv -Root $Root; $py = Join-Path $Root ".venv\Scripts\python.exe" } catch {
        Write-Step "venv fail: $_"; exit 1
    }
}
Write-Step "Hotfix sha=$HotfixSha"
& $py "lr\download_hotfix.py" $HotfixSha
if ($LASTEXITCODE -ne 0) {
    Write-Step "hotfix failed exit=$LASTEXITCODE (CDN may lag; retry in 1-2 min)"
    exit $LASTEXITCODE
}

# 3) backfill fill-only per day, push once
$bf = Join-Path $PSScriptRoot "run_lr_profit_fill_backfill.ps1"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $bf `
    -FromDate $FromDate -ToDate $ToDate -ForceRefill -PushOnce
exit $LASTEXITCODE
