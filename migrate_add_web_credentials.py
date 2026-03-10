#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Миграция: Добавление полей web_login и web_password_hash в таблицу users
"""

import sqlite3
import os
import sys
from database import get_database_url

def migrate_database():
    """Добавление полей web_login и web_password_hash в таблицу users"""
    
    # Получаем путь к базе данных
    db_url = get_database_url()
    if not db_url.startswith('sqlite:///'):
        print("Эта миграция работает только с SQLite")
        return False
    
    db_path = db_url.replace('sqlite:///', '', 1)
    
    if not os.path.exists(db_path):
        print(f"База данных не найдена: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Проверяем, существуют ли уже поля
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        changes_made = False
        
        # Добавляем web_login, если его нет
        if 'web_login' not in columns:
            print("Добавление поля web_login...")
            # SQLite не позволяет добавлять UNIQUE колонку напрямую, добавляем без UNIQUE
            cursor.execute("ALTER TABLE users ADD COLUMN web_login VARCHAR(50)")
            # Создаем уникальный индекс для обеспечения уникальности
            try:
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_web_login ON users(web_login) WHERE web_login IS NOT NULL")
                print("  ✓ Создан уникальный индекс для web_login")
            except Exception as e:
                print(f"  ⚠ Не удалось создать уникальный индекс: {e}")
            changes_made = True
        else:
            print("Поле web_login уже существует")
            # Проверяем, есть ли индекс
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_users_web_login'")
            if not cursor.fetchone():
                try:
                    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_web_login ON users(web_login) WHERE web_login IS NOT NULL")
                    print("  ✓ Создан уникальный индекс для web_login")
                    changes_made = True
                except Exception as e:
                    print(f"  ⚠ Не удалось создать уникальный индекс: {e}")
        
        # Добавляем web_password_hash, если его нет
        if 'web_password_hash' not in columns:
            print("Добавление поля web_password_hash...")
            cursor.execute("ALTER TABLE users ADD COLUMN web_password_hash VARCHAR(255)")
            changes_made = True
        else:
            print("Поле web_password_hash уже существует")
        
        conn.commit()
        conn.close()
        
        if changes_made:
            print("✅ Миграция успешно выполнена!")
        else:
            print("ℹ️ Все поля уже существуют, миграция не требуется")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при выполнении миграции: {e}")
        return False

if __name__ == '__main__':
    print("=" * 50)
    print("Миграция базы данных: добавление web_login и web_password_hash")
    print("=" * 50)
    print()
    
    success = migrate_database()
    
    if success:
        print()
        print("Миграция завершена. Можно продолжать работу.")
        sys.exit(0)
    else:
        print()
        print("Миграция не выполнена. Проверьте ошибки выше.")
        sys.exit(1)
