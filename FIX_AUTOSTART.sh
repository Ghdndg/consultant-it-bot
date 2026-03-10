#!/bin/bash
# Скрипт для включения автозапуска сервисов

set -e

if [ "$EUID" -ne 0 ]; then 
    echo "Запустите с правами root: sudo ./FIX_AUTOSTART.sh"
    exit 1
fi

echo "Включение автозапуска сервисов..."
echo ""

# Включение автозапуска
systemctl enable loyalty-bot.service
systemctl enable loyalty-web.service
systemctl enable nginx.service

echo "✓ Автозапуск включен для всех сервисов"
echo ""

# Проверка статуса
echo "Статус автозапуска:"
systemctl is-enabled loyalty-bot.service && echo "✓ loyalty-bot: включен" || echo "✗ loyalty-bot: выключен"
systemctl is-enabled loyalty-web.service && echo "✓ loyalty-web: включен" || echo "✗ loyalty-web: выключен"
systemctl is-enabled nginx.service && echo "✓ nginx: включен" || echo "✗ nginx: выключен"

echo ""
echo "Готово! Сервисы будут автоматически запускаться при загрузке системы."
echo ""
