@echo off
chcp 65001 >nul
title Запуск Apache и Waitress

echo ============================================
echo   Запуск Apache и Waitress
echo ============================================
echo.

REM Проверка наличия Apache
if not exist "C:\Apache24\bin\httpd.exe" (
    echo ОШИБКА: Apache не найден в C:\Apache24\bin\httpd.exe
    echo Убедитесь, что Apache установлен.
    pause
    exit /b 1
)

REM Шаг 1: Проверка синтаксиса конфигурации Apache
echo [1/4] Проверка конфигурации Apache...
"C:\Apache24\bin\httpd.exe" -t >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo ОШИБКА: Конфигурация Apache некорректна!
    echo Проверяем детали...
    "C:\Apache24\bin\httpd.exe" -t
    echo.
    echo Исправьте ошибки в конфигурации и попробуйте снова.
    pause
    exit /b 1
)
echo OK - Синтаксис конфигурации корректен
echo.

REM Шаг 2: Остановка Apache (если запущен)
echo [2/4] Остановка Apache (если запущен)...
taskkill /f /im httpd.exe >nul 2>&1
if %errorLevel% equ 0 (
    echo OK - Apache остановлен
) else (
    echo OK - Apache не был запущен
)
timeout /t 1 /nobreak >nul
echo.

REM Шаг 3: Запуск Apache
echo [3/4] Запуск Apache...
start "Apache Server" "C:\Apache24\bin\httpd.exe"
timeout /t 2 /nobreak >nul
echo OK - Apache запущен
echo.

REM Шаг 4: Запуск Waitress
echo [4/4] Запуск Waitress...
echo.
start "Waitress Server" "%~dp0start_waitress.bat"
timeout /t 1 /nobreak >nul
echo OK - Waitress запускается
echo.

echo ============================================
echo   ГОТОВО!
echo ============================================
echo.
echo Apache и Waitress запущены
echo.
echo Архитектура:
echo   Apache (порты 80/443) → Waitress (127.0.0.1:5000) → Flask
echo.
echo Для остановки используйте: stop_servers.bat
echo Или закройте окна Apache и Waitress
echo.
pause
