@echo off
chcp 65001 >nul
title Остановка Apache и Waitress

echo ============================================
echo   Остановка Apache и Waitress
echo ============================================
echo.

REM Остановка Apache
echo [1/2] Остановка Apache...
taskkill /f /im httpd.exe >nul 2>&1
if %errorLevel% equ 0 (
    echo OK - Apache остановлен
) else (
    echo OK - Apache не был запущен
)
echo.

REM Остановка Waitress (Python процессы по названию окна)
echo [2/2] Остановка Waitress...
taskkill /f /fi "WINDOWTITLE eq Запуск бекенда через Waitress*" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq Waitress Server*" >nul 2>&1

REM Останавливаем процессы, использующие порт 5000 (Waitress)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5000 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)

echo OK - Waitress остановлен
echo.

echo ============================================
echo   ГОТОВО!
echo ============================================
echo.
echo Все серверы остановлены
echo.
pause
