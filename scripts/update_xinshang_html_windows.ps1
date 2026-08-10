# Update xinshang dashboard HTML via CDN (no git required).
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\update_xinshang_html_windows.ps1
# Optional:
#   powershell -ExecutionPolicy Bypass -File .\scripts\update_xinshang_html_windows.ps1 -Ref b276487

param(
  # Prefer short commit SHA. Branch names with "/" may 403 on jsDelivr.
  [string]$Ref = "b276487"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$relPath = "static/dashboards/cz1-xinshang-pingjia.html"
$out1 = Join-Path $Root "static\dashboards\cz1-xinshang-pingjia.html"
$out2 = Join-Path $Root "docs\xinshang\index.html"
New-Item -ItemType Directory -Force -Path (Split-Path $out1) | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $out2) | Out-Null

$stamp = [int][double]::Parse((Get-Date -UFormat %s))
$tmp = Join-Path $env:TEMP ("cz1-xinshang-" + $stamp + ".html")

$urls = New-Object System.Collections.Generic.List[string]
$urls.Add("https://cdn.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@" + $Ref + "/" + $relPath + "?t=" + $stamp)
$urls.Add("https://fastly.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@" + $Ref + "/" + $relPath + "?t=" + $stamp)
$urls.Add("https://gcore.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@" + $Ref + "/" + $relPath + "?t=" + $stamp)
$urls.Add("https://raw.gitmirror.com/h15881142023-oss/fuzzy-umbrella/" + $Ref + "/" + $relPath + "?t=" + $stamp)
$urls.Add("https://ghproxy.net/https://raw.githubusercontent.com/h15881142023-oss/fuzzy-umbrella/" + $Ref + "/" + $relPath + "?t=" + $stamp)

$ok = $false
$used = $null

foreach ($url in $urls) {
  Write-Host ("==> try: " + $url)
  try {
    Invoke-WebRequest -Uri $url -OutFile $tmp -UseBasicParsing -TimeoutSec 60
    $bytes = [System.IO.File]::ReadAllBytes($tmp)
    if ($bytes.Length -lt 5000) {
      Write-Host ("[WARN] too small: " + $bytes.Length)
      continue
    }
    $text = [System.Text.Encoding]::UTF8.GetString($bytes)
    if ($text -notmatch "新商能力评价看板") {
      Write-Host "[WARN] marker missing, skip"
      continue
    }
    $ok = $true
    $used = $url
    break
  } catch {
    Write-Host ("[WARN] failed: " + $_.Exception.Message)
  }
}

if (-not $ok) {
  Write-Host "[BAD] all mirrors failed. Ask for a newer -Ref commit SHA."
  exit 1
}

$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($out1, [System.Text.Encoding]::UTF8.GetString([System.IO.File]::ReadAllBytes($tmp)), $utf8)
[System.IO.File]::WriteAllText($out2, [System.Text.Encoding]::UTF8.GetString([System.IO.File]::ReadAllBytes($tmp)), $utf8)
Remove-Item $tmp -Force -ErrorAction SilentlyContinue

Write-Host ("[OK] wrote " + $out1)
Write-Host ("[OK] wrote " + $out2)
Write-Host ("[OK] source: " + $used)

$hit = Select-String -Path $out1 -Pattern "group-head|4n\+1货架达标数|餐饮商家渗透率"
if ($hit) {
  Write-Host "[OK] content markers found"
} else {
  Write-Host "[WARN] expected markers not found; please open the page and check"
}

Write-Host ""
Write-Host "Next: https://1.chuanzangyiqu.top/evaluation/xinshang"
Write-Host "Hard refresh  Mac: Cmd+Shift+R   Windows: Ctrl+F5"
