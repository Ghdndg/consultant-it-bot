#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from waitress import serve
from cashier_admin_stable import app, schedule_daily_backup
import config

if __name__ == '__main__':
    print('Запуск Flask-приложения через Waitress на http://127.0.0.1:5000')
    try:
        schedule_daily_backup()
        print(f"Плановый бэкап БД запланирован ежедневно на {config.BACKUP_HOUR:02d}:{config.BACKUP_MINUTE:02d}")
    except Exception as e:
        print(f"Не удалось запланировать бэкап: {e}")
    serve(app, host='127.0.0.1', port=5000, threads=4)
