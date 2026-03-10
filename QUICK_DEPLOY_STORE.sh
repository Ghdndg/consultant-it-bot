#!/bin/bash
# Быстрый скрипт развертывания для конкретного магазина
# Использование: ./QUICK_DEPLOY_STORE.sh "Название" "домен.ru" "/opt/path"

set -e

if [ "$EUID" -ne 0 ]; then 
    echo "Запустите с правами root: sudo ./QUICK_DEPLOY_STORE.sh"
    exit 1
fi

if [ $# -lt 2 ]; then
    echo "Использование:"
    echo "  sudo ./QUICK_DEPLOY_STORE.sh \"Название магазина\" \"домен.ru\" [путь]"
    echo ""
    echo "Примеры:"
    echo "  sudo ./QUICK_DEPLOY_STORE.sh \"НихренаСебе\" \"nixrenasebe.ru\" \"/opt/loyalty-lev\""
    echo "  sudo ./QUICK_DEPLOY_STORE.sh \"Тютелька\" \"tyutelkavtyutelku.ru\" \"/opt/loyalty-samuil\""
    exit 1
fi

STORE_NAME="$1"
DOMAIN="$2"
PROJECT_DIR="${3:-/opt/loyalty-$(echo $STORE_NAME | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | sed 's/[^a-z0-9-]//g')}"

echo "=========================================="
echo "  Быстрое развертывание: $STORE_NAME"
echo "=========================================="
echo ""
echo "Домен: $DOMAIN"
echo "Путь: $PROJECT_DIR"
echo ""

# Проверка наличия файлов
if [ ! -f "$PROJECT_DIR/main.py" ]; then
    echo "ОШИБКА: Файлы проекта не найдены в $PROJECT_DIR"
    echo "Загрузите файлы проекта и запустите скрипт снова"
    exit 1
fi

# Запуск основного скрипта с автоматическими ответами
echo "$STORE_NAME" | sudo ./deploy_store_ubuntu.sh <<EOF
$STORE_NAME
$DOMAIN
$PROJECT_DIR

y
EOF

echo ""
echo "Развертывание завершено!"
echo "Не забудьте создать .env файл в $PROJECT_DIR"
echo ""
