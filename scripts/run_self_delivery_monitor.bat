@echo off
setlocal
cd /d "%~dp0.."
python scripts\self_delivery_monitor_windows.py
exit /b %ERRORLEVEL%
