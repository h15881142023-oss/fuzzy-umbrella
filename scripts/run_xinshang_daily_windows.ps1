# 新商评日更入口 — 兼容旧调用，转调经营宝同款英文 Python 入口
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_xinshang_daily_windows.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_xinshang_daily_windows.ps1 -Once

param(
  [switch]$Once
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd -and $cmd.Source -notmatch "WindowsApps\\python.exe$") {
    $py = $cmd.Source
  } else {
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) { $py = $pyLauncher.Source } else { $py = $null }
  }
}
if (-not $py) {
  Write-Host "[BAD] 未找到 Python"
  exit 1
}

$argsList = @()
if ($Once) { $argsList += "--once" }
& $py "scripts\xinshang_daily_push.py" @argsList
exit $LASTEXITCODE
