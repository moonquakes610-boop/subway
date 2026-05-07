@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title BeijingSubwaySystem 后端
echo ============================================
echo 工程目录（必须在此运行）:
echo   %CD%
echo ============================================
echo [自检] 携带物查询逻辑（宠物/小猫应显示 likely_prohibited）...
py -3 "%CD%\scripts\verify_carry_on_e_drive.py"
if errorlevel 1 (
  echo.
  echo [失败] 请先安装依赖: py -3 -m pip install -r requirements.txt
  pause
  exit /b 1
)
echo.
echo [启动] 使用本目录下的 api_server.py（绝对路径，避免跑错副本）
echo 浏览器访问上面打印的地址；停止服务请在本窗口按 Ctrl+C
echo.
py -3 "%CD%\api_server.py"
echo.
pause
endlocal
