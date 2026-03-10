#!/bin/bash
# Скрипт для проверки статуса приложения и диагностики проблем

echo "=========================================="
echo "  Проверка статуса веб-приложения"
echo "=========================================="
echo ""

# Проверка статуса сервиса
echo "1. Статус сервиса loyalty-web:"
sudo systemctl status loyalty-web.service --no-pager -l
echo ""

# Проверка последних логов
echo "2. Последние 50 строк логов сервиса:"
sudo journalctl -u loyalty-web.service -n 50 --no-pager
echo ""

# Проверка, что порт 5000 слушается
echo "3. Проверка порта 5000:"
netstat -tlnp | grep 5000 || ss -tlnp | grep 5000 || echo "Порт 5000 не слушается"
echo ""

# Проверка синтаксиса Python
echo "4. Проверка синтаксиса cashier_admin_stable.py:"
cd /home
/home/venv/bin/python3 -m py_compile cashier_admin_stable.py 2>&1
if [ $? -eq 0 ]; then
    echo "✓ Синтаксис корректен"
else
    echo "✗ Ошибка синтаксиса!"
fi
echo ""

# Проверка импортов
echo "5. Проверка импортов:"
/home/venv/bin/python3 -c "
try:
    from cashier_admin_stable import app
    print('✓ Импорт app успешен')
except Exception as e:
    print(f'✗ Ошибка импорта: {e}')
    import traceback
    traceback.print_exc()
"
echo ""

# Проверка Nginx
echo "6. Статус Nginx:"
sudo systemctl status nginx --no-pager -l | head -20
echo ""

echo "=========================================="
echo "  Проверка завершена"
echo "=========================================="
