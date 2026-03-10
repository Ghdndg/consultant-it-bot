#!/bin/bash
# Скрипт обновления для проекта в /home

set -e

PROJECT_DIR="/home"
APP_USER="loyaltybot"

echo "=========================================="
echo "  Обновление пользовательского интерфейса"
echo "=========================================="
echo ""

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

# Создание иконок PWA
echo ""
echo "Создание иконок PWA..."
if [ -f "$PROJECT_DIR/create_pwa_icons.py" ] && [ -f "$PROJECT_DIR/static/favicon.ico" ]; then
    # Установка Pillow если нужно
    if ! "$PROJECT_DIR/venv/bin/python3" -c "import PIL" 2>/dev/null; then
        echo "Установка Pillow..."
        "$PROJECT_DIR/venv/bin/pip" install Pillow
    fi
    
    # Создание иконок
    cd "$PROJECT_DIR"
    "$PROJECT_DIR/venv/bin/python3" create_pwa_icons.py
    
    if [ -f "$PROJECT_DIR/static/icon-192.png" ] && [ -f "$PROJECT_DIR/static/icon-512.png" ]; then
        echo "✓ Иконки созданы"
    else
        echo "⚠ Иконки не созданы, создайте вручную"
    fi
else
    echo "⚠ Скрипт создания иконок или favicon.ico не найден"
    echo "Создайте иконки вручную:"
    echo "  - $PROJECT_DIR/static/icon-192.png (192x192)"
    echo "  - $PROJECT_DIR/static/icon-512.png (512x512)"
fi

# Установка прав
echo ""
echo "Установка прав доступа..."
if id "$APP_USER" &>/dev/null; then
    chown -R $APP_USER:$APP_USER "$PROJECT_DIR"
    echo "✓ Права установлены"
else
    echo "⚠ Пользователь $APP_USER не найден, пропускаем установку прав"
fi

chmod -R 755 "$PROJECT_DIR"

# Перезапуск сервиса
echo ""
echo "Перезапуск веб-сервиса..."
systemctl restart loyalty-web.service

# Проверка статуса
sleep 2
echo ""
echo "Проверка статуса..."
if systemctl is-active --quiet loyalty-web.service; then
    echo "✓ Веб-сервис запущен"
else
    echo "✗ Веб-сервис не запущен"
    echo "Проверьте логи: sudo journalctl -u loyalty-web -n 50"
fi

echo ""
echo "=========================================="
echo "  Обновление завершено!"
echo "=========================================="
echo ""
echo "Проверьте работу:"
echo "  https://optobuvfeo.ru/user/login"
echo ""
