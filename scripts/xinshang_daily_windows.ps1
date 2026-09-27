# 新商评外发页 — 本机无人值守日更（请改用 run_xinshang_daily_windows.ps1）
# 保留本文件兼容旧调用；内部转调 run 脚本。
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\xinshang_daily_windows.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\run_xinshang_daily_windows.ps1") @args
exit $LASTEXITCODE
