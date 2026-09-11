# 川藏一区 · 新商评价看板（Windows 启动：本机 Web + 可选 Cloudflare 隧道）
# 用法：在项目根目录右键「使用 PowerShell 运行」，或：
#   powershell -ExecutionPolicy Bypass -File .\scripts\start_xinshang_windows.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "==> 项目目录: $Root"
New-Item -ItemType Directory -Force -Path ".\logs" | Out-Null

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
  Write-Host "==> 创建虚拟环境并安装依赖..."
  python -m venv .venv
  & ".\.venv\Scripts\python.exe" -m pip install -U pip
  & ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
}

$env:CZ_SITE_PASSWORD = if ($env:CZ_SITE_PASSWORD) { $env:CZ_SITE_PASSWORD } else { "chuanzang2026" }
$env:CZ_SECRET_KEY = if ($env:CZ_SECRET_KEY) { $env:CZ_SECRET_KEY } else { "chuanzang-change-me-in-production" }

Write-Host "==> 初始化数据库..."
& ".\.venv\Scripts\python.exe" -c "import db; db.init_db(); db.seed_demo_if_empty(); print('DB ready')"

# 若 5001 已被占用，视为服务已在跑
$listening = netstat -ano | Select-String ":5001\s+.*LISTENING"
if ($listening) {
  Write-Host "==> 检测到 5001 已在监听，跳过启动 Web"
} else {
  Write-Host "==> 启动 Web（http://127.0.0.1:5001）..."
  $web = Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "-c","from app import create_app; create_app().run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)" -PassThru -WindowStyle Minimized
  $web.Id | Out-File -Encoding ascii ".\logs\web_windows.pid" -Force
  Start-Sleep -Seconds 2
}

# 可选：拉起 cloudflared（需已配置 ~/.cloudflared/config.yml）
$cfConfig = Join-Path $env:USERPROFILE ".cloudflared\config.yml"
$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if ($cloudflared -and (Test-Path $cfConfig)) {
  $cfRunning = Get-Process cloudflared -ErrorAction SilentlyContinue
  if ($cfRunning) {
    Write-Host "==> cloudflared 已在运行"
  } else {
    Write-Host "==> 启动 cloudflared 隧道..."
    Start-Process -FilePath $cloudflared.Source -ArgumentList "tunnel","--config",$cfConfig,"run","chuanzang-data" -WindowStyle Minimized
  }
  Write-Host ""
  Write-Host "外发地址（免登录）:"
  Write-Host "  https://1.chuanzangyiqu.top/evaluation/xinshang"
  Write-Host "  https://1.chuanzangyiqu.top/static/dashboards/cz1-xinshang-pingjia.html"
} else {
  Write-Host ""
  Write-Host "本机地址（免登录）:"
  Write-Host "  http://127.0.0.1:5001/evaluation/xinshang"
  Write-Host "提示：未检测到 cloudflared 配置，外网域名暂不可用。见 README「Cloudflare 绑定」。"
}

Write-Host ""
Write-Host "Done."
