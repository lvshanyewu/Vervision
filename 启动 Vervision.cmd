@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-vervision.ps1"
if errorlevel 1 (
  echo.
  echo Vervision 启动失败，请查看上方错误信息。
  pause
)
