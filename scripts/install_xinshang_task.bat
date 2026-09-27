@echo off
REM 双击安装：每周二、周五 22:00 新商评自动更新（需管理员）
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_xinshang_task.ps1"
if errorlevel 1 pause
