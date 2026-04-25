@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3 main.py --from 西单 --to 圆明园 --out output\last_guide.txt
pause
