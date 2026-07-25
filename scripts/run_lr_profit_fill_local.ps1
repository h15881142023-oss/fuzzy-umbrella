# 利润填写推送（≠ 利润数据源推送）
# 抓取 → 填 LR 模板「数据源(日)」→ WPS 五城看板截图 → 企微 5 图 + Excel
# 默认计划：每天 23:30
param(
    [string]$TargetDate = ""
)

$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_local_common.ps1"

$Root = Get-RepoRoot
Set-Location $Root
New-Item -ItemType Directory -Force -Path "logs","data\lr_scrape","lr\work","lr\output" | Out-Null
$Log = "logs\lr_profit_fill_local.log"

if (-not $TargetDate) {
    $TargetDate = (Get-Date).AddDays(-1).ToString("yyyy-MM-dd")
}

Write-Step "LR PROFIT FILL start target=$TargetDate. Log: $Root\$Log"
Write-LogLine $Log "start profit-fill target=$TargetDate"
try {
    $py = Ensure-Venv -Root $Root
} catch {
    Write-Step "venv fail: $_"
    Write-LogLine $Log "venv fail: $_"
    exit 1
}

Write-Step "Scraping LR page for $TargetDate ..."
$code = Invoke-PythonLogged -PythonExe $py -Arguments @("lr\scrape_live.py", "--target-date", $TargetDate) -LogPath $Log
if ($code -ne 0) {
    Write-LogLine $Log "exit=$code (scrape fail)"
    Write-Step "FAILED scrape exit=$code. See $Log"
    exit $code
}

Write-Step "Fill template + WPS kanban + WeCom (5 images + excel) ..."
# PowerShell COM 优先：避免 64 位 Python 对 32 位 WPS 报「无效的类字符串」
$env:LR_KANBAN_EXPORT = "ps1,com"
$code = Invoke-PythonLogged -PythonExe $py -Arguments @(
    "lr\run_daily.py",
    "--scrape-json", "data\lr_scrape\latest.json",
    "--target-date", $TargetDate
) -LogPath $Log
Write-LogLine $Log "exit=$code"
if ($code -eq 0) {
    Write-Step "SUCCESS profit-fill. See $Log"
} else {
    Write-Step "FAILED profit-fill exit=$code. See $Log"
    if (Test-Path $Log) { Get-Content -Path $Log -Tail 60 -Encoding UTF8 | ForEach-Object { Write-Host $_ } }
}
exit $code
