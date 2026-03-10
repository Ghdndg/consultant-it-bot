#!/bin/bash
# Скрипт проверки статуса сервисов

echo "=========================================="
echo "  Проверка статуса сервисов"
echo "=========================================="
echo ""

# Проверка systemd сервисов
echo "1. Статус systemd сервисов:"
echo ""

if systemctl is-active --quiet loyalty-bot.service; then
    echo "✓ Telegram бот: ЗАПУЩЕН (через systemd)"
else
    echo "✗ Telegram бот: НЕ ЗАПУЩЕН"
fi

if systemctl is-active --quiet loyalty-web.service; then
    echo "✓ Веб-приложение: ЗАПУЩЕНО (через systemd)"
else
    echo "✗ Веб-приложение: НЕ ЗАПУЩЕНО"
fi

if systemctl is-active --quiet nginx.service; then
    echo "✓ Nginx: ЗАПУЩЕН (через systemd)"
else
    echo "✗ Nginx: НЕ ЗАПУЩЕН"
fi

echo ""
echo "2. Автозапуск при загрузке:"
echo ""

if systemctl is-enabled --quiet loyalty-bot.service; then
    echo "✓ Telegram бот: автозапуск ВКЛЮЧЕН"
else
    echo "✗ Telegram бот: автозапуск ВЫКЛЮЧЕН"
    echo "  Включите: sudo systemctl enable loyalty-bot.service"
fi

if systemctl is-enabled --quiet loyalty-web.service; then
    echo "✓ Веб-приложение: автозапуск ВКЛЮЧЕН"
else
    echo "✗ Веб-приложение: автозапуск ВЫКЛЮЧЕН"
    echo "  Включите: sudo systemctl enable loyalty-web.service"
fi

if systemctl is-enabled --quiet nginx.service; then
    echo "✓ Nginx: автозапуск ВКЛЮЧЕН"
else
    echo "✗ Nginx: автозапуск ВЫКЛЮЧЕН"
    echo "  Включите: sudo systemctl enable nginx.service"
fi

echo ""
echo "3. Проверка процессов:"
echo ""

# Проверка процессов Python (бот)
if pgrep -f "python.*main.py" > /dev/null; then
    echo "✓ Процесс бота найден"
else
    echo "✗ Процесс бота не найден"
fi

# Проверка процессов Python (веб)
if pgrep -f "python.*waitress_http.py" > /dev/null; then
    echo "✓ Процесс веб-приложения найден"
else
    echo "✗ Процесс веб-приложения не найден"
fi

# Проверка Nginx
if pgrep nginx > /dev/null; then
    echo "✓ Процесс Nginx найден"
else
    echo "✗ Процесс Nginx не найден"
fi

echo ""
echo "4. Проверка портов:"
echo ""

if netstat -tlnp 2>/dev/null | grep -q ":5000"; then
    echo "✓ Порт 5000 (Waitress) открыт"
else
    echo "✗ Порт 5000 (Waitress) не открыт"
fi

if netstat -tlnp 2>/dev/null | grep -q ":80"; then
    echo "✓ Порт 80 (HTTP) открыт"
else
    echo "✗ Порт 80 (HTTP) не открыт"
fi

if netstat -tlnp 2>/dev/null | grep -q ":443"; then
    echo "✓ Порт 443 (HTTPS) открыт"
else
    echo "✗ Порт 443 (HTTPS) не открыт"
fi

echo ""
echo "=========================================="
echo "  Рекомендации"
echo "=========================================="
echo ""

# Проверка, запущены ли процессы от root (плохо)
if pgrep -u root -f "python.*main.py" > /dev/null; then
    echo "⚠ ВНИМАНИЕ: Бот запущен от root! Это небезопасно."
    echo "  Остановите и запустите через systemd:"
    echo "    sudo systemctl restart loyalty-bot"
fi

if pgrep -u root -f "python.*waitress_http.py" > /dev/null; then
    echo "⚠ ВНИМАНИЕ: Веб-приложение запущено от root! Это небезопасно."
    echo "  Остановите и запустите через systemd:"
    echo "    sudo systemctl restart loyalty-web"
fi

echo ""
echo "Если сервисы запущены через systemd, можно безопасно закрыть консоль."
echo "Они продолжат работать в фоне и автоматически запустятся при перезагрузке."
echo ""
