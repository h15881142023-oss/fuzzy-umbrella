# 独立同步「同分群数值对比」模块（不影响主看板常规同步）
# 用法：
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\sync_peer_compare_windows.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\sync_peer_compare_windows.ps1 -XlsxPath "D:\...\新商考核体系1.1(202607281658).xlsx"

param(
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

if ($XlsxPath -and -not (Test-Path $XlsxPath)) {
  Write-Host ("[BAD] Excel not found: " + $XlsxPath)
  exit 1
}

if ($XlsxPath) {
  & $python "scripts\sync_peer_compare_from_excel.py" --xlsx $XlsxPath
} else {
  & $python "scripts\sync_peer_compare_from_excel.py"
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "[OK] 同分群数值对比模块已同步"
Write-Host "Open: https://1.chuanzangyiqu.top/evaluation/xinshang"
Write-Host "Then click: 同分群数值对比（需密码） and input chuanyi006"
