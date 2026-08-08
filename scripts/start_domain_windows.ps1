# Start local web (5001) + Cloudflare tunnel for domain access
# Public dashboard: https://1.chuanzangyiqu.top/evaluation/xinshang
# Other pages still need site password
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\start_domain_windows.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
New-Item -ItemType Directory -Force -Path ".\logs" | Out-Null

Write-Host ("==> project: " + $Root)

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
  Write-Host "==> create venv and install deps"
  python -m venv .venv
  & ".\.venv\Scripts\python.exe" -m pip install -U pip
  & ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
}

if (-not $env:CZ_SITE_PASSWORD) { $env:CZ_SITE_PASSWORD = "chuanzang2026" }
if (-not $env:CZ_SECRET_KEY) { $env:CZ_SECRET_KEY = "chuanzang-change-me-in-production" }

Write-Host "==> init db"
& ".\.venv\Scripts\python.exe" -c "import db; db.init_db(); db.seed_demo_if_empty(); print('DB ready')"

$listening = netstat -ano | Select-String ":5001\s+.*LISTENING"
if ($listening) {
  Write-Host "==> port 5001 already listening"
} else {
  Write-Host "==> starting web on 5001"
  $arg = "-c"
  $py = "from app import create_app; create_app().run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)"
  $web = Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList @($arg, $py) -PassThru -WindowStyle Minimized
  $web.Id | Out-File -Encoding ascii ".\logs\web_windows.pid" -Force
  Start-Sleep -Seconds 3
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
  Write-Host "[MISS] cloudflared not installed"
  Write-Host "Install Windows cloudflared, then rerun this script."
  exit 1
}

if (-not (Test-Path $cfConfig)) {
  Write-Host ("[MISS] tunnel config not found: " + $cfConfig)
  Write-Host "Copy cloudflared.config.windows.example.yml to that path and fill tunnel id."
  Write-Host "Also ensure: cloudflared tunnel login / create / route dns"
  exit 1
}

$cfProc = Get-Process cloudflared -ErrorAction SilentlyContinue
if ($cfProc) {
  Write-Host "==> cloudflared already running"
} else {
  Write-Host "==> starting cloudflared"
  # Do not redirect stdout/stderr to the same file (Start-Process will fail on Windows)
  Start-Process -FilePath $cloudflared.Source -ArgumentList @("tunnel","--config",$cfConfig,"run","chuanzang-data") -WindowStyle Minimized
  Start-Sleep -Seconds 3
}

Write-Host ""
Write-Host "Done. Verify:"
Write-Host "  local : http://127.0.0.1:5001/evaluation/xinshang"
Write-Host "  domain: https://1.chuanzangyiqu.top/evaluation/xinshang"
Write-Host "  home  : https://1.chuanzangyiqu.top/  (password required)"
Write-Host ""
Write-Host "If domain still fails, run check_domain_windows.ps1 and paste output."
