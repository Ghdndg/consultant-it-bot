#!/bin/bash
# Скрипт для проверки ошибок на странице scanner

echo "=========================================="
echo "  Проверка ошибок на странице scanner"
echo "=========================================="
echo ""

# Проверка последних ошибок в логах
echo "1. Последние ошибки из логов приложения:"
sudo journalctl -u loyalty-web.service -n 100 --no-pager | grep -i "error\|exception\|traceback" | tail -20
echo ""

# Попытка импорта и проверки маршрута
echo "2. Проверка маршрута cashier.scanner:"
cd /home
/home/venv/bin/python3 << 'EOF'
try:
    from cashier_admin_stable import app
    with app.app_context():
        from flask import url_for
        try:
            url = url_for('cashier.scanner')
            print(f"✓ Маршрут cashier.scanner найден: {url}")
        except Exception as e:
            print(f"✗ Ошибка получения URL: {e}")
        
        # Проверка всех кассовых маршрутов
        routes = []
        for rule in app.url_map.iter_rules():
            if rule.endpoint.startswith('cashier.'):
                routes.append(rule.endpoint)
        print(f"✓ Найдено кассовых маршрутов: {len(routes)}")
        if routes:
            print("  Примеры:", ', '.join(routes[:5]))
except Exception as e:
    print(f"✗ Ошибка: {e}")
    import traceback
    traceback.print_exc()
EOF

echo ""
echo "=========================================="
echo "  Проверка завершена"
echo "=========================================="
