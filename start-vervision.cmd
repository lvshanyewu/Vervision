@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-vervision.ps1"
if errorlevel 1 (
  echo.
  echo Vervision failed to start. Review the error above.
  pause
)
