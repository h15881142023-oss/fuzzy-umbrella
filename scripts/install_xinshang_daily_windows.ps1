# 新商评外发页 — 兼容旧安装入口，转调经营宝同款 install_xinshang_task.ps1
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_xinshang_daily_windows.ps1

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here "install_xinshang_task.ps1")
exit $LASTEXITCODE
