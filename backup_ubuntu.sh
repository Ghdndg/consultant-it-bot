#!/bin/bash
# Скрипт создания резервной копии

set -e

PROJECT_DIR="/opt/loyalty-bot"  # Измените на ваш путь
BACKUP_DIR="$PROJECT_DIR/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_$DATE.db"

echo "Создание резервной копии..."

# Создание директории для бэкапов
mkdir -p "$BACKUP_DIR"

# Создание бэкапа БД
if [ -f "$PROJECT_DIR/loyalty_bot.db" ]; then
    sqlite3 "$PROJECT_DIR/loyalty_bot.db" ".backup '$BACKUP_FILE'"
    echo "Бэкап создан: $BACKUP_FILE"
    
    # Сжатие (опционально)
    gzip "$BACKUP_FILE"
    echo "Бэкап сжат: $BACKUP_FILE.gz"
    
    # Удаление старых бэкапов (старше 30 дней)
    find "$BACKUP_DIR" -name "backup_*.db.gz" -mtime +30 -delete
    echo "Старые бэкапы удалены"
else
    echo "База данных не найдена!"
    exit 1
fi

echo "Готово!"
