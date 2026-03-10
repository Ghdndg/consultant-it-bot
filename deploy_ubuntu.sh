#!/bin/bash
# Скрипт развертывания бота и веб-приложения на Ubuntu

set -e  # Остановка при ошибке

echo "=========================================="
echo "  Развертывание программы лояльности"
echo "=========================================="
echo ""

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция для вывода сообщений
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    error "Запустите скрипт с правами root: sudo ./deploy_ubuntu.sh"
    exit 1
fi

# Получаем путь к директории проекта
PROJECT_DIR=$(pwd)
if [ ! -f "$PROJECT_DIR/main.py" ]; then
    error "Скрипт должен быть запущен из корневой директории проекта!"
    exit 1
fi

info "Директория проекта: $PROJECT_DIR"

# Шаг 1: Обновление системы
info "Шаг 1: Обновление системы..."
apt-get update
apt-get upgrade -y

# Шаг 2: Установка Python и зависимостей
info "Шаг 2: Установка Python и зависимостей..."
apt-get install -y python3 python3-pip python3-venv python3-dev
apt-get install -y nginx supervisor
apt-get install -y sqlite3
apt-get install -y git curl wget

# Шаг 3: Создание пользователя для приложения
info "Шаг 3: Создание пользователя для приложения..."
APP_USER="loyaltybot"
if ! id "$APP_USER" &>/dev/null; then
    useradd -r -s /bin/bash -d "$PROJECT_DIR" -m "$APP_USER"
    info "Пользователь $APP_USER создан"
else
    info "Пользователь $APP_USER уже существует"
fi

# Шаг 4: Настройка прав доступа
info "Шаг 4: Настройка прав доступа..."
chown -R $APP_USER:$APP_USER "$PROJECT_DIR"
chmod +x "$PROJECT_DIR/deploy_ubuntu.sh"

# Шаг 5: Создание виртуального окружения
info "Шаг 5: Создание виртуального окружения..."
if [ ! -d "$PROJECT_DIR/venv" ]; then
    sudo -u $APP_USER python3 -m venv "$PROJECT_DIR/venv"
    info "Виртуальное окружение создано"
else
    info "Виртуальное окружение уже существует"
fi

# Шаг 6: Установка Python зависимостей
info "Шаг 6: Установка Python зависимостей..."
sudo -u $APP_USER "$PROJECT_DIR/venv/bin/pip" install --upgrade pip
sudo -u $APP_USER "$PROJECT_DIR/venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt"

# Шаг 7: Создание директорий для логов и бэкапов
info "Шаг 7: Создание директорий..."
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/backups"
chown -R $APP_USER:$APP_USER "$PROJECT_DIR/logs"
chown -R $APP_USER:$APP_USER "$PROJECT_DIR/backups"

# Шаг 8: Создание .env файла (если не существует)
info "Шаг 8: Настройка конфигурации..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
    warn ".env файл не найден. Создайте его вручную с настройками:"
    echo "  BOT_TOKEN=ваш_токен_бота"
    echo "  ADMIN_USER_ID=ваш_telegram_id"
    echo "  BACKUP_CHAT_ID=ваш_chat_id"
    echo ""
    echo "Пример:"
    echo "  nano $PROJECT_DIR/.env"
else
    info ".env файл найден"
fi

# Шаг 9: Создание systemd сервисов
info "Шаг 9: Создание systemd сервисов..."

# Сервис для Telegram бота
cat > /etc/systemd/system/loyalty-bot.service << EOF
[Unit]
Description=Telegram Loyalty Bot
After=network.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin"
ExecStart=$PROJECT_DIR/venv/bin/python3 $PROJECT_DIR/main.py
Restart=always
RestartSec=10
StandardOutput=append:$PROJECT_DIR/logs/bot.log
StandardError=append:$PROJECT_DIR/logs/bot_error.log

[Install]
WantedBy=multi-user.target
EOF

# Сервис для веб-приложения (Waitress)
cat > /etc/systemd/system/loyalty-web.service << EOF
[Unit]
Description=Loyalty Web Application (Waitress)
After=network.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin"
ExecStart=$PROJECT_DIR/venv/bin/python3 $PROJECT_DIR/waitress_http.py
Restart=always
RestartSec=10
StandardOutput=append:$PROJECT_DIR/logs/web.log
StandardError=append:$PROJECT_DIR/logs/web_error.log

[Install]
WantedBy=multi-user.target
EOF

# Шаг 10: Настройка Nginx
info "Шаг 10: Настройка Nginx..."

# Создание конфигурации Nginx
# Запрашиваем домен у пользователя
read -p "Введите домен (например, optobuvfeo.ru): " DOMAIN
DOMAIN=${DOMAIN:-optobuvfeo.ru}

# Установка пакета для самоподписанных сертификатов (если нужно)
if [ ! -f "/etc/ssl/certs/ssl-cert-snakeoil.pem" ]; then
    info "Установка пакета для временных SSL сертификатов..."
    apt-get install -y ssl-cert
fi

cat > /etc/nginx/sites-available/loyalty << EOF
# HTTP - временная конфигурация (до установки SSL)
# После установки SSL будет добавлен редирект на HTTPS
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;

    # Логи
    access_log /var/log/nginx/loyalty_access.log;
    error_log /var/log/nginx/loyalty_error.log;

    # Максимальный размер загружаемого файла
    client_max_body_size 10M;

    # Проксирование на Waitress (аналог Apache ProxyPass)
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto http;
        proxy_set_header X-Forwarded-Host \$server_name;
        
        # Таймауты
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Буферизация
        proxy_buffering off;
    }

    # Статические файлы
    location /static/ {
        alias $PROJECT_DIR/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}

# HTTPS - будет автоматически добавлен после установки SSL через certbot
# Или раскомментируйте вручную после настройки сертификатов:
#
# server {
#     listen 443 ssl http2;
#     server_name $DOMAIN www.$DOMAIN;
#
#     ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
#     ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
#
#     ssl_protocols TLSv1.2 TLSv1.3;
#     ssl_ciphers HIGH:!aNULL:!MD5;
#     ssl_prefer_server_ciphers on;
#
#     access_log /var/log/nginx/loyalty_ssl_access.log;
#     error_log /var/log/nginx/loyalty_ssl_error.log;
#
#     client_max_body_size 10M;
#
#     location / {
#         proxy_pass http://127.0.0.1:5000;
#         proxy_set_header Host \$host;
#         proxy_set_header X-Real-IP \$remote_addr;
#         proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
#         proxy_set_header X-Forwarded-Proto https;
#         proxy_set_header X-Forwarded-Host \$server_name;
#         proxy_connect_timeout 60s;
#         proxy_send_timeout 60s;
#         proxy_read_timeout 60s;
#         proxy_buffering off;
#     }
#
#     location /static/ {
#         alias $PROJECT_DIR/static/;
#         expires 30d;
#         add_header Cache-Control "public, immutable";
#     }
# }
EOF

# Активация конфигурации
ln -sf /etc/nginx/sites-available/loyalty /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Проверка конфигурации Nginx
if nginx -t; then
    info "Конфигурация Nginx корректна"
else
    error "Ошибка в конфигурации Nginx!"
    exit 1
fi

# Шаг 11: Перезагрузка сервисов
info "Шаг 11: Перезагрузка сервисов..."
systemctl daemon-reload
systemctl enable loyalty-bot.service
systemctl enable loyalty-web.service
systemctl enable nginx

# Шаг 12: Запуск сервисов
info "Шаг 12: Запуск сервисов..."
systemctl restart nginx
systemctl start loyalty-bot.service
systemctl start loyalty-web.service

# Проверка статуса
echo ""
info "Проверка статуса сервисов..."
sleep 2

if systemctl is-active --quiet loyalty-bot.service; then
    info "✓ Telegram бот запущен"
else
    error "✗ Telegram бот не запущен. Проверьте логи: journalctl -u loyalty-bot -n 50"
fi

if systemctl is-active --quiet loyalty-web.service; then
    info "✓ Веб-приложение запущено"
else
    error "✗ Веб-приложение не запущено. Проверьте логи: journalctl -u loyalty-web -n 50"
fi

if systemctl is-active --quiet nginx; then
    info "✓ Nginx запущен"
else
    error "✗ Nginx не запущен. Проверьте: systemctl status nginx"
fi

echo ""
echo "=========================================="
info "Развертывание завершено!"
echo "=========================================="
echo ""
echo "Полезные команды:"
echo "  Статус сервисов:"
echo "    sudo systemctl status loyalty-bot"
echo "    sudo systemctl status loyalty-web"
echo "    sudo systemctl status nginx"
echo ""
echo "  Логи:"
echo "    sudo journalctl -u loyalty-bot -f"
echo "    sudo journalctl -u loyalty-web -f"
echo "    tail -f $PROJECT_DIR/logs/bot.log"
echo "    tail -f $PROJECT_DIR/logs/web.log"
echo ""
echo "  Управление:"
echo "    sudo systemctl restart loyalty-bot"
echo "    sudo systemctl restart loyalty-web"
echo "    sudo systemctl restart nginx"
echo ""
echo "  Настройка SSL (Let's Encrypt):"
echo "    sudo chmod +x setup_ssl_ubuntu.sh"
echo "    sudo ./setup_ssl_ubuntu.sh"
echo "    ИЛИ: sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN"
echo ""
echo "  Домен настроен: $DOMAIN"
echo "  Сайт доступен по HTTP: http://$DOMAIN"
echo "  После установки SSL будет доступен по HTTPS"
echo ""
warn "ВАЖНО:"
echo "  1. Создайте файл .env с настройками"
echo "  2. Настройте домен в /etc/nginx/sites-available/loyalty"
echo "  3. Установите SSL сертификат для HTTPS"
echo ""
