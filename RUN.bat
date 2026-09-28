@echo off
rem 唔使安裝、唔使管理員權限, 雙擊即跑
chcp 65001 >nul
cd /d %~dp0
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 report.py
) else (
    python report.py
)
echo.
echo 完成, 按任意鍵關閉...
pause >nul
