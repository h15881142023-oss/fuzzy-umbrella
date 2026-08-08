# LR profit fill backfill. ASCII-only.
# Default: each day full scrape+fill+export+push.
# -PushOnce: scrape+fill each day, then kanban+WeCom only once for ToDate.
param(
    [string]$FromDate = "2026-07-23",
    [string]$ToDate = "2026-07-25",
    [switch]$StopOnError,
    [switch]$ForceRefill,
    [switch]$PushOnce
)

$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_local_common.ps1"

$Root = Get-RepoRoot
Set-Location $Root
$Work = Join-Path $Root "lr\work"
New-Item -ItemType Directory -Force -Path "logs","data\lr_scrape",$Work,"lr\output" | Out-Null
$Log = "logs\lr_profit_fill_local.log"

try {
    $from = [datetime]::ParseExact($FromDate, "yyyy-MM-dd", $null)
    $to = [datetime]::ParseExact($ToDate, "yyyy-MM-dd", $null)
} catch {
    Write-Step "Invalid date. Use yyyy-MM-dd. $_"
    exit 1
}
if ($from -gt $to) {
    Write-Step "FromDate must be <= ToDate"
    exit 1
}

# ASCII alias avoids GBK mojibake of Chinese names inside .ps1
$templatesDir = Join-Path $Root "lr\templates"
$templateNew = Join-Path $templatesDir "LR_DAILY_NEW.xlsx"
if (-not (Test-Path -LiteralPath $templateNew)) {
    $cand = Get-ChildItem -LiteralPath $templatesDir -Filter "*.xlsx" -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notlike "*5.4*" -and $_.Name -notlike "~$*" } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($cand) {
        Copy-Item -LiteralPath $cand.FullName -Destination $templateNew -Force
        Write-Step ("Aliased template -> LR_DAILY_NEW.xlsx from " + $cand.Name)
    }
}
if (-not (Test-Path -LiteralPath $templateNew)) {
    Write-Step "MISSING template: $templateNew (put non-5.4 xlsx under lr\templates)"
    exit 1
}
$env:LR_TEMPLATE_PATH = $templateNew
Write-Step ("Using template: " + $templateNew)

if ($ForceRefill) {
    Write-Step "ForceRefill: remove existing workbooks in range + sanitized cache"
    $cache = Join-Path $Work "_template_sanitized.xlsx"
    if (Test-Path -LiteralPath $cache) {
        Remove-Item -LiteralPath $cache -Force
        Write-Step "removed _template_sanitized.xlsx"
    }
    $curClean = $from
    $months = @{}
    while ($curClean -le $to) {
        $d = $curClean.ToString("yyyy-MM-dd")
        Get-ChildItem -LiteralPath $Work -Filter "*_$d.xlsx" -ErrorAction SilentlyContinue |
            ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force; Write-Step ("removed " + $_.Name) }
        $mk = $curClean.ToString("yyyy-MM")
        if (-not $months.ContainsKey($mk)) {
            $months[$mk] = $true
            Get-ChildItem -LiteralPath $Work -Filter "*$mk.xlsx" -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -match "${mk}\.xlsx$" } |
                ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force; Write-Step ("removed " + $_.Name) }
        }
        $curClean = $curClean.AddDays(1)
    }
}

Write-Step "LR PROFIT FILL BACKFILL $FromDate .. $ToDate (ForceRefill=$ForceRefill PushOnce=$PushOnce)"
Write-LogLine $Log "start backfill from=$FromDate to=$ToDate force=$ForceRefill pushOnce=$PushOnce"
try {
    $py = Ensure-Venv -Root $Root
} catch {
    Write-Step "venv fail: $_"
    Write-LogLine $Log "venv fail: $_"
    exit 1
}

$fillPs1 = Join-Path $PSScriptRoot "run_lr_profit_fill_local.ps1"
$ok = @()
$fail = @()
$cur = $from
while ($cur -le $to) {
    $d = $cur.ToString("yyyy-MM-dd")
    if ($PushOnce) {
        Write-Step "==== backfill day $d (scrape+fill only) ===="
        Write-LogLine $Log "backfill day=$d begin fill-only"
        Write-Step "Scraping LR page for $d ..."
        $code = Invoke-PythonLogged -PythonExe $py -Arguments @("lr\scrape_live.py", "--target-date", $d) -LogPath $Log
        if ($code -ne 0) {
            $fail += $d
            Write-Step "FAIL $d scrape exit=$code"
            Write-LogLine $Log "backfill day=$d scrape fail exit=$code"
            if ($StopOnError) { break }
            $cur = $cur.AddDays(1)
            continue
        }
        Write-Step "Fill template (fill-only). Large xlsx may take 1-5 min."
        $code = Invoke-PythonLogged -PythonExe $py -Arguments @(
            "lr\run_daily.py",
            "--scrape-json", "data\lr_scrape\latest.json",
            "--target-date", $d,
            "--fill-only"
        ) -LogPath $Log
        if ($code -eq 0) {
            $ok += $d
            Write-Step "OK $d fill"
            Write-LogLine $Log "backfill day=$d ok fill-only"
        } else {
            $fail += $d
            Write-Step "FAIL $d fill exit=$code"
            Write-LogLine $Log "backfill day=$d fill fail exit=$code"
            if (Test-Path $Log) { Get-Content -Path $Log -Tail 30 -Encoding UTF8 | ForEach-Object { Write-Host $_ } }
            if ($StopOnError) { break }
        }
    } else {
        Write-Step "==== backfill day $d (full pipeline, cumulative fill) ===="
        Write-LogLine $Log "backfill day=$d begin"
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $fillPs1 -TargetDate $d
        $code = $LASTEXITCODE
        if ($code -eq 0) {
            $ok += $d
            Write-LogLine $Log "backfill day=$d ok"
            Write-Step "OK $d"
        } else {
            $fail += $d
            Write-LogLine $Log "backfill day=$d fail exit=$code"
            Write-Step "FAIL $d exit=$code"
            if ($StopOnError) {
                Write-Step "StopOnError: abort remaining days"
                break
            }
        }
    }
    $cur = $cur.AddDays(1)
}

if ($PushOnce) {
    if ($ok.Count -eq 0) {
        Write-Step "PushOnce: no successful fill days; skip WeCom"
        Write-LogLine $Log "pushOnce skip no ok days"
        Write-Step "BACKFILL DONE ok=[] fail=[$($fail -join ',')]"
        exit 1
    }
    $pushDate = $ToDate
    if ($fail -contains $ToDate) {
        $pushDate = $ok[$ok.Count - 1]
        Write-Step "ToDate fill failed; push last OK day $pushDate"
    }
    Write-Step "==== PushOnce: kanban + WeCom for $pushDate (final workbook) ===="
    $Xlsx = Resolve-LrFilledXlsx -Root $Root -TargetDate $pushDate
    if (-not $Xlsx) {
        Write-Step "MISSING filled xlsx for $pushDate"
        Write-LogLine $Log "pushOnce missing xlsx $pushDate"
        exit 1
    }
    Write-Step "Filled xlsx: $Xlsx"
    $exportPs1 = Join-Path $PSScriptRoot "run_lr_kanban_export.ps1"
    & powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File $exportPs1 -Xlsx $Xlsx -TargetDate $pushDate
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        Write-Step "FAILED kanban export exit=$code"
        Write-LogLine $Log "pushOnce kanban fail exit=$code"
        exit $code
    }
    $code = Invoke-PythonLogged -PythonExe $py -Arguments @(
        "lr\run_daily.py",
        "--filled-xlsx", $Xlsx,
        "--target-date", $pushDate,
        "--push-only"
    ) -LogPath $Log
    if ($code -ne 0) {
        Write-Step "FAILED WeCom push exit=$code"
        Write-LogLine $Log "pushOnce wecom fail exit=$code"
        if (Test-Path $Log) { Get-Content -Path $Log -Tail 40 -Encoding UTF8 | ForEach-Object { Write-Host $_ } }
        exit $code
    }
    Write-Step "PushOnce SUCCESS for $pushDate"
}

Write-Step "BACKFILL DONE ok=[$($ok -join ',')] fail=[$($fail -join ',')]"
Write-LogLine $Log "backfill done ok=$($ok -join ',') fail=$($fail -join ',') pushOnce=$PushOnce"
if ($fail.Count -gt 0) { exit 1 }
exit 0
