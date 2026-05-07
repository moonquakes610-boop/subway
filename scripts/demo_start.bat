@echo off
setlocal
cd /d "%~dp0\.."
set "API_PY=%CD%\api_server.py"

echo [1/3] Starting backend server...
echo     使用: %API_PY%
start "BeijingSubwaySystem API" cmd /k "py -3 ""%API_PY%"""

echo [2/3] Waiting server warm-up...
ping 127.0.0.1 -n 3 >nul

echo [3/3] Opening pages...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process 'http://127.0.0.1:8765/'; Start-Process 'http://127.0.0.1:8765/app.html'" >nul 2>&1
if errorlevel 1 (
  start "" "http://127.0.0.1:8765/"
  start "" "http://127.0.0.1:8765/app.html"
)

echo Done. If browser was not opened, copy URLs manually:
echo   http://127.0.0.1:8765/
echo   http://127.0.0.1:8765/app.html
endlocal
