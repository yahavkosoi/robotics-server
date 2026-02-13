@echo off
setlocal

rem ===== Config =====
set "ROOT_DIR=S:\robotics-serverV2"
set "WEB_DIR=%ROOT_DIR%\web"
set "BACKEND_PORT=8080"
set "HEALTH_URL=http://127.0.0.1:%BACKEND_PORT%/api/health"
set "MAX_WAIT_SECONDS=90"

echo [1/3] Starting backend...
start "Robotics Backend" cmd /k "cd /d %ROOT_DIR% && call venv\Scripts\activate.bat && python -m server.run"

echo [2/3] Waiting for backend health check: %HEALTH_URL%
powershell -NoProfile -Command ^
  "$ok=$false; for ($i=0; $i -lt %MAX_WAIT_SECONDS%; $i++) { try { Invoke-WebRequest -UseBasicParsing '%HEALTH_URL%' | Out-Null; $ok=$true; break } catch { Start-Sleep -Seconds 1 } }; if (-not $ok) { exit 1 }"

if errorlevel 1 (
  echo Backend did not become ready within %MAX_WAIT_SECONDS% seconds.
  echo Web dev server was not started.
  exit /b 1
)

echo [3/3] Starting web...
start "Robotics Web" cmd /k "cd /d %WEB_DIR% && npm install && npm run dev"

echo Done. Backend and web windows are running.
exit /b 0

