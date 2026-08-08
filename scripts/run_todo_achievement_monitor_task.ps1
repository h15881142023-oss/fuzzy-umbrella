Param(
    [string]$ProjectRoot = "",
    [string]$PythonExe = "",
    [switch]$Headless
)

$ErrorActionPreference = "Continue"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
}

$logDir = "C:\Windows\Temp\todo_monitor"
$logFile = Join-Path $logDir "monitor.log"
$scriptPath = Join-Path $ProjectRoot "scripts\todo_achievement_monitor_windows.py"

if (!(Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

function Write-Log([string]$Message) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $logFile -Value $line -Encoding UTF8
    Write-Host $line
}

try {
    Set-Location -Path $ProjectRoot
    Write-Log "START project=$ProjectRoot"

    if ([string]::IsNullOrWhiteSpace($PythonExe)) {
        $PythonExe = (Get-Command python -ErrorAction Stop).Source
    }
    Write-Log "python=$PythonExe"
    Write-Log "script=$scriptPath"

    if (!(Test-Path $scriptPath)) {
        throw "script missing: $scriptPath"
    }

    # Headless switch kept for interface consistency; this job is API-only.
    $output = & $PythonExe $scriptPath 2>&1
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) { $exitCode = 0 }

    foreach ($line in $output) {
        Write-Log ([string]$line)
    }
    Write-Log "END exitCode=$exitCode"
    exit $exitCode
}
catch {
    Write-Log ("FATAL: " + $_.Exception.Message)
    exit 1
}
