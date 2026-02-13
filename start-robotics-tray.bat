@echo off
setlocal

set "ROOT_DIR=S:\robotics-serverV2"
powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%ROOT_DIR%\scripts\robotics-tray.ps1"

exit /b 0

