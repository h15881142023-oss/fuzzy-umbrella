@echo off
REM Does not depend on the local .ps1 (that copy may still be the old PS 5.1-broken version).
cd /d "%~dp0\.."
if not exist "static\dashboards" mkdir "static\dashboards"
if not exist "docs\xinshang" mkdir "docs\xinshang"

set REF=da4e478
set REL=static/dashboards/cz1-xinshang-pingjia.html
set OUT=static\dashboards\cz1-xinshang-pingjia.html

echo Downloading dashboard HTML %REF% ...
curl.exe -L --fail --connect-timeout 20 -o "%OUT%" "https://fastly.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@%REF%/%REL%"
if errorlevel 1 curl.exe -L --fail --connect-timeout 20 -o "%OUT%" "https://gcore.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@%REF%/%REL%"
if errorlevel 1 curl.exe -L --fail --connect-timeout 20 -o "%OUT%" "https://cdn.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@%REF%/%REL%"
if errorlevel 1 curl.exe -L --fail --connect-timeout 20 -o "%OUT%" "https://raw.githubusercontent.com/h15881142023-oss/fuzzy-umbrella/%REF%/%REL%"
if errorlevel 1 (
  echo [BAD] download failed
  pause
  exit /b 1
)

copy /Y "%OUT%" "docs\xinshang\index.html" >nul
echo [OK] wrote %OUT%
echo [OK] wrote docs\xinshang\index.html
echo.
echo Next: https://1.chuanzangyiqu.top/evaluation/xinshang
echo Hard refresh: Ctrl+F5
echo.
pause
