# 利润填写推送：按日期区间补跑（抓取 → 填表 → 看板 → 企微）
# 默认：2026-07-22 .. 2026-07-25（含）
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts\run_lr_profit_fill_backfill.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\run_lr_profit_fill_backfill.ps1 -FromDate 2026-07-20 -ToDate 2026-07-25
#   powershell -ExecutionPolicy Bypass -File scripts\run_lr_profit_fill_backfill.ps1 -FromDate 2026-07-24 -ToDate 2026-07-25 -StopOnError
param(
    [string]$FromDate = "2026-07-22",
    [string]$ToDate = "2026-07-25",
    [switch]$StopOnError
)

$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_local_common.ps1"

$Root = Get-RepoRoot
Set-Location $Root
New-Item -ItemType Directory -Force -Path "logs","data\lr_scrape","lr\work","lr\output" | Out-Null
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

Write-Step "LR PROFIT FILL BACKFILL $FromDate .. $ToDate (StopOnError=$StopOnError)"
Write-LogLine $Log "start backfill from=$FromDate to=$ToDate"
try {
    $null = Ensure-Venv -Root $Root
} catch {
    Write-Step "venv fail: $_"
    Write-LogLine $Log "venv fail: $_"
    exit 1
}

$env:LR_KANBAN_EXPORT = "ps1,com"
$ok = @()
$fail = @()
$cur = $from
while ($cur -le $to) {
    $d = $cur.ToString("yyyy-MM-dd")
    Write-Step "==== backfill day $d ===="
    Write-LogLine $Log "backfill day=$d begin"
    $code = 1
    try {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "run_lr_profit_fill_local.ps1") -TargetDate $d
        $code = $LASTEXITCODE
    } catch {
        Write-LogLine $Log "backfill day=$d exception: $_"
        $code = 1
    }
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
