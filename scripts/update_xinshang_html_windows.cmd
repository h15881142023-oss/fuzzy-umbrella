@echo off
cd /d "%~dp0\.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0update_xinshang_html_windows.ps1" %*
echo.
pause
