Param(
    [string]$ProjectRoot = "",
    [string]$Branch = "cursor/local-windows-monitor-db56"
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
}

Set-Location -Path $ProjectRoot
Write-Host "project=$ProjectRoot"
Write-Host "branch=$Branch"

# 不走 raw.githubusercontent.com（部分网络不可达），改用 git 拉文件。
git fetch origin $Branch
if ($LASTEXITCODE -ne 0) {
    throw "git fetch failed. 请确认本机可访问 GitHub，或手动配置代理后再试。"
}

git checkout "origin/$Branch" -- "scripts/self_delivery_monitor_windows.py" "scripts/run_self_delivery_monitor_task.ps1"
if ($LASTEXITCODE -ne 0) {
    throw "git checkout file failed"
}

Write-Host "UPDATED scripts/self_delivery_monitor_windows.py"
Write-Host "UPDATED scripts/run_self_delivery_monitor_task.ps1"
Write-Host "下一步手动试跑:"
Write-Host '  python -u scripts\self_delivery_monitor_windows.py --headless --debug'
