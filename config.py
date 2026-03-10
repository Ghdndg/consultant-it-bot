import os
from dotenv import load_dotenv

load_dotenv()

# Конфигурация бота
BOT_TOKEN = os.getenv('BOT_TOKEN', '8422779940:AAGvI2HSUr6hk4lMfh9xG_7lv-tjhtj6Vys')
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '895237112'))

# Дополнительные администраторы (можно указать через запятую в .env)
ADMIN_IDS_STR = os.getenv('ADMIN_IDS', f"{ADMIN_USER_ID},895237133")
ADMIN_IDS = [int(id.strip()) for id in ADMIN_IDS_STR.split(',') if id.strip().isdigit()]

# Убеждаемся, что основной админ в списке, и убираем дубликаты
if ADMIN_USER_ID not in ADMIN_IDS:
    ADMIN_IDS.append(ADMIN_USER_ID)

# Убираем дубликаты из списка (сохраняет порядок)
ADMIN_IDS = list(dict.fromkeys(ADMIN_IDS))
ADMIN_TELEGRAM_IDS = ADMIN_IDS  # Алиас для совместимости

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///loyalty_bot.db')
BACKUP_CHAT_ID = int(os.getenv('BACKUP_CHAT_ID', '-1003562995775'))
BACKUP_HOUR = int(os.getenv('BACKUP_HOUR', '3'))
BACKUP_MINUTE = int(os.getenv('BACKUP_MINUTE', '0'))
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

# Настройки программы лояльности
POINTS_PER_PURCHASE = 5  # Обновлено через админ-панель
BONUS_THRESHOLD = 100     # Порог для получения бонуса
BONUS_AMOUNT = 50         # Размер бонуса
REFERRAL_BONUS = 25       # Бонус за приглашение друга

# Настройки QR кодов
QR_CODE_SIZE = 10
QR_CODE_BORDER = 4

# Настройки уведомлений
INACTIVITY_DAYS_THRESHOLD = int(os.getenv('INACTIVITY_DAYS_THRESHOLD', '20'))  # Дни до отправки напоминания
WELCOME_BACK_BONUS = int(os.getenv('WELCOME_BACK_BONUS', '10'))  # Бонус за возвращение
BIRTHDAY_BONUS = int(os.getenv('BIRTHDAY_BONUS', '50'))  # Подарочные баллы на день рождения
ENABLE_NOTIFICATIONS = os.getenv('ENABLE_NOTIFICATIONS', 'True').lower() == 'true'  # Включить уведомления

# Настройки расписания уведомлений
NOTIFICATION_WEEKDAY = int(os.getenv('NOTIFICATION_WEEKDAY', '4'))  # День недели (0=понедельник, 4=пятница)
NOTIFICATION_HOUR = int(os.getenv('NOTIFICATION_HOUR', '12'))  # Час отправки (0-23)
NOTIFICATION_MINUTE = int(os.getenv('NOTIFICATION_MINUTE', '0'))  # Минута отправки (0-59) 