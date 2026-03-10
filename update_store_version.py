#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для обновления старых версий программы лояльности до актуальной версии
Обновляет версии в папках "Самуил" и "Лев" до версии из основной папки
"""

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Пути к папкам
BASE_DIR = Path(__file__).parent
SOURCE_DIR = BASE_DIR  # Актуальная версия (текущая папка)
TARGET_DIRS = [
    BASE_DIR / "Самуил" / "ЧатБот Программа Лояльности",
    BASE_DIR / "Лев" / "ЧатБот Программа Лояльности"
]

# Файлы, которые нужно обновить
FILES_TO_UPDATE = [
    # Основные Python файлы
    "handlers.py",
    "services.py",
    "admin_handlers.py",
    "keyboards.py",
    "main.py",
    "database.py",
    "notifications.py",
    "telegram_notifications.py",
    "charts.py",
    "cashier_admin_stable.py",
    
    # Новые файлы (могут отсутствовать в старых версиях)
    "user_web_routes.py",
    "migrate_add_web_credentials.py",  # Скрипт миграции БД
    
    # Конфигурационные файлы (обновляем, но сохраняем старые значения)
    "requirements.txt",
]

# Файлы, которые нужно сохранить (не обновлять)
FILES_TO_PRESERVE = [
    "config.py",  # Сохраняем токены и настройки
    "loyalty_bot.db",  # База данных
    ".env",  # Переменные окружения
]

# Папки для обновления
DIRS_TO_UPDATE = [
    "templates",
    "static",
]

# Файлы в папках, которые нужно сохранить
PRESERVE_IN_TEMPLATES = []  # Все шаблоны обновляем
PRESERVE_IN_STATIC = []  # Все статические файлы обновляем

def create_backup(target_dir):
    """Создает резервную копию перед обновлением"""
    backup_dir = target_dir.parent / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"📦 Создание резервной копии в {backup_dir}...")
    
    try:
        shutil.copytree(target_dir, backup_dir, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.db-journal'))
        print(f"✅ Резервная копия создана: {backup_dir}")
        return backup_dir
    except Exception as e:
        print(f"❌ Ошибка при создании резервной копии: {e}")
        return None

def preserve_config(target_dir, source_dir):
    """Сохраняет конфигурационные файлы из старой версии"""
    print("💾 Сохранение конфигурационных файлов...")
    
    preserved = {}
    
    # Сохраняем config.py
    target_config = target_dir / "config.py"
    if target_config.exists():
        with open(target_config, 'r', encoding='utf-8') as f:
            preserved['config'] = f.read()
        print("  ✅ config.py сохранен")
    
    # Сохраняем .env если есть
    target_env = target_dir / ".env"
    if target_env.exists():
        with open(target_env, 'r', encoding='utf-8') as f:
            preserved['env'] = f.read()
        print("  ✅ .env сохранен")
    
    return preserved

def restore_config(target_dir, preserved):
    """Восстанавливает сохраненные конфигурационные файлы"""
    print("🔄 Восстановление конфигурационных файлов...")
    
    # Восстанавливаем config.py
    if 'config' in preserved:
        target_config = target_dir / "config.py"
        with open(target_config, 'w', encoding='utf-8') as f:
            f.write(preserved['config'])
        print("  ✅ config.py восстановлен")
    
    # Восстанавливаем .env
    if 'env' in preserved:
        target_env = target_dir / ".env"
        with open(target_env, 'w', encoding='utf-8') as f:
            f.write(preserved['env'])
        print("  ✅ .env восстановлен")

def copy_file(source, target):
    """Копирует файл с созданием директорий если нужно"""
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)

def update_files(target_dir, source_dir):
    """Обновляет файлы в целевой директории"""
    print(f"\n📝 Обновление файлов в {target_dir.name}...")
    
    updated_count = 0
    new_count = 0
    
    # Обновляем отдельные файлы
    for file_name in FILES_TO_UPDATE:
        source_file = source_dir / file_name
        target_file = target_dir / file_name
        
        if not source_file.exists():
            print(f"  ⚠️  Файл {file_name} не найден в исходной версии, пропускаем")
            continue
        
        if target_file.exists():
            print(f"  🔄 Обновление {file_name}...")
        else:
            print(f"  ➕ Добавление нового файла {file_name}...")
            new_count += 1
        
        copy_file(source_file, target_file)
        updated_count += 1
    
    # Обновляем папки
    for dir_name in DIRS_TO_UPDATE:
        source_dir_path = source_dir / dir_name
        target_dir_path = target_dir / dir_name
        
        if not source_dir_path.exists():
            print(f"  ⚠️  Папка {dir_name} не найдена в исходной версии, пропускаем")
            continue
        
        print(f"  📁 Обновление папки {dir_name}...")
        
        # Удаляем старую папку (кроме сохраненных файлов)
        if target_dir_path.exists():
            # Сохраняем файлы, которые нужно сохранить
            preserve_patterns = PRESERVE_IN_TEMPLATES if dir_name == "templates" else PRESERVE_IN_STATIC
            preserved_files = {}
            for pattern in preserve_patterns:
                preserved_file = target_dir_path / pattern
                if preserved_file.exists():
                    with open(preserved_file, 'rb') as f:
                        preserved_files[pattern] = f.read()
            
            shutil.rmtree(target_dir_path)
        
        # Копируем новую папку
        shutil.copytree(source_dir_path, target_dir_path, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        
        # Восстанавливаем сохраненные файлы
        for pattern, content in preserved_files.items():
            preserved_file = target_dir_path / pattern
            with open(preserved_file, 'wb') as f:
                f.write(content)
        
        updated_count += 1
    
    print(f"\n✅ Обновлено файлов: {updated_count}, добавлено новых: {new_count}")

def check_database_migration(target_dir):
    """Проверяет, нужна ли миграция базы данных"""
    db_file = target_dir / "loyalty_bot.db"
    if not db_file.exists():
        print("  ℹ️  База данных не найдена, миграция не требуется")
        return False
    
    # Проверяем наличие новых полей
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()
        
        # Проверяем наличие поля web_login
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        needs_migration = 'web_login' not in columns
        
        conn.close()
        
        if needs_migration:
            print("  ⚠️  Требуется миграция базы данных (добавление полей web_login, web_password_hash)")
            return True
        else:
            print("  ✅ База данных актуальна, миграция не требуется")
            return False
    except Exception as e:
        print(f"  ⚠️  Не удалось проверить базу данных: {e}")
        return False

def run_database_migration(target_dir):
    """Выполняет миграцию базы данных"""
    print("\n🔧 Выполнение миграции базы данных...")
    
    try:
        # Импортируем функцию миграции
        sys.path.insert(0, str(target_dir))
        from migrate_add_web_credentials import migrate_database
        
        if migrate_database():
            print("  ✅ Миграция базы данных выполнена успешно")
            return True
        else:
            print("  ⚠️  Миграция базы данных не выполнена (возможно, уже выполнена)")
            return False
    except ImportError:
        print("  ⚠️  Скрипт миграции не найден, пропускаем")
        return False
    except Exception as e:
        print(f"  ❌ Ошибка при миграции базы данных: {e}")
        return False

def update_store(target_dir_name):
    """Обновляет одну версию магазина"""
    target_dir = BASE_DIR / target_dir_name / "ЧатБот Программа Лояльности"
    
    if not target_dir.exists():
        print(f"❌ Папка {target_dir} не найдена!")
        return False
    
    print(f"\n{'='*60}")
    print(f"🔄 Обновление: {target_dir_name}")
    print(f"{'='*60}")
    
    # Создаем резервную копию
    backup_dir = create_backup(target_dir)
    if not backup_dir:
        response = input("⚠️  Не удалось создать резервную копию. Продолжить? (y/n): ")
        if response.lower() != 'y':
            print("❌ Обновление отменено")
            return False
    
    # Сохраняем конфигурацию
    preserved = preserve_config(target_dir, SOURCE_DIR)
    
    # Обновляем файлы
    update_files(target_dir, SOURCE_DIR)
    
    # Восстанавливаем конфигурацию
    restore_config(target_dir, preserved)
    
    # Проверяем миграцию БД
    if check_database_migration(target_dir):
        response = input("⚠️  Требуется миграция базы данных. Выполнить? (y/n): ")
        if response.lower() == 'y':
            run_database_migration(target_dir)
    
    print(f"\n✅ Обновление {target_dir_name} завершено!")
    print(f"📦 Резервная копия: {backup_dir}")
    
    return True

def main():
    """Главная функция"""
    print("="*60)
    print("🚀 Обновление старых версий программы лояльности")
    print("="*60)
    print("\nЭтот скрипт обновит версии в папках:")
    print("  - Самуил/ЧатБот Программа Лояльности")
    print("  - Лев/ЧатБот Программа Лояльности")
    print("\n⚠️  ВНИМАНИЕ: Будет создана резервная копия перед обновлением")
    print("⚠️  Конфигурационные файлы (config.py, .env) будут сохранены")
    print("⚠️  База данных (loyalty_bot.db) будет сохранена")
    
    response = input("\nПродолжить обновление? (y/n): ")
    if response.lower() != 'y':
        print("❌ Обновление отменено")
        return
    
    # Выбираем какие версии обновлять
    print("\nВыберите версии для обновления:")
    print("  1. Самуил")
    print("  2. Лев")
    print("  3. Обе версии")
    
    choice = input("\nВаш выбор (1/2/3): ").strip()
    
    updated = []
    
    if choice == '1' or choice == '3':
        if update_store("Самуил"):
            updated.append("Самуил")
    
    if choice == '2' or choice == '3':
        if update_store("Лев"):
            updated.append("Лев")
    
    if updated:
        print(f"\n{'='*60}")
        print("✅ Обновление завершено!")
        print(f"{'='*60}")
        print("\nОбновленные версии:")
        for name in updated:
            print(f"  ✅ {name}")
        print("\n📋 Следующие шаги:")
        print("  1. Проверьте работу бота и веб-интерфейса")
        print("  2. Убедитесь, что все функции работают корректно")
        print("  3. Если что-то не работает, используйте резервные копии для отката")
    else:
        print("\n❌ Обновление не выполнено")

if __name__ == '__main__':
    main()
