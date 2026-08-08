# 检查本机 Web + Cloudflare 隧道是否可支撑域名
# 用法：
#   powershell -ExecutionPolicy Bypass -File .\scripts\check_domain_windows.ps1

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "======== 川藏一区域名自检 ========"
Write-Host "项目目录: $Root"
Write-Host ""

# 1) 看板文件
$html = Join-Path $Root "static\dashboards\cz1-xinshang-pingjia.html"
if (Test-Path $html) {
  Write-Host "[OK] 看板文件存在: $html"
} else {
  Write-Host "[缺] 看板文件不存在，请先 git fetch / restore 最新分支"
}

# 2) 本机 5001
$listen = netstat -ano | Select-String ":5001\s+.*LISTENING"
if ($listen) {
  Write-Host "[OK] 本机 5001 正在监听"
  try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:5001/evaluation/xinshang" -UseBasicParsing -TimeoutSec 8
    if ($resp.StatusCode -eq 200) {
      Write-Host "[OK] 本机看板可访问 http://127.0.0.1:5001/evaluation/xinshang （免登录）"
    } else {
      Write-Host "[异] 本机看板 HTTP 状态: $($resp.StatusCode)"
    }
  } catch {
    Write-Host "[异] 本机看板请求失败: $($_.Exception.Message)"
  }
} else {
  Write-Host "[缺] 本机 5001 未监听 —— 网站服务没开，域名一定打不开"
}

# 3) cloudflared
$cf = Get-Command cloudflared -ErrorAction SilentlyContinue
$cfConfig = Join-Path $env:USERPROFILE ".cloudflared\config.yml"
if ($cf) {
  Write-Host "[OK] 已安装 cloudflared: $($cf.Source)"
} else {
  Write-Host "[缺] 未安装 cloudflared（域名外网入口）"
}
if (Test-Path $cfConfig) {
  Write-Host "[OK] 找到隧道配置: $cfConfig"
  Get-Content $cfConfig | Select-Object -First 20 | ForEach-Object { Write-Host "    $_" }
} else {
  Write-Host "[缺] 未找到 $cfConfig"
  Write-Host "    可参考仓库 cloudflared.config.windows.example.yml"
}
$cfProc = Get-Process cloudflared -ErrorAction SilentlyContinue
if ($cfProc) {
  Write-Host "[OK] cloudflared 进程在跑 (PID: $($cfProc.Id -join ', '))"
} else {
  Write-Host "[缺] cloudflared 进程未运行 —— 域名无法连到本机"
}

Write-Host ""
Write-Host "目标外发地址（看板免登录）:"
Write-Host "  https://1.chuanzangyiqu.top/evaluation/xinshang"
Write-Host "其它页面仍走站点密码。"
Write-Host "=================================="
