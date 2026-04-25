@echo off
setlocal
cd /d "%~dp0\.."

echo ==========================================
echo [1/3] Python compileall
echo ==========================================
py -3 -m compileall "api_server.py" "src"
if errorlevel 1 (
  echo [FAIL] compileall failed.
  exit /b 1
)

echo.
echo ==========================================
echo [2/3] Boundary tests
echo ==========================================
py -3 scripts\run_boundary_tests.py
if errorlevel 1 (
  echo [FAIL] boundary tests failed.
  exit /b 1
)

echo.
echo ==========================================
echo [3/3] API smoke tests
echo ==========================================
py -3 scripts\run_api_smoke_tests.py
if errorlevel 1 (
  echo [FAIL] API smoke tests failed.
  exit /b 1
)

echo.
echo ==========================================
echo [PASS] All checks passed.
echo ==========================================
endlocal
exit /b 0
