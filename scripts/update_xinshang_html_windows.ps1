# Update xinshang dashboard HTML via CDN (no git required).
# Windows PowerShell 5.1 compatible:
#   - do NOT use Generic.List[string]
#   - do NOT use -f format with {0} inside @( )
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\update_xinshang_html_windows.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\update_xinshang_html_windows.ps1 -Ref 0e446d1

param(
  [string]$Ref = "da4e478"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$relPath = "static/dashboards/cz1-xinshang-pingjia.html"
$out1 = Join-Path $Root "static\dashboards\cz1-xinshang-pingjia.html"
$out2 = Join-Path $Root "docs\xinshang\index.html"
New-Item -ItemType Directory -Force -Path (Split-Path $out1) | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $out2) | Out-Null

$stamp = Get-Date -Format "yyyyMMddHHmmss"
$tmp = Join-Path $env:TEMP ("cz1-xinshang-" + $stamp + ".html")

# jsDelivr needs commit SHA. Branch names containing "/" often return Forbidden.
$u1 = "https://fastly.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@" + $Ref + "/" + $relPath + "?t=" + $stamp
$u2 = "https://gcore.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@" + $Ref + "/" + $relPath + "?t=" + $stamp
$u3 = "https://cdn.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@" + $Ref + "/" + $relPath + "?t=" + $stamp
$u4 = "https://raw.gitmirror.com/h15881142023-oss/fuzzy-umbrella/" + $Ref + "/" + $relPath + "?t=" + $stamp
$u5 = "https://ghproxy.net/https://raw.githubusercontent.com/h15881142023-oss/fuzzy-umbrella/" + $Ref + "/" + $relPath + "?t=" + $stamp
$urls = @($u1, $u2, $u3, $u4, $u5)

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
$body = [System.IO.File]::ReadAllBytes($tmp)
$text = [System.Text.Encoding]::UTF8.GetString($body)
[System.IO.File]::WriteAllText($out1, $text, $utf8)
[System.IO.File]::WriteAllText($out2, $text, $utf8)
Remove-Item $tmp -Force -ErrorAction SilentlyContinue

Write-Host ("[OK] wrote " + $out1)
Write-Host ("[OK] wrote " + $out2)
Write-Host ("[OK] source: " + $used)
Write-Host ""
Write-Host "Next: https://1.chuanzangyiqu.top/evaluation/xinshang"
Write-Host "Hard refresh  Windows: Ctrl+F5"
