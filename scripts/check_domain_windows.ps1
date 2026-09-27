# Domain health check (ASCII-only for Windows PowerShell 5)
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\check_domain_windows.ps1

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "======== domain check ========"
Write-Host ("project: " + $Root)

$html = Join-Path $Root "static\dashboards\cz1-xinshang-pingjia.html"
if (Test-Path $html) {
  Write-Host "[OK] dashboard html exists"
} else {
  Write-Host "[MISS] dashboard html missing"
}

$listen = netstat -ano | Select-String ":5001\s+.*LISTENING"
if ($listen) {
  Write-Host "[OK] port 5001 is listening"
  try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:5001/evaluation/xinshang" -UseBasicParsing -TimeoutSec 8
    Write-Host ("[OK] local dashboard status=" + $resp.StatusCode)
  } catch {
    Write-Host ("[BAD] local dashboard request failed: " + $_.Exception.Message)
  }
} else {
  Write-Host "[MISS] port 5001 not listening (web not running)"
}

$cf = Get-Command cloudflared -ErrorAction SilentlyContinue
$cfConfig = Join-Path $env:USERPROFILE ".cloudflared\config.yml"
if ($cf) {
  Write-Host ("[OK] cloudflared installed: " + $cf.Source)
} else {
  Write-Host "[MISS] cloudflared not installed"
}

if (Test-Path $cfConfig) {
  Write-Host ("[OK] tunnel config found: " + $cfConfig)
  Get-Content $cfConfig -ErrorAction SilentlyContinue | Select-Object -First 12 | ForEach-Object { Write-Host ("    " + $_) }
} else {
  Write-Host ("[MISS] tunnel config not found: " + $cfConfig)
}

$cfProc = Get-Process cloudflared -ErrorAction SilentlyContinue
if ($cfProc) {
  Write-Host ("[OK] cloudflared running pid=" + ($cfProc.Id -join ","))
} else {
  Write-Host "[MISS] cloudflared process not running"
}

Write-Host "target: https://1.chuanzangyiqu.top/evaluation/xinshang"
Write-Host "note: dashboard is public; other pages still need site password"
Write-Host "================================"
