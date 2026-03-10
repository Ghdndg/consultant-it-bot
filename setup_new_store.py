#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для автоматической настройки программы лояльности для нового магазина
"""

import os
import shutil
from datetime import datetime


def print_header(text):
    """Красивый заголовок"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")


def print_step(step_num, text):
    """Нумерованный шаг"""
    print(f"\n[Шаг {step_num}] {text}")


def get_input(prompt, default=None):
    """Получить ввод от пользователя"""
    if default:
        user_input = input(f"{prompt} [{default}]: ").strip()
        return user_input if user_input else default
    return input(f"{prompt}: ").strip()


def backup_file(filepath):
    """Создать резервную копию файла"""
    if os.path.exists(filepath):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"{filepath}.backup_{timestamp}"
        shutil.copy2(filepath, backup_path)
        print(f"✅ Создана резервная копия: {backup_path}")
        return True
    return False


def replace_in_file(filepath, old_text, new_text):
    """Заменить текст в файле"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if old_text in content:
            content = content.replace(old_text, new_text)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"❌ Ошибка при обработке {filepath}: {e}")
        return False


def main():
    print_header("🚀 НАСТРОЙКА ПРОГРАММЫ ЛОЯЛЬНОСТИ ДЛЯ НОВОГО МАГАЗИНА")
    
    print("Этот скрипт поможет вам автоматически настроить программу лояльности")
    print("для вашего магазина, заменив все необходимые данные.")
    print("\n⚠️  ВАЖНО: Перед началом убедитесь, что у вас есть:")
    print("   - Токен нового бота от @BotFather")
    print("   - Ваш Telegram ID (узнать через @userinfobot)")
    print("   - Chat ID для бэкапов")
    
    proceed = get_input("\nПродолжить? (yes/no)", "yes").lower()
    if proceed not in ['yes', 'y', 'да', 'д']:
        print("Отменено.")
        return
    
    # Сбор данных
    print_header("📋 СБОР ДАННЫХ")
    
    print_step(1, "Данные Telegram бота")
    bot_token = get_input("Введите токен нового бота")
    admin_id = get_input("Введите ваш Telegram ID")
    additional_admins = get_input("Дополнительные админы (через запятую, или Enter чтобы пропустить)", admin_id)
    backup_chat_id = get_input("Chat ID для бэкапов", admin_id)
    
    print_step(2, "Данные для веб-админки (кассир)")
    cashier_login = get_input("Логин кассира", "cashier")
    cashier_password = get_input("Пароль кассира")
    
    print_step(3, "Настройки программы лояльности")
    points_per_purchase = get_input("Баллов за 100₽ покупки", "5")
    referral_bonus = get_input("Бонус за приглашение друга", "25")
    welcome_back_bonus = get_input("Бонус за возвращение", "10")
    birthday_bonus = get_input("Бонус на день рождения", "50")
    
    print_step(4, "Домен (если используете)")
    has_domain = get_input("Используете собственный домен? (yes/no)", "no").lower()
    new_domain = None
    if has_domain in ['yes', 'y', 'да', 'д']:
        new_domain = get_input("Введите ваш домен (например: myshop.ru)")
    
    # Подтверждение
    print_header("🔍 ПРОВЕРКА ДАННЫХ")
    print(f"Токен бота: {bot_token[:20]}...")
    print(f"ID администратора: {admin_id}")
    print(f"Дополнительные админы: {additional_admins}")
    print(f"Chat ID для бэкапов: {backup_chat_id}")
    print(f"Логин кассира: {cashier_login}")
    print(f"Пароль кассира: {'*' * len(cashier_password)}")
    print(f"Баллов за 100₽: {points_per_purchase}")
    print(f"Бонус за реферала: {referral_bonus}")
    print(f"Бонус за возвращение: {welcome_back_bonus}")
    print(f"Бонус на ДР: {birthday_bonus}")
    if new_domain:
        print(f"Новый домен: {new_domain}")
    
    confirm = get_input("\n✅ Все правильно? Начать замену? (yes/no)", "yes").lower()
    if confirm not in ['yes', 'y', 'да', 'д']:
        print("Отменено.")
        return
    
    # Создание резервных копий
    print_header("💾 СОЗДАНИЕ РЕЗЕРВНЫХ КОПИЙ")
    
    files_to_backup = [
        'config.py',
        'cashier_admin_stable.py',
        'cashier_admin_regru_ssl.py',
        'cashier_apache.py'
    ]
    
    for filepath in files_to_backup:
        backup_file(filepath)
    
    # Замена данных
    print_header("🔧 ЗАМЕНА ДАННЫХ")
    
    changes_count = 0
    
    # config.py
    print("\n📝 Обновление config.py...")
    config_changes = [
        ("BOT_TOKEN = os.getenv('BOT_TOKEN', '8131593151:AAFgZ0-cIZf3VfR1WRHaYW_OifqMTLONxOw')",
         f"BOT_TOKEN = os.getenv('BOT_TOKEN', '{bot_token}')"),
        ("ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '5990048971'))",
         f"ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '{admin_id}'))"),
        ("ADMIN_IDS_STR = os.getenv('ADMIN_IDS', f\"{ADMIN_USER_ID},895237112\")",
         f"ADMIN_IDS_STR = os.getenv('ADMIN_IDS', f\"{{ADMIN_USER_ID}},{additional_admins}\")"),
        ("BACKUP_CHAT_ID = int(os.getenv('BACKUP_CHAT_ID', '-4933276798'))",
         f"BACKUP_CHAT_ID = int(os.getenv('BACKUP_CHAT_ID', '{backup_chat_id}'))"),
        (f"POINTS_PER_PURCHASE = 5",
         f"POINTS_PER_PURCHASE = {points_per_purchase}"),
        (f"REFERRAL_BONUS = 25",
         f"REFERRAL_BONUS = {referral_bonus}"),
        (f"WELCOME_BACK_BONUS = int(os.getenv('WELCOME_BACK_BONUS', '10'))",
         f"WELCOME_BACK_BONUS = int(os.getenv('WELCOME_BACK_BONUS', '{welcome_back_bonus}'))"),
        (f"BIRTHDAY_BONUS = int(os.getenv('BIRTHDAY_BONUS', '50'))",
         f"BIRTHDAY_BONUS = int(os.getenv('BIRTHDAY_BONUS', '{birthday_bonus}'))"),
    ]
    
    for old, new in config_changes:
        if replace_in_file('config.py', old, new):
            changes_count += 1
            print(f"  ✅ Обновлено")
    
    # Файлы кассира
    cashier_files = [
        'cashier_admin_stable.py',
        'cashier_admin_regru_ssl.py',
        'cashier_apache.py'
    ]
    
    for filepath in cashier_files:
        print(f"\n📝 Обновление {filepath}...")
        cashier_changes = [
            ('CASHIER_LOGIN = "cashier"', f'CASHIER_LOGIN = "{cashier_login}"'),
            ('CASHIER_PASSWORD = "Qq2AoZG4XwF"', f'CASHIER_PASSWORD = "{cashier_password}"'),
        ]
        
        if new_domain:
            cashier_changes.extend([
                ('nixrenasebe.ru', new_domain),
            ])
    
    # site_monitor.py
    if new_domain:
        print(f"\n📝 Обновление site_monitor.py...")
        monitor_changes = [
            ('https://your-domain.com', f'https://{new_domain}'),
        ]
        
        for old, new in monitor_changes:
            if replace_in_file('site_monitor.py', old, new):
                changes_count += 1
                print(f"  ✅ Обновлено")
        
        for old, new in cashier_changes:
            if replace_in_file(filepath, old, new):
                changes_count += 1
                print(f"  ✅ Обновлено")
    
    # Результат
    print_header("✅ ГОТОВО!")
    print(f"Успешно выполнено изменений: {changes_count}")
    print("\n📋 СЛЕДУЮЩИЕ ШАГИ:")
    print("1. Удалите старую базу данных: loyalty_bot.db")
    print("2. Удалите папку backups (или переименуйте)")
    print("3. Запустите бота: python main.py")
    print("4. Запустите веб-админку: python waitress_http.py")
    print("5. Протестируйте работу системы")
    
    print("\n⚠️  ВАЖНО:")
    print("- Резервные копии сохранены с расширением .backup_*")
    print("- В случае проблем можно восстановить из резервных копий")
    print("- Рекомендуется создать новый secret_key для Flask")
    
    print("\n🔐 Для генерации нового secret_key выполните:")
    print("   python -c \"import secrets; print(secrets.token_hex(32))\"")
    
    # Создание .env файла
    create_env = get_input("\n📝 Создать файл .env с вашими данными? (yes/no)", "yes").lower()
    if create_env in ['yes', 'y', 'да', 'д']:
        env_content = f"""# Автоматически сгенерирован {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

BOT_TOKEN={bot_token}
ADMIN_USER_ID={admin_id}
ADMIN_IDS={additional_admins}
BACKUP_CHAT_ID={backup_chat_id}

DATABASE_URL=sqlite:///loyalty_bot.db

POINTS_PER_PURCHASE={points_per_purchase}
BONUS_THRESHOLD=100
BONUS_AMOUNT=50
REFERRAL_BONUS={referral_bonus}

ENABLE_NOTIFICATIONS=True
INACTIVITY_DAYS_THRESHOLD=20
WELCOME_BACK_BONUS={welcome_back_bonus}
BIRTHDAY_BONUS={birthday_bonus}

NOTIFICATION_WEEKDAY=4
NOTIFICATION_HOUR=12
NOTIFICATION_MINUTE=0

BACKUP_HOUR=3
BACKUP_MINUTE=0

DEBUG=False
"""
        try:
            with open('.env', 'w', encoding='utf-8') as f:
                f.write(env_content)
            print("✅ Файл .env создан!")
        except Exception as e:
            print(f"❌ Не удалось создать .env: {e}")
            print("\n📝 Содержимое для .env:")
            print(env_content)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Прервано пользователем")
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        print("Проверьте резервные копии файлов (.backup_*)")

