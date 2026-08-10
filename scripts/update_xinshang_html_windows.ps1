# 一键更新新商评看板 HTML（不依赖 GitHub git 协议，走 CDN 镜像）
# 用法：
#   双击 scripts\update_xinshang_html_windows.cmd
#   或：powershell -ExecutionPolicy Bypass -File .\scripts\update_xinshang_html_windows.ps1
#
# 可选：指定提交/分支
#   powershell -ExecutionPolicy Bypass -File .\scripts\update_xinshang_html_windows.ps1 -Ref f6f08cd

param(
  [string]$Ref = "cursor/cz1-merchant-dashboard-74a9"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$relPath = "static/dashboards/cz1-xinshang-pingjia.html"
$out1 = Join-Path $Root "static\dashboards\cz1-xinshang-pingjia.html"
$out2 = Join-Path $Root "docs\xinshang\index.html"
New-Item -ItemType Directory -Force -Path (Split-Path $out1) | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $out2) | Out-Null

$stamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$encRef = [Uri]::EscapeDataString($Ref)

# 多镜像：按顺序尝试（国内通常 jsDelivr / gitmirror 更稳）
$urls = @(
  "https://cdn.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@${Ref}/${relPath}?t=${stamp}",
  "https://fastly.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@${Ref}/${relPath}?t=${stamp}",
  "https://gcore.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@${Ref}/${relPath}?t=${stamp}",
  "https://raw.gitmirror.com/h15881142023-oss/fuzzy-umbrella/${Ref}/${relPath}?t=${stamp}",
  "https://ghproxy.net/https://raw.githubusercontent.com/h15881142023-oss/fuzzy-umbrella/${Ref}/${relPath}?t=${stamp}"
)

$tmp = Join-Path $env:TEMP ("cz1-xinshang-" + $stamp + ".html")
$ok = $false
$used = $null

foreach ($url in $urls) {
  Write-Host "==> try: $url"
  try {
    Invoke-WebRequest -Uri $url -OutFile $tmp -UseBasicParsing -TimeoutSec 60
    $text = Get-Content -Path $tmp -Raw -Encoding UTF8
    if ($text -notmatch "新商能力评价看板") {
      Write-Host "[WARN] downloaded but content marker missing, skip"
      continue
    }
    # 基本完整性：不能太小
    if ($text.Length -lt 5000) {
      Write-Host "[WARN] file too small ($($text.Length)), skip"
      continue
    }
    $ok = $true
    $used = $url
    break
  } catch {
    Write-Host "[WARN] failed: $($_.Exception.Message)"
  }
}

if (-not $ok) {
  Write-Host "[BAD] all mirrors failed. Check network / try -Ref <commitSha>"
  exit 1
}

# UTF-8 无 BOM 写入，避免部分浏览器异常
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($out1, (Get-Content -Path $tmp -Raw -Encoding UTF8), $utf8)
[System.IO.File]::WriteAllText($out2, (Get-Content -Path $tmp -Raw -Encoding UTF8), $utf8)
Remove-Item $tmp -Force -ErrorAction SilentlyContinue

Write-Host "[OK] wrote $out1"
Write-Host "[OK] wrote $out2"
Write-Host "[OK] source: $used"

$hit = Select-String -Path $out1 -Pattern "group-head|4n\+1货架达标数|餐饮商家渗透率"
if ($hit) {
  Write-Host "[OK] content markers found"
  $hit | Select-Object -First 3 | ForEach-Object {
    $line = $_.Line.Trim()
    if ($line.Length -gt 80) { $line = $line.Substring(0, 80) }
    Write-Host ("  line " + $_.LineNumber + ": " + $line)
  }
} else {
  Write-Host "[WARN] expected markers not found; file written but please eyeball the page"
}

Write-Host ""
Write-Host "Next: open https://1.chuanzangyiqu.top/evaluation/xinshang and hard refresh"
Write-Host "  Mac: Cmd+Shift+R    Windows: Ctrl+F5"
