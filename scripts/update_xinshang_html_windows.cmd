@echo off
cd /d "%~dp0\.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0update_xinshang_html_windows.ps1" %*
if errorlevel 1 (
  echo.
  echo Script failed. If you saw an unexpected ")" error, the local .ps1 is the old Windows PowerShell 5.1-incompatible copy.
  echo Paste the one-liner from the agent instead, or replace this .ps1 from GitHub then retry.
)
echo.
pause
