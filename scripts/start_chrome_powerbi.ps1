# Start Chrome with CDP 9222 for Power BI (Windows)
param(
    [string]$Url = "https://app.powerbi.com/reportEmbed?reportId=002a894f-ba61-4a4c-b99c-b275e5e4142f&autoAuth=true&ctid=7c792a97-2300-4444-aa97-172fed9b0501"
)

$ErrorActionPreference = "Stop"
$DebugPort = 9222
$UserDataDir = Join-Path $env:LOCALAPPDATA "Google\ChromeAutomation"

$chromeCandidates = @(
    "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)
$Chrome = $chromeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Chrome) {
    throw "Google Chrome not found. Please install Chrome."
}

# If CDP already up, reuse it
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$DebugPort/json/version" -TimeoutSec 2 -UseBasicParsing
    if ($resp.StatusCode -eq 200) {
        Write-Host "CDP $DebugPort already running."
        exit 0
    }
} catch {}

New-Item -ItemType Directory -Force -Path $UserDataDir | Out-Null
Write-Host "Starting Chrome CDP=$DebugPort profile=$UserDataDir"
Start-Process -FilePath $Chrome -ArgumentList @(
    "--remote-debugging-port=$DebugPort",
    "--remote-allow-origins=*",
    "--user-data-dir=`"$UserDataDir`"",
    "--profile-directory=Default",
    "--no-first-run",
    "--no-default-browser-check",
    $Url
)

for ($i = 1; $i -le 30; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$DebugPort/json/version" -TimeoutSec 2 -UseBasicParsing
        if ($resp.StatusCode -eq 200) {
            Write-Host "OK: Chrome CDP ready on $DebugPort"
            Write-Host "First time: login Power BI in that Chrome window, then re-run the morning script."
            exit 0
        }
    } catch {}
    Start-Sleep -Seconds 1
}

throw "Chrome CDP failed to start on port $DebugPort"
