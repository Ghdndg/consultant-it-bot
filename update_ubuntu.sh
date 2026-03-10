#!/bin/bash
# Скрипт обновления приложения на Ubuntu

set -e

PROJECT_DIR="/opt/loyalty-bot"  # Измените на ваш путь
APP_USER="loyaltybot"

echo "=========================================="
echo "  Обновление программы лояльности"
echo "=========================================="
echo ""

# Проверка прав
if [ "$EUID" -ne 0 ]; then 
    echo "Запустите с правами root: sudo ./update_ubuntu.sh"
    exit 1
fi

# Остановка сервисов
echo "Остановка сервисов..."
systemctl stop loyalty-bot.service
systemctl stop loyalty-web.service

# Обновление кода (если используется git)
if [ -d "$PROJECT_DIR/.git" ]; then
    echo "Обновление кода из git..."
    cd "$PROJECT_DIR"
    sudo -u $APP_USER git pull
fi

# Обновление зависимостей
echo "Обновление Python зависимостей..."
sudo -u $APP_USER "$PROJECT_DIR/venv/bin/pip" install --upgrade pip
sudo -u $APP_USER "$PROJECT_DIR/venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt"

# Применение миграций БД (если есть)
# sudo -u $APP_USER "$PROJECT_DIR/venv/bin/python3" "$PROJECT_DIR/migrate.py"

# Перезапуск сервисов
echo "Запуск сервисов..."
systemctl start loyalty-bot.service
systemctl start loyalty-web.service

# Проверка статуса
sleep 3
echo ""
echo "Статус сервисов:"
systemctl status loyalty-bot.service --no-pager -l
systemctl status loyalty-web.service --no-pager -l

echo ""
echo "Обновление завершено!"
