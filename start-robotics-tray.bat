@echo off
setlocal

set "ROOT_DIR=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%ROOT_DIR%scripts\robotics-tray.ps1" -RootDir "%ROOT_DIR%"

exit /b 0
