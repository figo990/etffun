@echo off
chcp 65001 >nul
echo ========== ETF 数据采集器 ==========
echo.
python -m collector.main
pause
