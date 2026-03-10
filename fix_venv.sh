#!/bin/bash
# Скрипт исправления виртуального окружения

set -e

if [ "$EUID" -ne 0 ]; then 
    echo "Запустите с правами root: sudo ./fix_venv.sh"
    exit 1
fi

read -p "Путь к проекту (например, /opt/loyalty-lev): " PROJECT_DIR
read -p "Пользователь приложения (например, loyalty-lev): " APP_USER

if [ -z "$PROJECT_DIR" ] || [ -z "$APP_USER" ]; then
    echo "Ошибка: укажите путь и пользователя"
    exit 1
fi

echo "Исправление виртуального окружения в $PROJECT_DIR..."

# Удаление старого окружения
if [ -d "$PROJECT_DIR/venv" ]; then
    echo "Удаление старого виртуального окружения..."
    rm -rf "$PROJECT_DIR/venv"
fi

# Создание нового
echo "Создание нового виртуального окружения..."
sudo -u $APP_USER python3 -m venv "$PROJECT_DIR/venv"

# Установка зависимостей
echo "Установка зависимостей..."
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    sudo -u $APP_USER "$PROJECT_DIR/venv/bin/pip" install --upgrade pip
    sudo -u $APP_USER "$PROJECT_DIR/venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
else
    echo "requirements.txt не найден, устанавливаю базовые зависимости..."
    sudo -u $APP_USER "$PROJECT_DIR/venv/bin/pip" install --upgrade pip
    sudo -u $APP_USER "$PROJECT_DIR/venv/bin/pip" install python-telegram-bot SQLAlchemy python-dotenv qrcode[pil] pillow Flask waitress requests
fi

echo "Готово! Виртуальное окружение исправлено."
