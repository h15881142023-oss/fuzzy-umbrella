# Start local web (5001) + Cloudflare tunnel for domain access
# Public dashboard: https://1.chuanzangyiqu.top/evaluation/xinshang
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\start_domain_windows.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
New-Item -ItemType Directory -Force -Path ".\logs" | Out-Null

Write-Host ("==> project: " + $Root)

function Get-SystemPython {
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd -and $cmd.Source -notmatch "WindowsApps\\python.exe$") {
    return $cmd.Source
  }
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) { return $py.Source }
  $cmd3 = Get-Command python3 -ErrorAction SilentlyContinue
  if ($cmd3 -and $cmd3.Source -notmatch "WindowsApps\\python.exe$") {
    return $cmd3.Source
  }
  return $null
}

$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
$sysPython = Get-SystemPython

if (-not (Test-Path $venvPython)) {
  if (-not $sysPython) {
    Write-Host "[MISS] Python not found. Install Python 3 and rerun."
    exit 1
  }
  Write-Host ("==> create venv with: " + $sysPython)
  if ($sysPython -match "\\py.exe$") {
    & $sysPython -3 -m venv (Join-Path $Root ".venv")
  } else {
    & $sysPython -m venv (Join-Path $Root ".venv")
  }
  if (-not (Test-Path $venvPython)) {
    Write-Host "[BAD] venv created but python.exe missing"
    Write-Host ("expected: " + $venvPython)
    exit 1
  }
  & $venvPython -m pip install -U pip
  & $venvPython -m pip install -r (Join-Path $Root "requirements.txt")
}

if (-not $env:CZ_SITE_PASSWORD) { $env:CZ_SITE_PASSWORD = "chuanzang2026" }
if (-not $env:CZ_SECRET_KEY) { $env:CZ_SECRET_KEY = "chuanzang-change-me-in-production" }

Write-Host "==> init db"
& $venvPython -c "import db; db.init_db(); db.seed_demo_if_empty(); print('DB ready')"

$listening = netstat -ano | Select-String ":5001\s+.*LISTENING"
$runWeb = Join-Path $Root "scripts\run_web_windows.py"
if ($listening) {
  Write-Host "==> port 5001 already listening"
} else {
  if (-not (Test-Path $runWeb)) {
    Write-Host ("[MISS] launcher missing: " + $runWeb)
    exit 1
  }
  if (-not (Test-Path $venvPython)) {
    Write-Host ("[MISS] python missing: " + $venvPython)
    exit 1
  }
  Write-Host ("==> starting web with: " + $venvPython)
  Write-Host ("==> launcher: " + $runWeb)
  # Launch via a new PowerShell window to avoid Start-Process -c path issues on Windows
  $psCmd = "& `"$venvPython`" `"$runWeb`""
  $web = Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile","-ExecutionPolicy","Bypass","-Command",$psCmd) -WorkingDirectory $Root -PassThru -WindowStyle Minimized
  $web.Id | Out-File -Encoding ascii (Join-Path $Root "logs\web_windows.pid") -Force
  Start-Sleep -Seconds 5
}

try {
  $r = Invoke-WebRequest -Uri "http://127.0.0.1:5001/evaluation/xinshang" -UseBasicParsing -TimeoutSec 8
  Write-Host ("==> local dashboard OK status=" + $r.StatusCode)
} catch {
  Write-Host ("==> local dashboard not ready: " + $_.Exception.Message)
}

$cfConfig = Join-Path $env:USERPROFILE ".cloudflared\config.yml"
$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cloudflared) {
  $guess = @(
    "$env:ProgramFiles\cloudflared\cloudflared.exe",
    "$env:LOCALAPPDATA\cloudflared\cloudflared.exe",
    "$env:USERPROFILE\bin\cloudflared.exe"
  ) | Where-Object { Test-Path $_ } | Select-Object -First 1
  if ($guess) {
    $cloudflared = @{ Source = $guess }
    Write-Host ("==> found cloudflared at " + $guess)
  }
}

if (-not $cloudflared) {
  Write-Host "[MISS] cloudflared not installed"
  Write-Host "Install steps:"
  Write-Host "  winget install --id Cloudflare.cloudflared -e"
  Write-Host "  OR download from Cloudflare cloudflared Windows releases"
  Write-Host "Then: cloudflared tunnel login"
  Write-Host "      cloudflared tunnel create chuanzang-data"
  Write-Host "      cloudflared tunnel route dns chuanzang-data 1.chuanzangyiqu.top"
  Write-Host "Local web may already be up: http://127.0.0.1:5001/evaluation/xinshang"
  exit 2
}

if (-not (Test-Path $cfConfig)) {
  Write-Host ("[MISS] tunnel config not found: " + $cfConfig)
  Write-Host "Create it from cloudflared.config.windows.example.yml and set tunnel id + credentials-file"
  Write-Host "Local web may already be up: http://127.0.0.1:5001/evaluation/xinshang"
  exit 3
}

$cfProc = Get-Process cloudflared -ErrorAction SilentlyContinue
if ($cfProc) {
  Write-Host "==> cloudflared already running"
} else {
  Write-Host "==> starting cloudflared"
  $cfPath = $cloudflared.Source
  Start-Process -FilePath $cfPath -ArgumentList @("tunnel","--config",$cfConfig,"run","chuanzang-data") -WorkingDirectory $Root -WindowStyle Minimized
  Start-Sleep -Seconds 3
}

Write-Host ""
Write-Host "Done. Verify:"
Write-Host "  local : http://127.0.0.1:5001/evaluation/xinshang"
Write-Host "  domain: https://1.chuanzangyiqu.top/evaluation/xinshang"
Write-Host "  home  : https://1.chuanzangyiqu.top/  (password required)"
