# 启动本机 Web(5001) + Cloudflare 隧道，使域名可访问
# 看板免登录：https://1.chuanzangyiqu.top/evaluation/xinshang
# 其它页面仍需站点密码
#
# 用法：
#   cd C:\Users\Administrator\Documents\fuzzy-umbrella
#   powershell -ExecutionPolicy Bypass -File .\scripts\start_domain_windows.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
New-Item -ItemType Directory -Force -Path ".\logs" | Out-Null

Write-Host "==> 项目目录: $Root"

# 依赖
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

# Web
$listening = netstat -ano | Select-String ":5001\s+.*LISTENING"
if ($listening) {
  Write-Host "==> 5001 已在监听，跳过启动 Web"
} else {
  Write-Host "==> 启动 Web http://127.0.0.1:5001 ..."
  $web = Start-Process -FilePath ".\.venv\Scripts\python.exe" `
    -ArgumentList "-c","from app import create_app; create_app().run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)" `
    -PassThru -WindowStyle Minimized
  $web.Id | Out-File -Encoding ascii ".\logs\web_windows.pid" -Force
  Start-Sleep -Seconds 2
}

# 本机验收看板
try {
  $r = Invoke-WebRequest -Uri "http://127.0.0.1:5001/evaluation/xinshang" -UseBasicParsing -TimeoutSec 8
  Write-Host "==> 本机看板 OK ($($r.StatusCode))"
} catch {
  Write-Host "==> 本机看板尚未就绪: $($_.Exception.Message)"
}

# Tunnel
$cfConfig = Join-Path $env:USERPROFILE ".cloudflared\config.yml"
$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue

if (-not $cloudflared) {
  Write-Host ""
  Write-Host "[需要处理] 未安装 cloudflared。"
  Write-Host "  1) 打开 https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/"
  Write-Host "  2) 安装 Windows 版 cloudflared，并确保命令可用"
  Write-Host "  3) 再重新运行本脚本"
  exit 1
}

if (-not (Test-Path $cfConfig)) {
  Write-Host ""
  Write-Host "[需要处理] 缺少隧道配置: $cfConfig"
  Write-Host "  可复制仓库示例后改真实 tunnel id："
  Write-Host "    copy cloudflared.config.windows.example.yml `"$cfConfig`""
  Write-Host "  并确保已执行过："
  Write-Host "    cloudflared tunnel login"
  Write-Host "    cloudflared tunnel create chuanzang-data"
  Write-Host "    cloudflared tunnel route dns chuanzang-data 1.chuanzangyiqu.top"
  exit 1
}

$cfProc = Get-Process cloudflared -ErrorAction SilentlyContinue
if ($cfProc) {
  Write-Host "==> cloudflared 已在运行"
} else {
  Write-Host "==> 启动 cloudflared ..."
  $log = Join-Path $Root "logs\cloudflared_windows.log"
  Start-Process -FilePath $cloudflared.Source `
    -ArgumentList "tunnel","--config",$cfConfig,"run","chuanzang-data" `
    -RedirectStandardOutput $log -RedirectStandardError $log `
    -WindowStyle Minimized
  Start-Sleep -Seconds 3
}

Write-Host ""
Write-Host "完成。请用浏览器验证："
Write-Host "  本机:   http://127.0.0.1:5001/evaluation/xinshang   （免登录）"
Write-Host "  域名:   https://1.chuanzangyiqu.top/evaluation/xinshang （免登录）"
Write-Host "  首页:   https://1.chuanzangyiqu.top/                  （仍要密码）"
Write-Host ""
Write-Host "若域名仍打不开，运行："
Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\check_domain_windows.ps1"
