# 新商评外发页 — 一键全量同步（Windows PowerShell 5.1）
#
# 顺序：
#   1) 从 GitHub（jsDelivr）拉最新看板 HTML 到本机
#   2) Power BI 抓取「月在线商家数」
#   3) 初心 Metabase 主看板（五城指标、环比、测试成绩）
#   4) 同分群数值对比（117 城名单等）
#
# 用法（在仓库根目录执行）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\sync_xinshang_full_windows.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\sync_xinshang_full_windows.ps1 -Ref 48bd699
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\sync_xinshang_full_windows.ps1 -Ref 48bd699 -SkipHtmlDownload
#
# 外发页：https://1.chuanzangyiqu.top/evaluation/xinshang
# Power BI 需 Chrome CDP 9222；若登录弹窗，用 qiaoxh@ppu.powerbi.bi 登录后重跑。

param(
  [string]$Ref = "48bd699",
  [string]$Date = "",
  [switch]$SkipHtmlDownload
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "========================================"
Write-Host " 新商评一键全量同步"
Write-Host " Ref: $Ref"
Write-Host " Root: $Root"
Write-Host "========================================"
Write-Host ""

if (-not $SkipHtmlDownload) {
  Write-Host "==> [1/4] 从 GitHub 拉最新看板 HTML"
  $updater = Join-Path $Root "scripts\update_xinshang_html_windows.ps1"
  if (-not (Test-Path $updater)) {
    Write-Host "[WARN] 缺少 update_xinshang_html_windows.ps1，尝试 bootstrap..."
    $bootstrap = Join-Path $Root "scripts\bootstrap_xinshang_html_windows.ps1"
    if (Test-Path $bootstrap) {
      & powershell -NoProfile -ExecutionPolicy Bypass -File $bootstrap -Ref $Ref
      if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    } else {
      Write-Host "[BAD] 找不到 HTML 更新脚本，请 git pull 或手动下载 scripts。"
      exit 1
    }
  } else {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $updater -Ref $Ref
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  }
  Write-Host ""
} else {
  Write-Host "==> [1/4] 跳过 HTML 下载（-SkipHtmlDownload）"
  Write-Host ""
}

Write-Host "==> [2/4] Power BI 月在线商家数 + 初心主看板"
$biArgs = @()
if ($Date) { $biArgs += @("-Date", $Date) }
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\sync_xinshang_bi_windows.ps1") @biArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host ""

Write-Host "==> [3/4] 同分群数值对比"
$peerArgs = @()
if ($Date) { $peerArgs += @("-Date", $Date) }
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\sync_peer_compare_windows.ps1") @peerArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host ""

Write-Host "==> [4/4] 完成"
Write-Host ""
Write-Host "[OK] 全量同步完成。"
Write-Host "     外发页: https://1.chuanzangyiqu.top/evaluation/xinshang"
Write-Host "     请 Ctrl+F5 硬刷新。"
Write-Host "     若 502: powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_domain_windows.ps1"
exit 0
