@echo off
REM 经营宝同款入口：计划任务只调英文 bat，避免中文文件名乱码。
REM 日志：logs\xinshang_push_YYYYMMDD.log
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0.."
if not exist "logs" mkdir "logs"

set "PY="
if exist "%CD%\.venv\Scripts\python.exe" set "PY=%CD%\.venv\Scripts\python.exe"
if not defined PY if exist "%CD%\.venv\Scripts\python3.exe" set "PY=%CD%\.venv\Scripts\python3.exe"
if not defined PY (
  for /f "delims=" %%I in ('where python 2^>nul') do (
    echo %%I | findstr /I /C:"WindowsApps\python.exe" >nul
    if errorlevel 1 (
      set "PY=%%I"
      goto :gotpy
    )
  )
)
:gotpy
if not defined PY (
  echo [BAD] python not found > "logs\xinshang_push_last.log"
  exit /b 1
)

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "STAMP=%%I"
set "LOG=%CD%\logs\xinshang_push_%STAMP%.log"

echo ==== %DATE% %TIME% start PY=%PY% ==== >> "%LOG%"
"%PY%" "%CD%\scripts\xinshang_daily_push.py" >> "%LOG%" 2>&1
set "CODE=%ERRORLEVEL%"
echo ==== %DATE% %TIME% exit=%CODE% ==== >> "%LOG%"
exit /b %CODE%
