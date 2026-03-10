#!/bin/bash
# Быстрая установка Certbot

set -e

if [ "$EUID" -ne 0 ]; then 
    echo "Запустите с правами root: sudo ./install_certbot_quick.sh"
    exit 1
fi

echo "Установка Certbot..."

# Обновление списка пакетов
apt-get update

# Установка Certbot и плагина для Nginx
apt-get install -y certbot python3-certbot-nginx

echo ""
echo "Certbot установлен!"
echo ""
echo "Теперь можно получить SSL сертификат:"
echo "  sudo certbot --nginx -d optobuvfeo.ru -d www.optobuvfeo.ru"
echo ""
echo "Или используйте скрипт:"
echo "  sudo ./setup_ssl_ubuntu.sh"
echo ""
