#!/bin/bash
# Быстрый скрипт обновления сервера для пользовательского интерфейса

set -e

if [ "$EUID" -ne 0 ]; then 
    echo "Запустите с правами root: sudo ./update_server_quick.sh"
    exit 1
fi

read -p "Путь к проекту (например, /opt/loyalty-bot): " PROJECT_DIR
read -p "Пользователь приложения (например, loyaltybot): " APP_USER

if [ -z "$PROJECT_DIR" ] || [ -z "$APP_USER" ]; then
    echo "Ошибка: укажите путь и пользователя"
    exit 1
fi

echo "=========================================="
echo "  Обновление сервера"
echo "=========================================="
echo ""

# Остановка сервиса
echo "Остановка веб-сервиса..."
systemctl stop loyalty-web 2>/dev/null || systemctl stop "loyalty-web-*" 2>/dev/null || true

# Проверка файлов
echo "Проверка файлов..."
REQUIRED_FILES=(
    "$PROJECT_DIR/user_web_routes.py"
    "$PROJECT_DIR/templates/user_login.html"
    "$PROJECT_DIR/templates/user_register.html"
    "$PROJECT_DIR/templates/user_base.html"
    "$PROJECT_DIR/static/manifest.json"
    "$PROJECT_DIR/static/service-worker.js"
)

MISSING_FILES=()
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        MISSING_FILES+=("$file")
    fi
done

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    echo "⚠ ВНИМАНИЕ: Отсутствуют файлы:"
    for file in "${MISSING_FILES[@]}"; do
        echo "  - $file"
    done
    echo ""
    echo "Скопируйте файлы на сервер и запустите скрипт снова"
    exit 1
fi

echo "✓ Все необходимые файлы найдены"

# Установка прав
echo "Установка прав доступа..."
chown -R $APP_USER:$APP_USER "$PROJECT_DIR"
chmod -R 755 "$PROJECT_DIR"

# Создание иконок (если скрипт есть)
if [ -f "$PROJECT_DIR/create_pwa_icons.py" ]; then
    echo "Создание иконок PWA..."
    if [ -f "$PROJECT_DIR/static/favicon.ico" ]; then
        sudo -u $APP_USER "$PROJECT_DIR/venv/bin/python3" "$PROJECT_DIR/create_pwa_icons.py" 2>/dev/null || echo "⚠ Не удалось создать иконки автоматически"
    else
        echo "⚠ favicon.ico не найден, создайте иконки вручную"
    fi
fi

# Проверка иконок
if [ ! -f "$PROJECT_DIR/static/icon-192.png" ] || [ ! -f "$PROJECT_DIR/static/icon-512.png" ]; then
    echo "⚠ ВНИМАНИЕ: Иконки PWA не найдены!"
    echo "Создайте вручную:"
    echo "  - $PROJECT_DIR/static/icon-192.png (192x192)"
    echo "  - $PROJECT_DIR/static/icon-512.png (512x512)"
    echo ""
    read -p "Продолжить без иконок? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Запуск сервиса
echo "Запуск веб-сервиса..."
systemctl start loyalty-web 2>/dev/null || systemctl start "loyalty-web-*" 2>/dev/null || true

# Проверка статуса
sleep 2
echo ""
echo "Проверка статуса..."
if systemctl is-active --quiet loyalty-web 2>/dev/null || systemctl is-active --quiet "loyalty-web-*" 2>/dev/null; then
    echo "✓ Веб-сервис запущен"
else
    echo "✗ Веб-сервис не запущен. Проверьте логи:"
    echo "  sudo journalctl -u loyalty-web -n 50"
fi

echo ""
echo "=========================================="
echo "  Обновление завершено!"
echo "=========================================="
echo ""
echo "Проверьте работу:"
echo "  https://ваш_домен.ru/user/login"
echo ""
