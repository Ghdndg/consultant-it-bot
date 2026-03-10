@echo off
chcp 65001 >nul
title Запуск бекенда через Waitress (HTTP:5000)

echo Запуск Flask-приложения через Waitress на http://127.0.0.1:5000

REM Проверка прав не требуется, порт 5000 не привилегированный

echo Устанавливаем зависимости (waitress)...
py -3.13 -m pip install waitress >nul 2>&1

echo Запускаем...
py -3.13 waitress_http.py

echo.
echo Окно можно закрыть для остановки сервера.
pause
