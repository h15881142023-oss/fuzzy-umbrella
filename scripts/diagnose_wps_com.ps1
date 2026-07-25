# Diagnose WPS/Excel COM on this machine (run in NORMAL PowerShell, not admin).
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\diagnose_wps_com.ps1

$ErrorActionPreference = "Continue"
Write-Host "=== WPS/Excel COM diagnose ==="
Write-Host ("User: {0}" -f $env:USERNAME)
Write-Host ("Elevated: {0}" -f ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))
Write-Host ""

Write-Host "-- ProgIDs in registry --"
$names = @()
try {
    Get-ChildItem Registry::HKEY_CLASSES_ROOT | Where-Object {
        $_.PSChildName -like "Ket.Application*" -or
        $_.PSChildName -like "et.Application*" -or
        $_.PSChildName -like "Excel.Application*"
    } | ForEach-Object {
        $names += $_.PSChildName
        Write-Host ("  HKCR\{0}" -f $_.PSChildName)
    }
} catch {
    Write-Host ("  registry scan fail: {0}" -f $_.Exception.Message)
}
if (-not $names) { Write-Host "  (none found)" }

Write-Host ""
Write-Host "-- Try CreateObject --"
foreach ($prog in @("Ket.Application", "et.Application", "Excel.Application") + $names) {
    try {
        $app = New-Object -ComObject $prog
        Write-Host ("  OK  {0}" -f $prog)
        try { $app.Quit() } catch {}
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null
    } catch {
        Write-Host ("  FAIL {0} -> {1}" -f $prog, $_.Exception.Message)
    }
}

Write-Host ""
Write-Host "-- Find et.exe / wps.exe --"
$patterns = @(
    "$env:LOCALAPPDATA\Kingsoft\WPS Office\*\office6\et.exe",
    "$env:ProgramFiles\Kingsoft\WPS Office\*\office6\et.exe",
    "${env:ProgramFiles(x86)}\Kingsoft\WPS Office\*\office6\et.exe",
    "$env:LOCALAPPDATA\Kingsoft\WPS Office\*\office6\wps.exe",
    "$env:ProgramFiles\Kingsoft\WPS Office\*\office6\wps.exe"
)
$found = @()
foreach ($p in $patterns) {
    Get-Item $p -ErrorAction SilentlyContinue | ForEach-Object {
        $found += $_.FullName
        Write-Host ("  {0}" -f $_.FullName)
    }
}
if (-not $found) { Write-Host "  (et.exe not found — WPS maybe not installed)" }

Write-Host ""
if ($found) {
    Write-Host "Next: try register COM (NORMAL user window):"
    Write-Host ("  & `"{0}`" /regserver" -f $found[0])
    Write-Host "Then reopen WPS spreadsheet once, and rerun profit fill."
} else {
    Write-Host "Next: install/repair WPS Office (表格), open 表格 once, then rerun diagnose."
}
Write-Host ""
Write-Host "Python check (ProgID + CLSID):"
Write-Host "  .\.venv\Scripts\python.exe -c `"import sys; from lr.export_kanban_com import _resolve_clsid,_candidate_prog_ids; print('py', 64 if sys.maxsize>2**32 else 32); print([(p,_resolve_clsid(p)) for p in _candidate_prog_ids()[:6]])`""
Write-Host "If PowerShell OK but Python FAIL: export will use PS1 first (LR_KANBAN_EXPORT=ps1,com)."
Write-Host "Retry filled workbook only:"
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\run_lr_kanban_push_existing.ps1 -TargetDate 2026-07-24"
