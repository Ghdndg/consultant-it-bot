#!/bin/bash
# Универсальный скрипт развертывания для любого магазина на Ubuntu

set -e  # Остановка при ошибке

echo "=========================================="
echo "  Развертывание программы лояльности"
echo "  (Универсальный скрипт для любого магазина)"
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
    error "Запустите скрипт с правами root: sudo ./deploy_store_ubuntu.sh"
    exit 1
fi

# Запрос информации о магазине
echo "Введите информацию о магазине:"
echo ""
read -p "Название магазина (например: НихренаСебе, Тютелька): " STORE_NAME
STORE_NAME=${STORE_NAME:-"Магазин"}

read -p "Домен (например: nixrenasebe.ru, tyutelkavtyutelku.ru): " DOMAIN
if [ -z "$DOMAIN" ]; then
    error "Домен обязателен!"
    exit 1
fi

read -p "Путь к проекту на сервере [/opt/loyalty-$STORE_NAME]: " PROJECT_DIR
PROJECT_DIR=${PROJECT_DIR:-"/opt/loyalty-$STORE_NAME"}

read -p "Имя пользователя для приложения [loyalty-$STORE_NAME]: " APP_USER
APP_USER=${APP_USER:-"loyalty-$(echo $STORE_NAME | tr '[:upper:]' '[:lower:]' | tr ' ' '-')"}

# Очистка имени пользователя от спецсимволов
APP_USER=$(echo $APP_USER | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | sed 's/[^a-z0-9-]//g')

info "Настройки:"
echo "  Магазин: $STORE_NAME"
echo "  Домен: $DOMAIN"
echo "  Путь: $PROJECT_DIR"
echo "  Пользователь: $APP_USER"
echo ""
read -p "Продолжить? (y/n): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Отменено"
    exit 1
fi

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
if ! id "$APP_USER" &>/dev/null; then
    useradd -r -s /bin/bash -d "$PROJECT_DIR" -m "$APP_USER"
    info "Пользователь $APP_USER создан"
else
    info "Пользователь $APP_USER уже существует"
fi

# Шаг 4: Настройка прав доступа
info "Шаг 4: Настройка прав доступа..."
if [ -d "$PROJECT_DIR" ]; then
    chown -R $APP_USER:$APP_USER "$PROJECT_DIR"
    info "Права установлены для существующей директории"
else
    warn "Директория $PROJECT_DIR не существует"
    warn "Создайте её и загрузите файлы проекта, затем запустите скрипт снова"
    warn "Или создайте сейчас: mkdir -p $PROJECT_DIR && chown -R $APP_USER:$APP_USER $PROJECT_DIR"
    read -p "Создать директорию сейчас? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        mkdir -p "$PROJECT_DIR"
        chown -R $APP_USER:$APP_USER "$PROJECT_DIR"
        info "Директория создана. Загрузите файлы проекта в $PROJECT_DIR и запустите скрипт снова."
        exit 0
    fi
fi

# Проверка наличия основных файлов
if [ ! -f "$PROJECT_DIR/main.py" ]; then
    error "Файл main.py не найден в $PROJECT_DIR"
    error "Загрузите файлы проекта в $PROJECT_DIR и запустите скрипт снова"
    exit 1
fi

# Шаг 5: Создание виртуального окружения
info "Шаг 5: Создание виртуального окружения..."
if [ ! -d "$PROJECT_DIR/venv" ]; then
    info "Создание нового виртуального окружения..."
    sudo -u $APP_USER python3 -m venv "$PROJECT_DIR/venv"
    info "Виртуальное окружение создано"
else
    # Проверка целостности виртуального окружения
    if [ ! -f "$PROJECT_DIR/venv/bin/pip" ] || [ ! -f "$PROJECT_DIR/venv/bin/python3" ]; then
        warn "Виртуальное окружение повреждено, пересоздаю..."
        rm -rf "$PROJECT_DIR/venv"
        sudo -u $APP_USER python3 -m venv "$PROJECT_DIR/venv"
        info "Виртуальное окружение пересоздано"
    else
        info "Виртуальное окружение уже существует и проверено"
    fi
fi

# Шаг 6: Установка Python зависимостей
info "Шаг 6: Установка Python зависимостей..."

# Проверка, что pip доступен
if [ ! -f "$PROJECT_DIR/venv/bin/pip" ]; then
    error "pip не найден в виртуальном окружении!"
    error "Попробуйте удалить venv и запустить скрипт снова:"
    error "  sudo rm -rf $PROJECT_DIR/venv"
    exit 1
fi

if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    info "Установка зависимостей из requirements.txt..."
    sudo -u $APP_USER "$PROJECT_DIR/venv/bin/pip" install --upgrade pip
    sudo -u $APP_USER "$PROJECT_DIR/venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
    if [ $? -eq 0 ]; then
        info "Зависимости установлены успешно"
    else
        error "Ошибка при установке зависимостей!"
        exit 1
    fi
else
    warn "Файл requirements.txt не найден, устанавливаю базовые зависимости..."
    sudo -u $APP_USER "$PROJECT_DIR/venv/bin/pip" install --upgrade pip
    sudo -u $APP_USER "$PROJECT_DIR/venv/bin/pip" install python-telegram-bot SQLAlchemy python-dotenv qrcode[pil] pillow Flask waitress requests
    if [ $? -eq 0 ]; then
        info "Базовые зависимости установлены"
    else
        error "Ошибка при установке базовых зависимостей!"
        exit 1
    fi
fi

# Шаг 7: Создание директорий для логов и бэкапов
info "Шаг 7: Создание директорий..."
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/backups"
chown -R $APP_USER:$APP_USER "$PROJECT_DIR/logs"
chown -R $APP_USER:$APP_USER "$PROJECT_DIR/backups"

# Шаг 8: Настройка конфигурации
info "Шаг 8: Настройка конфигурации..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
    warn ".env файл не найден. Создайте его вручную с настройками:"
    echo ""
    echo "BOT_TOKEN=ваш_токен_бота_от_BotFather"
    echo "ADMIN_USER_ID=ваш_telegram_id"
    echo "BACKUP_CHAT_ID=ваш_chat_id_для_бэкапов"
    echo "BACKUP_HOUR=3"
    echo "BACKUP_MINUTE=0"
    echo "DEBUG=False"
    echo ""
    echo "Создайте файл: nano $PROJECT_DIR/.env"
    echo ""
else
    info ".env файл найден"
fi

# Шаг 9: Создание systemd сервисов
info "Шаг 9: Создание systemd сервисов..."

# Имя сервиса на основе названия магазина
SERVICE_NAME_BOT="loyalty-bot-$(echo $STORE_NAME | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | sed 's/[^a-z0-9-]//g')"
SERVICE_NAME_WEB="loyalty-web-$(echo $STORE_NAME | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | sed 's/[^a-z0-9-]//g')"

# Сервис для Telegram бота
cat > /etc/systemd/system/${SERVICE_NAME_BOT}.service << EOF
[Unit]
Description=Telegram Loyalty Bot - $STORE_NAME
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
cat > /etc/systemd/system/${SERVICE_NAME_WEB}.service << EOF
[Unit]
Description=Loyalty Web Application (Waitress) - $STORE_NAME
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

# Установка пакета для временных сертификатов (если нужно)
if [ ! -f "/etc/ssl/certs/ssl-cert-snakeoil.pem" ]; then
    info "Установка пакета для временных SSL сертификатов..."
    apt-get install -y ssl-cert
fi

# Имя конфигурации на основе домена
NGINX_CONFIG="loyalty-$(echo $DOMAIN | tr '.' '-')"

cat > /etc/nginx/sites-available/$NGINX_CONFIG << EOF
# HTTP - временная конфигурация (до установки SSL)
# Магазин: $STORE_NAME
# Домен: $DOMAIN
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;

    # Логи
    access_log /var/log/nginx/${NGINX_CONFIG}_access.log;
    error_log /var/log/nginx/${NGINX_CONFIG}_error.log;

    # Максимальный размер загружаемого файла
    client_max_body_size 10M;

    # Проксирование на Waitress
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
EOF

# Активация конфигурации
ln -sf /etc/nginx/sites-available/$NGINX_CONFIG /etc/nginx/sites-enabled/

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
systemctl enable ${SERVICE_NAME_BOT}.service
systemctl enable ${SERVICE_NAME_WEB}.service
systemctl enable nginx

# Шаг 12: Запуск сервисов
info "Шаг 12: Запуск сервисов..."
systemctl restart nginx
systemctl start ${SERVICE_NAME_BOT}.service
systemctl start ${SERVICE_NAME_WEB}.service

# Проверка статуса
echo ""
info "Проверка статуса сервисов..."
sleep 2

if systemctl is-active --quiet ${SERVICE_NAME_BOT}.service; then
    info "✓ Telegram бот запущен"
else
    error "✗ Telegram бот не запущен. Проверьте логи: journalctl -u ${SERVICE_NAME_BOT} -n 50"
fi

if systemctl is-active --quiet ${SERVICE_NAME_WEB}.service; then
    info "✓ Веб-приложение запущено"
else
    error "✗ Веб-приложение не запущено. Проверьте логи: journalctl -u ${SERVICE_NAME_WEB} -n 50"
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
echo "Информация о развертывании:"
echo "  Магазин: $STORE_NAME"
echo "  Домен: $DOMAIN"
echo "  Путь: $PROJECT_DIR"
echo "  Пользователь: $APP_USER"
echo "  Сервис бота: ${SERVICE_NAME_BOT}"
echo "  Сервис веб: ${SERVICE_NAME_WEB}"
echo "  Конфигурация Nginx: $NGINX_CONFIG"
echo ""
echo "Полезные команды:"
echo "  Статус сервисов:"
echo "    sudo systemctl status ${SERVICE_NAME_BOT}"
echo "    sudo systemctl status ${SERVICE_NAME_WEB}"
echo ""
echo "  Логи:"
echo "    sudo journalctl -u ${SERVICE_NAME_BOT} -f"
echo "    sudo journalctl -u ${SERVICE_NAME_WEB} -f"
echo ""
echo "  Управление:"
echo "    sudo systemctl restart ${SERVICE_NAME_BOT}"
echo "    sudo systemctl restart ${SERVICE_NAME_WEB}"
echo ""
echo "  Настройка SSL:"
echo "    sudo apt-get install certbot python3-certbot-nginx"
echo "    sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN"
echo ""
warn "ВАЖНО:"
echo "  1. Создайте файл .env с настройками в $PROJECT_DIR"
echo "  2. Настройте DNS: домен $DOMAIN должен указывать на IP этого сервера"
echo "  3. Установите SSL сертификат для HTTPS"
echo ""
