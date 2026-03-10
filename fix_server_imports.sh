#!/bin/bash
# Скрипт исправления проблем с импортами на сервере

set -e

PROJECT_DIR="/home"

echo "=========================================="
echo "  Исправление проблем с импортами"
echo "=========================================="
echo ""

cd "$PROJECT_DIR"

# 1. Проверка виртуального окружения
echo "1. Проверка виртуального окружения..."
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo "ОШИБКА: Виртуальное окружение не найдено!"
    echo "Создаю виртуальное окружение..."
    python3 -m venv "$PROJECT_DIR/venv"
    echo "✓ Виртуальное окружение создано"
fi

# 2. Установка зависимостей
echo ""
echo "2. Установка зависимостей..."
"$PROJECT_DIR/venv/bin/pip" install --upgrade pip
"$PROJECT_DIR/venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt"

# 3. Проверка Flask
echo ""
echo "3. Проверка Flask..."
if ! "$PROJECT_DIR/venv/bin/python3" -c "import flask" 2>/dev/null; then
    echo "Установка Flask..."
    "$PROJECT_DIR/venv/bin/pip" install Flask
fi

# 4. Проверка импорта user_web_routes
echo ""
echo "4. Проверка импорта user_web_routes..."
if "$PROJECT_DIR/venv/bin/python3" -c "import user_web_routes" 2>&1; then
    echo "✓ Импорт user_web_routes успешен"
else
    echo "✗ Ошибка импорта user_web_routes"
    echo "Проверьте наличие файла: $PROJECT_DIR/user_web_routes.py"
    exit 1
fi

# 5. Проверка импорта cashier_admin_stable
echo ""
echo "5. Проверка импорта cashier_admin_stable..."
if "$PROJECT_DIR/venv/bin/python3" -c "import cashier_admin_stable" 2>&1; then
    echo "✓ Импорт cashier_admin_stable успешен"
else
    echo "✗ Ошибка импорта cashier_admin_stable"
    echo "Проверьте файл: $PROJECT_DIR/cashier_admin_stable.py"
    exit 1
fi

# 6. Создание недостающих файлов
echo ""
echo "6. Проверка статических файлов..."

# Создание директорий если нужно
mkdir -p "$PROJECT_DIR/static/css"

# Создание manifest.json если нет
if [ ! -f "$PROJECT_DIR/static/manifest.json" ]; then
    echo "Создание manifest.json..."
    cat > "$PROJECT_DIR/static/manifest.json" << 'EOF'
{
  "name": "Программа лояльности",
  "short_name": "Лояльность",
  "description": "Программа лояльности - баллы, покупки, QR-код",
  "start_url": "/user/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#198754",
  "orientation": "portrait-primary",
  "icons": [
    {
      "src": "/static/favicon.ico",
      "sizes": "48x48",
      "type": "image/x-icon"
    }
  ]
}
EOF
    echo "✓ manifest.json создан"
fi

# Создание service-worker.js если нет
if [ ! -f "$PROJECT_DIR/static/service-worker.js" ]; then
    echo "Создание service-worker.js..."
    cat > "$PROJECT_DIR/static/service-worker.js" << 'EOF'
// Service Worker для PWA
const CACHE_NAME = 'loyalty-app-v1';
const urlsToCache = [
  '/',
  '/user/',
  '/user/login',
  '/static/css/style.css',
  '/static/favicon.ico',
  '/static/manifest.json'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request)
      .then((response) => response || fetch(event.request))
  );
});
EOF
    echo "✓ service-worker.js создан"
fi

# Создание pwa.css если нет
if [ ! -f "$PROJECT_DIR/static/css/pwa.css" ]; then
    echo "Создание pwa.css..."
    cat > "$PROJECT_DIR/static/css/pwa.css" << 'EOF'
/* Стили для PWA на iOS */
@media all and (display-mode: standalone) {
    body {
        -webkit-touch-callout: none;
        -webkit-user-select: none;
        user-select: none;
    }
}
EOF
    echo "✓ pwa.css создан"
fi

# 7. Создание простых иконок если нет
if [ ! -f "$PROJECT_DIR/static/icon-192.png" ] || [ ! -f "$PROJECT_DIR/static/icon-512.png" ]; then
    echo ""
    echo "7. Создание простых иконок..."
    if [ -f "$PROJECT_DIR/static/favicon.ico" ]; then
        "$PROJECT_DIR/venv/bin/python3" create_pwa_icons.py 2>/dev/null || echo "⚠ Не удалось создать иконки автоматически"
    else
        echo "⚠ favicon.ico не найден, создайте иконки вручную"
    fi
fi

echo ""
echo "=========================================="
echo "  Проверка завершена!"
echo "=========================================="
echo ""
