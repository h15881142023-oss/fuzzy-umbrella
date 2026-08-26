# 独立同步「同分群数值对比」模块（从初心新商考核各模块页拉取，不影响主看板常规同步）
# 用法：
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\sync_peer_compare_windows.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\sync_peer_compare_windows.ps1 -Date 2026-08-24
#
# 已停用 Excel 同步。旧参数 -XlsxPath 会被忽略。

param(
  [string]$Date = "",
  [string]$XlsxPath = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Get-Python {
  $venv = Join-Path $Root ".venv\Scripts\python.exe"
  if (Test-Path $venv) { return $venv }
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd -and $cmd.Source -notmatch "WindowsApps\\python.exe$") { return $cmd.Source }
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) { return $py.Source }
  return $null
}

$python = Get-Python
if (-not $python) {
  Write-Host "[BAD] Python not found."
  exit 1
}

if ($XlsxPath) {
  Write-Host "[WARN] Excel 同步已停用，忽略 -XlsxPath。改从新商考核各模块页拉取。"
}

if ($Date) {
  & $python "scripts\sync_peer_compare_from_chuxin.py" --date $Date
} else {
  & $python "scripts\sync_peer_compare_from_chuxin.py"
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "[OK] 同分群数值对比模块已同步（Metabase 各模块页）"
Write-Host "Open: https://1.chuanzangyiqu.top/evaluation/xinshang"
Write-Host "Then click: 同分群数值对比（需密码） and input chuanyi006"
