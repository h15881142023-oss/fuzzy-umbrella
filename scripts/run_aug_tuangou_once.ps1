# One-shot: ensure new template -> hotfix -> fill 2026-08-01..06 -> WeCom once.
# ASCII-only paths in this file (GBK consoles break Chinese filenames in .ps1).
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

$templatesDir = Join-Path $Root "lr\templates"
$Dest = Join-Path $templatesDir "LR_DAILY_NEW.xlsx"
Write-Step "Repo: $Root"

function Resolve-NewLrTemplate {
    param([string]$Dir, [string]$AliasPath, [string]$Source)
    New-Item -ItemType Directory -Force -Path $Dir | Out-Null
    if ($Source -and (Test-Path -LiteralPath $Source)) {
        Copy-Item -LiteralPath $Source -Destination $AliasPath -Force
        return $AliasPath
    }
    if (Test-Path -LiteralPath $AliasPath) {
        return $AliasPath
    }
    # Pick newest xlsx that is NOT the old 5.4 template (ASCII-safe filter)
    $cand = Get-ChildItem -LiteralPath $Dir -Filter "*.xlsx" -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notlike "*5.4*" -and $_.Name -notlike "~$*" } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($cand) {
        Copy-Item -LiteralPath $cand.FullName -Destination $AliasPath -Force
        Write-Step ("Aliased template -> LR_DAILY_NEW.xlsx from " + $cand.Name)
        return $AliasPath
    }
    return $null
}

$resolved = Resolve-NewLrTemplate -Dir $templatesDir -AliasPath $Dest -Source $TemplateSource
if (-not $resolved) {
    Write-Step "MISSING new LR template under lr\templates (need non-5.4 xlsx)"
    Write-Step "Current templates folder:"
    if (Test-Path -LiteralPath $templatesDir) {
        Get-ChildItem -LiteralPath $templatesDir | ForEach-Object { Write-Host ("  " + $_.Name + "  " + $_.Length) }
    }
    exit 1
}
Write-Step ("Template OK: " + $resolved + " bytes=" + (Get-Item -LiteralPath $resolved).Length)
$env:LR_TEMPLATE_PATH = $resolved

# drop sanitized cache so new template is used
$cache = Join-Path $Root "lr\work\_template_sanitized.xlsx"
if (Test-Path -LiteralPath $cache) {
    Remove-Item -LiteralPath $cache -Force
    Write-Step "removed _template_sanitized.xlsx"
}

# hotfix
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

# Re-resolve after hotfix (config.py prefers LR_DAILY_NEW.xlsx)
$env:LR_TEMPLATE_PATH = $Dest

$bf = Join-Path $PSScriptRoot "run_lr_profit_fill_backfill.ps1"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $bf `
    -FromDate $FromDate -ToDate $ToDate -ForceRefill -PushOnce
exit $LASTEXITCODE
