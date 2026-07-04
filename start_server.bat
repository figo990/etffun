@echo off
chcp 65001 >nul
echo ========== ETF Web 服务 ==========
echo.
python -m server.app
pause
