#!/bin/bash
# Скрипт настройки SSL сертификата для домена

set -e

if [ "$EUID" -ne 0 ]; then 
    echo "Запустите с правами root: sudo ./setup_ssl_ubuntu.sh"
    exit 1
fi

# Запрос домена
read -p "Введите домен (например, optobuvfeo.ru): " DOMAIN
if [ -z "$DOMAIN" ]; then
    echo "Ошибка: домен не указан"
    exit 1
fi

echo "=========================================="
echo "  Настройка SSL для $DOMAIN"
echo "=========================================="
echo ""

# Установка Certbot
echo "Установка Certbot..."
apt-get update
apt-get install -y certbot python3-certbot-nginx

# Проверка, что Nginx настроен
if [ ! -f "/etc/nginx/sites-available/loyalty" ]; then
    echo "Ошибка: конфигурация Nginx не найдена!"
    echo "Сначала запустите deploy_ubuntu.sh"
    exit 1
fi

# Получение сертификата
echo "Получение SSL сертификата от Let's Encrypt..."
echo "Убедитесь, что:"
echo "  1. Домен $DOMAIN указывает на IP этого сервера"
echo "  2. Порты 80 и 443 открыты в firewall"
echo "  3. Nginx работает и доступен по HTTP"
echo ""

# Проверка доступности домена
echo "Проверка доступности домена..."
if curl -s -o /dev/null -w "%{http_code}" "http://$DOMAIN" | grep -q "200\|301\|302"; then
    echo "✓ Домен доступен"
else
    echo "⚠ Внимание: домен может быть недоступен. Продолжаем..."
fi

read -p "Продолжить установку SSL? (y/n): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Отменено"
    exit 1
fi

# Запрос email для Let's Encrypt
read -p "Введите email для уведомлений Let's Encrypt: " EMAIL
EMAIL=${EMAIL:-admin@$DOMAIN}

# Получение сертификата
echo "Получение сертификата..."
certbot --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos --email $EMAIL --redirect

# Автоматическое обновление
echo "Настройка автоматического обновления сертификата..."
systemctl enable certbot.timer
systemctl start certbot.timer

# Перезагрузка Nginx
echo "Перезагрузка Nginx..."
systemctl reload nginx

echo ""
echo "=========================================="
echo "  SSL сертификат установлен!"
echo "=========================================="
echo ""
echo "Проверьте работу сайта:"
echo "  https://$DOMAIN"
echo ""
echo "Статус сертификата:"
echo "  sudo certbot certificates"
echo ""
echo "Тестовое обновление:"
echo "  sudo certbot renew --dry-run"
echo ""
