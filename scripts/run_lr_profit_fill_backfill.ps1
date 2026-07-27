# LR profit fill backfill: always full scrape+fill+export+push in date order. ASCII-only.
param(
    [string]$FromDate = "2026-07-23",
    [string]$ToDate = "2026-07-25",
    [switch]$StopOnError,
    [switch]$ForceRefill
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

if ($ForceRefill) {
    Write-Step "ForceRefill: remove existing workbooks in range"
    $curClean = $from
    $months = @{}
    while ($curClean -le $to) {
        $d = $curClean.ToString("yyyy-MM-dd")
        $daily = Join-Path $Work ("LR日报_{0}.xlsx" -f $d)
        if (Test-Path -LiteralPath $daily) {
            Remove-Item -LiteralPath $daily -Force
            Write-Step "removed $daily"
        }
        $mk = $curClean.ToString("yyyy-MM")
        if (-not $months.ContainsKey($mk)) {
            $months[$mk] = $true
            $monthly = Join-Path $Work ("LR日报_{0}.xlsx" -f $mk)
            if (Test-Path -LiteralPath $monthly) {
                Remove-Item -LiteralPath $monthly -Force
                Write-Step "removed $monthly"
            }
        }
        $curClean = $curClean.AddDays(1)
    }
}

Write-Step "LR PROFIT FILL BACKFILL $FromDate .. $ToDate (ForceRefill=$ForceRefill)"
Write-LogLine $Log "start backfill from=$FromDate to=$ToDate force=$ForceRefill"
try {
    $null = Ensure-Venv -Root $Root
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
    $cur = $cur.AddDays(1)
}

Write-Step "BACKFILL DONE ok=[$($ok -join ',')] fail=[$($fail -join ',')]"
Write-LogLine $Log "backfill done ok=$($ok -join ',') fail=$($fail -join ',')"
if ($fail.Count -gt 0) { exit 1 }
exit 0
