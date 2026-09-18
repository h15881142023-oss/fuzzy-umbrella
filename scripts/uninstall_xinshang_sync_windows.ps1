# Stop and remove xinshang auto-sync leftovers on this PC.
#   powershell -ExecutionPolicy Bypass -File .\scripts\uninstall_xinshang_sync_windows.ps1

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "==> stop xinshang clock processes"
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -and ($_.CommandLine -like "*xinshang_clock_windows.py*") } |
  ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host ("[OK] killed pid=" + $_.ProcessId)
  }

Write-Host "==> remove Startup shortcut"
$lnk = Join-Path ([Environment]::GetFolderPath("Startup")) "ChuanzangXinshangClock.lnk"
if (Test-Path $lnk) {
  Remove-Item $lnk -Force
  Write-Host "[OK] removed $lnk"
} else {
  Write-Host "[INFO] no Startup shortcut"
}

Write-Host "==> remove local helper cmd files"
@(
  "scripts\run_xinshang_sync_windows.cmd",
  "scripts\run_xinshang_clock_windows.cmd"
) | ForEach-Object {
  $p = Join-Path $Root $_
  if (Test-Path $p) {
    Remove-Item $p -Force
    Write-Host "[OK] removed $p"
  }
}

Write-Host "==> try delete scheduled tasks (ignore if denied)"
foreach ($name in @("ChuanzangXinshangSync", "ChuanzangXinshangSyncFri")) {
  try {
    Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction Stop
    Write-Host "[OK] unregistered $name"
  } catch {
    schtasks /Delete /TN $name /F 2>$null | Out-Null
  }
}

Write-Host ""
Write-Host "Done. Dashboard stays on detail HTML; no auto sync."
Write-Host "If Web5001 still runs old run_web_windows.py with clock thread, restart it:"
Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\start_domain_windows.ps1"
