# 本机：自配门店早间监控（Windows）
$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_local_common.ps1"

$Root = Get-RepoRoot
Set-Location $Root
New-Item -ItemType Directory -Force -Path "logs" | Out-Null
$Log = "logs\store_morning_monitor_local.log"

Write-LogLine $Log "start"
try {
    $py = Ensure-Venv -Root $Root
} catch {
    Write-LogLine $Log "venv fail: $_"
    exit 1
}

if ($env:CZ_STORE_MORNING_CMD) {
    cmd /c $env:CZ_STORE_MORNING_CMD *>> $Log
} else {
    # 默认：代补抓取一轮（若本机未配置 Chrome CDP，会失败并写日志）
    & $py "scrapers\powerbi_subsidy_daily.py" --once *>> $Log
}
$code = $LASTEXITCODE
Write-LogLine $Log "exit=$code"
exit $code
