#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Стабильная версия веб-админки для кассиров с профессиональным WSGI-сервером Waitress
"""

from flask import Flask, Blueprint, render_template, request, jsonify, redirect, url_for, session, flash, send_from_directory
from database import get_db, User, Purchase, PointsHistory, safe_migrate
from services import LoyaltyService, UserService
from telegram_notifications import send_purchase_notification_sync
from telegram_notifications import send_document_sync
from telegram_notifications import send_message_with_inline_button_sync
from user_web_routes import user_bp  # Импорт пользовательских маршрутов
import re
import config
from datetime import datetime
import logging
import threading
import atexit
import socket
import os
import signal
import sys
from sqlalchemy import func
import shutil
from datetime import timedelta
import requests

# Безопасный импорт ngrok
try:
    import pyngrok.ngrok as ngrok
    NGROK_AVAILABLE = True
except ImportError:
    NGROK_AVAILABLE = False
    print("ВНИМАНИЕ: pyngrok не установлен. Для публичного доступа установите: pip install pyngrok")

# Импорт Waitress
try:
    from waitress import serve
    WAITRESS_AVAILABLE = True
except ImportError:
    WAITRESS_AVAILABLE = False
    print("ОШИБКА: Waitress не установлен. Установите: pip install waitress")

app = Flask(__name__)
app.secret_key = 'programmaloyalty_program'

# Создаем Blueprint для кассовых маршрутов
cashier_bp = Blueprint('cashier', __name__, url_prefix='/kassa')

# Регистрация Blueprint для пользовательских маршрутов
app.register_blueprint(user_bp)

# Вызываем безопасную миграцию
safe_migrate()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cashier_server.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

CASHIER_LOGIN = "cashier"
CASHIER_PASSWORD = "8kVpL5Eu4Ds"

def get_server_ip():
    """Получить IP адрес сервера"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def create_fullchain_certificate():
    """Создание полного сертификата из файлов reg.ru"""
    if os.path.exists('./certificate.crt') and os.path.exists('./certificate_ca.crt'):
        try:
            with open('./certificate.crt', 'r') as f:
                cert_content = f.read()
            with open('./certificate_ca.crt', 'r') as f:
                ca_content = f.read()
            
            # Объединяем сертификаты
            fullchain = cert_content + '\n' + ca_content
            
            with open('./fullchain.pem', 'w') as f:
                f.write(fullchain)
            
            print("Создан полный сертификат fullchain.pem")
            return './fullchain.pem'
        except Exception as e:
            print(f"ОШИБКА создания полного сертификата: {e}")
            return './certificate.crt'
    
    return './certificate.crt'

def find_regru_certificates():
    """Поиск сертификатов от reg.ru"""
    
    # Если есть файлы от reg.ru, создаем полный сертификат
    if os.path.exists('./certificate.crt') and os.path.exists('./certificate.key'):
        cert_path = create_fullchain_certificate()
        key_path = './certificate.key'
        return cert_path, key_path
    
    # Альтернативные пути
    possible_paths = [
        # Стандартные пути для reg.ru
        ('/etc/ssl/certs/tyutelkavtyutelku.ru.crt', '/etc/ssl/private/tyutelkavtyutelku.ru.key'),
        ('/etc/letsencrypt/live/tyutelkavtyutelku.ru/fullchain.pem', '/etc/letsencrypt/live/tyutelkavtyutelku.ru/privkey.pem'),
        # Локальные пути
        ('./ssl/tyutelkavtyutelku.ru.crt', './ssl/tyutelkavtyutelku.ru.key'),
        ('./certificates/tyutelkavtyutelku.ru.crt', './certificates/tyutelkavtyutelku.ru.key'),
        # Альтернативные имена
        ('./tyutelkavtyutelku.ru.crt', './tyutelkavtyutelku.ru.key'),
        ('./cert.pem', './key.pem')
    ]
    
    for cert_path, key_path in possible_paths:
        if os.path.exists(cert_path) and os.path.exists(key_path):
            return cert_path, key_path
    
    return None, None

def setup_signal_handlers():
    """Настройка обработчиков сигналов для graceful shutdown"""
    def signal_handler(signum, frame):
        logger.info(f"Получен сигнал {signum}, завершаю работу...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

def setup_ngrok():
    if not NGROK_AVAILABLE:
        print("ОШИБКА: ngrok не доступен. Установите командой: pip install pyngrok")
        return None
        
    try:
        public_url = ngrok.connect(443)
        print(f"\nПУБЛИЧНЫЙ АДРЕС АДМИНКИ:")
        print(f"   {public_url}")
        print(f"\nОткройте этот адрес на любом устройстве с интернетом!")
        print(f"Логин: {CASHIER_LOGIN}")
        print(f"Пароль: {CASHIER_PASSWORD}")
        print(f"\nВАЖНО: Этот адрес работает только пока запущена программа!")
        print(f"Для остановки нажмите Ctrl+C")
        
        atexit.register(ngrok.disconnect, public_url)
        
        return public_url
        
    except Exception as e:
        logger.error(f"Ошибка настройки ngrok: {e}")
        print(f"ОШИБКА: Не удалось создать публичный доступ: {e}")
        return None

# Главная страница - пользовательский интерфейс
@app.route('/')
def index():
    # Если пользователь зашел на главную, перенаправляем в зависимости от типа
    if session.get('user_logged_in'):
        # Пользователь залогинен - перенаправляем в его профиль
        return redirect(url_for('user.user_profile'))
    elif session.get('logged_in'):
        # Кассир залогинен - перенаправляем на кассовый интерфейс
        return redirect(url_for('cashier.scanner'))
    else:
        # По умолчанию перенаправляем на пользовательский вход
        return redirect(url_for('user.user_index'))

# Кассовые маршруты (Blueprint)
@cashier_bp.route('/')
def cashier_index():
    # Если кассир залогинен, перенаправляем на сканер
    if session.get('logged_in'):
        return redirect(url_for('cashier.scanner'))
    else:
        return redirect(url_for('cashier.login'))

@cashier_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == CASHIER_LOGIN and password == CASHIER_PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('cashier.scanner'))
        else:
            flash('Неверные учетные данные')
    
    return render_template('login.html')

@cashier_bp.route('/scanner')
def scanner():
    if not session.get('logged_in'):
        return redirect(url_for('cashier.login'))
    return render_template('scanner.html')

@cashier_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('cashier.login'))

@cashier_bp.route('/users')
def users_database():
    if not session.get('logged_in'):
        return redirect(url_for('cashier.login'))
    
    db = None
    try:
        db = get_db()
        page = request.args.get('page', 1, type=int)
        if page < 1:
            page = 1
        per_page = 20
        search_query = request.args.get('search', '').strip()
        
        # Логируем запрос поиска для отладки
        if search_query:
            logger.info(f"Поиск пользователей: запрос '{search_query}'")
        
        # Безопасная сортировка с обработкой None значений
        from sqlalchemy import desc, nullslast
        try:
            all_users = db.query(User).order_by(nullslast(desc(User.registration_date))).all()
        except Exception:
            # Fallback если nullslast не поддерживается
            all_users = db.query(User).order_by(desc(User.registration_date)).all()
        
        # Unicode‑дружественный поиск на стороне Python (работает с кириллицей)
        if search_query:
            sq = search_query.strip().lower()
            sq_clean = ''.join(filter(str.isdigit, sq))  # Только цифры для поиска по ID/телефону
            
            def matches(u):
                try:
                    # Поиск по текстовым полям
                    first_name = (u.first_name or '').lower()
                    last_name = (u.last_name or '').lower()
                    username = (u.username or '').lower()
                    phone = (u.phone or '').lower()
                    referral_code = (u.referral_code or '').lower()
                    
                    # Поиск по числовым полям
                    tgid = str(u.telegram_id or '')
                    user_id_str = str(u.id)
                    
                    # Поиск по текстовым полям (имя, фамилия, username, реферальный код)
                    text_match = (sq in first_name) or (sq in last_name) or (sq in username) or (sq in referral_code)
                    
                    # Поиск по телефону (может быть как текст, так и цифры)
                    phone_match = sq in phone or (sq_clean and sq_clean in phone.replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', ''))
                    
                    # Поиск по числовым полям (ID пользователя, Telegram ID)
                    numeric_match = False
                    if sq_clean:
                        numeric_match = (sq_clean in user_id_str) or (sq_clean in tgid)
                    
                    return text_match or phone_match or numeric_match
                except Exception as e:
                    logger.error(f"Ошибка при проверке пользователя {u.id}: {e}")
                    return False
            
            filtered = [u for u in all_users if matches(u)]
        else:
            filtered = all_users
        
        total_users = len(filtered)
        start = (page - 1) * per_page
        end = start + per_page
        users = filtered[start:end]
        
        total_pages = (total_users + per_page - 1) // per_page if total_users > 0 else 1
        has_prev = page > 1
        has_next = page < total_pages
        
        return render_template('users_database.html', 
                             users=users, 
                             page=page, 
                             total_pages=total_pages,
                             has_prev=has_prev,
                             has_next=has_next,
                             search_query=search_query,
                             total_users=total_users)
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке базы пользователей: {e}", exc_info=True)
        flash(f'Ошибка при загрузке базы данных пользователей: {str(e)}', 'error')
        return redirect(url_for('cashier.scanner'))
    finally:
        if db:
            try:
                db.close()
            except Exception:
                pass

@cashier_bp.route('/users/<int:user_id>')
def user_details(user_id):
    if not session.get('logged_in'):
        return redirect(url_for('cashier.login'))
    
    try:
        db = get_db()
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            db.close()
            flash('Пользователь не найден', 'error')
            return redirect(url_for('cashier.users_database'))
        
        purchases = db.query(Purchase).filter(Purchase.user_id == user_id).order_by(Purchase.purchase_date.desc()).limit(10).all()
        
        loyalty_service = LoyaltyService(db)
        points_history = loyalty_service.get_points_history(user_id, limit=10)
        
        referrals = db.query(User).filter(User.referred_by == user_id).all()
        
        db.close()
        
        return render_template('user_details.html', 
                             user=user, 
                             purchases=purchases,
                             points_history=points_history,
                             referrals=referrals)
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке данных пользователя: {e}", exc_info=True)
        flash(f'Ошибка при загрузке данных пользователя: {str(e)}', 'error')
        try:
            if 'db' in locals():
                db.close()
        except:
            pass
        return redirect(url_for('cashier.users_database'))

@cashier_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
def edit_user(user_id):
    if not session.get('logged_in'):
        return redirect(url_for('cashier.login'))
    
    try:
        db = get_db()
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            db.close()
            flash('Пользователь не найден', 'error')
            return redirect(url_for('cashier.users_database'))
        
        if request.method == 'POST':
            user.first_name = request.form.get('first_name', '').strip()
            user.last_name = request.form.get('last_name', '').strip()
            user.username = request.form.get('username', '').strip()
            user.phone = request.form.get('phone', '').strip()
            
            new_points = request.form.get('points', type=int)
            if new_points is not None and new_points != user.points:
                points_difference = new_points - user.points
                user.points = new_points
                
                points_history = PointsHistory(
                    user_id=user_id,
                    points_change=points_difference,
                    transaction_type='manual_adjustment',
                    description=f"Ручная корректировка кассиром ({session.get('username')})"
                )
                db.add(points_history)
            
            is_active = request.form.get('is_active') == 'on'
            user.is_active = is_active
            
            db.commit()
            db.close()
            flash('Данные пользователя успешно обновлены', 'success')
            return redirect(url_for('cashier.user_details', user_id=user_id))
        
        db.close()
        return render_template('edit_user.html', user=user)
        
    except Exception as e:
        logger.error(f"Ошибка при редактировании пользователя: {e}")
        flash('Ошибка при редактировании пользователя', 'error')
        return redirect(url_for('users_database'))

@cashier_bp.route('/api/user/<int:user_id>/reset_password', methods=['POST'])
def reset_user_password(user_id):
    """Сброс пароля пользователя - генерирует новый пароль в открытом виде"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Не авторизован'}), 401
    
    try:
        import random
        import string
        
        def generate_password():
            """Генерация пароля для веб-входа"""
            # Генерируем пароль: 8 символов (буквы + цифры)
            return ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        
        db = get_db()
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            db.close()
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        # Генерируем новый пароль
        new_password = generate_password()
        
        # Сохраняем пароль в открытом виде
        user.web_password_hash = new_password
        db.commit()
        
        logger.info(f"Пароль пользователя {user_id} сброшен кассиром {session.get('username')}")
        
        db.close()
        
        return jsonify({
            'success': True,
            'new_password': new_password,
            'message': 'Пароль успешно сброшен'
        })
        
    except Exception as e:
        logger.error(f"Ошибка при сбросе пароля пользователя {user_id}: {e}", exc_info=True)
        try:
            if 'db' in locals():
                db.close()
        except:
            pass
        return jsonify({'error': f'Ошибка при сбросе пароля: {str(e)}'}), 500

@cashier_bp.route('/api/user/<int:user_id>/toggle_status', methods=['POST'])
def toggle_user_status(user_id):
    if not session.get('logged_in'):
        return jsonify({'error': 'Не авторизован'}), 401
    
    try:
        db = get_db()
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            db.close()
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        user.is_active = not user.is_active
        db.commit()
        
        status_text = 'активирован' if user.is_active else 'деактивирован'
        logger.info(f"Пользователь {user_id} {status_text} кассиром {session.get('username')}")
        
        db.close()
        
        return jsonify({
            'success': True,
            'is_active': user.is_active,
            'message': f'Пользователь {status_text}'
        })
        
    except Exception as e:
        logger.error(f"Ошибка при изменении статуса пользователя: {e}")
        return jsonify({'error': 'Ошибка сервера'}), 500

@cashier_bp.route('/referral-top')
def referral_top():
    """Страница с топом рефералов"""
    if not session.get('logged_in'):
        return redirect(url_for('cashier.login'))
    
    db = None
    try:
        db = get_db()
        loyalty_service = LoyaltyService(db)
        
        # Получаем топ 10 рефералов
        top_referrals = loyalty_service.get_referral_top(limit=10)
        
        # Получаем позицию пользователя, если указан user_id в параметрах
        user_position = None
        user_id_param = request.args.get('user_id', type=int)
        if user_id_param:
            user_position = loyalty_service.get_user_referral_position(user_id_param)
        
        db.close()
        
        return render_template('referral_top.html', 
                             top_referrals=top_referrals,
                             user_position=user_position)
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке топа рефералов: {e}", exc_info=True)
        flash(f'Ошибка при загрузке топа рефералов: {str(e)}', 'error')
        try:
            if db:
                db.close()
        except:
            pass
        return redirect(url_for('cashier.scanner'))


@cashier_bp.route('/giveaway')
def giveaway_page():
    """Страница розыгрыша (кассир)"""
    if not session.get('logged_in'):
        return redirect(url_for('cashier.login'))

    db = None
    try:
        db = get_db()
        loyalty_service = LoyaltyService(db)

        giveaway = loyalty_service.get_active_giveaway()
        top = []
        if giveaway:
            top = loyalty_service.get_giveaway_top(giveaway.id, limit=10)

        return render_template('giveaway.html', giveaway=giveaway, top=top)
    except Exception as e:
        logger.error(f"Ошибка при загрузке розыгрыша: {e}", exc_info=True)
        flash(f"Ошибка при загрузке розыгрыша: {str(e)}", "error")
        return redirect(url_for('cashier.scanner'))
    finally:
        if db:
            try:
                db.close()
            except Exception:
                pass


@cashier_bp.route('/giveaway/create', methods=['POST'])
def giveaway_create():
    if not session.get('logged_in'):
        return redirect(url_for('cashier.login'))

    title = (request.form.get('title') or '').strip() or 'Розыгрыш'
    description = (request.form.get('description') or '').strip()
    days = request.form.get('days', type=int) or 7

    db = None
    try:
        db = get_db()
        loyalty_service = LoyaltyService(db)
        giveaway = loyalty_service.create_giveaway(title=title, days=days, description=description)
        flash(f"✅ Розыгрыш создан: {giveaway.title} (на {days} дн.)", "success")
    except Exception as e:
        logger.error(f"Ошибка создания розыгрыша: {e}", exc_info=True)
        flash(f"Ошибка создания розыгрыша: {str(e)}", "error")
    finally:
        if db:
            try:
                db.close()
            except Exception:
                pass

    return redirect(url_for('cashier.giveaway_page'))


@cashier_bp.route('/giveaway/stop', methods=['POST'])
def giveaway_stop():
    if not session.get('logged_in'):
        return redirect(url_for('cashier.login'))

    giveaway_id = request.form.get('giveaway_id', type=int)
    if not giveaway_id:
        flash("Не указан giveaway_id", "error")
        return redirect(url_for('cashier.giveaway_page'))

    db = None
    try:
        from database import User, Giveaway
        db = get_db()
        loyalty_service = LoyaltyService(db)
        
        # Завершаем розыгрыш
        ok = loyalty_service.stop_giveaway(giveaway_id)
        if not ok:
            flash("Розыгрыш не найден", "warning")
            return redirect(url_for('cashier.giveaway_page'))
        
        # Получаем информацию о розыгрыше
        giveaway = db.query(Giveaway).filter(Giveaway.id == giveaway_id).first()
        if not giveaway:
            flash("Розыгрыш не найден", "warning")
            return redirect(url_for('cashier.giveaway_page'))
        
        # Определяем победителя (первый в топе)
        giveaway_top = loyalty_service.get_giveaway_top(giveaway_id, limit=1)
        winner_info = "Победителей нет"
        
        if giveaway_top and len(giveaway_top) > 0 and giveaway_top[0]["referrals_count"] > 0:
            winner_data = giveaway_top[0]
            winner = db.query(User).filter(User.id == winner_data["user_id"]).first()
            if winner:
                winner_name = f"{winner.first_name or ''} {winner.last_name or ''}".strip() or f"Участник #{winner.id}"
                winner_info = f"🏆 Победитель: {winner_name}\n📊 Приглашено друзей: {winner_data['referrals_count']}"
        
        # Отправляем уведомление всем админам
        admin_message = f"""
🎉 Розыгрыш завершён!

📋 Название: {giveaway.title}
{winner_info}

📢 Нажмите кнопку ниже, чтобы разослать сообщение всем участникам о завершении розыгрыша.
        """.strip()
        
        # Отправляем всем админам
        for admin_id in config.ADMIN_IDS:
            try:
                send_message_with_inline_button_sync(
                    telegram_id=admin_id,
                    message=admin_message,
                    button_text="📢 Разослать участникам",
                    callback_data=f"admin_giveaway_notify_participants_{giveaway_id}"
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
        
        flash("✅ Розыгрыш завершён. Уведомления с информацией о победителе отправлены всем администраторам.", "success")
    except Exception as e:
        logger.error(f"Ошибка завершения розыгрыша: {e}", exc_info=True)
        flash(f"Ошибка завершения розыгрыша: {str(e)}", "error")
    finally:
        if db:
            try:
                db.close()
            except Exception:
                pass

    return redirect(url_for('cashier.giveaway_page'))


@cashier_bp.route('/giveaway/broadcast', methods=['POST'])
def giveaway_broadcast():
    if not session.get('logged_in'):
        return redirect(url_for('cashier.login'))

    giveaway_id = request.form.get('giveaway_id', type=int)
    text = (request.form.get('message') or '').strip()
    if not giveaway_id:
        flash("Не указан giveaway_id", "error")
        return redirect(url_for('cashier.giveaway_page'))

    db = None
    try:
        db = get_db()
        loyalty_service = LoyaltyService(db)
        giveaway = loyalty_service.get_active_giveaway()
        if not giveaway or giveaway.id != giveaway_id:
            flash("Розыгрыш не найден или не активен", "warning")
            return redirect(url_for('cashier.giveaway_page'))

        # Если текст не указан, формируем автоматически из данных розыгрыша
        if not text:
            text = f"🎉 Розыгрыш: {giveaway.title}\n\n"
            if giveaway.description:
                text += f"{giveaway.description}\n\n"
            if giveaway.end_date:
                text += f"⏰ Срок проведения: до {giveaway.end_date.strftime('%d.%m.%Y %H:%M')}\n\n"
            text += "🏆 Чтобы принять участие и побороться за приз, нажмите кнопку «✅ Участвую!» ниже.\n"
            text += "Победитель будет определен по наибольшему количеству приглашенных друзей за период розыгрыша."

        # Тем, кто уже участвует — кнопка «Вы участвуете», остальным — «Участвую»
        from database import GiveawayParticipant
        participant_ids = {
            int(row[0])
            for row in db.query(GiveawayParticipant.user_id).filter(GiveawayParticipant.giveaway_id == giveaway.id).all()
        }

        users = db.query(User).filter(User.is_active == True, User.is_registered == True).all()
        sent = 0
        for u in users:
            try:
                if u.id in participant_ids:
                    button_text = "✅ Вы участвуете"
                    callback_data = f"giveaway_status_{giveaway.id}"
                else:
                    button_text = "✅ Участвую"
                    callback_data = f"giveaway_join_{giveaway.id}"

                ok = send_message_with_inline_button_sync(
                    telegram_id=u.telegram_id,
                    message=text,
                    button_text=button_text,
                    callback_data=callback_data
                )
                if ok:
                    sent += 1
            except Exception:
                continue

        flash(f"📢 Рассылка отправлена: {sent} пользователям", "success")
    except Exception as e:
        logger.error(f"Ошибка рассылки розыгрыша: {e}", exc_info=True)
        flash(f"Ошибка рассылки: {str(e)}", "error")
    finally:
        if db:
            try:
                db.close()
            except Exception:
                pass

    return redirect(url_for('cashier.giveaway_page'))

@cashier_bp.route('/gift_points', methods=['GET', 'POST'])
def gift_points():
    """Раздача баллов всем пользователям на праздник"""
    if not session.get('logged_in'):
        return redirect(url_for('cashier.login'))
    
    if request.method == 'POST':
        # ... (код обработки POST остается прежним)
        try:
            amount = request.form.get('amount', type=int)
            days = request.form.get('days', type=int, default=0)
            description = request.form.get('description', '').strip()
            
            if not amount or amount <= 0:
                flash('Укажите корректную сумму баллов', 'error')
                return redirect(url_for('cashier.gift_points'))
            
            if not description:
                flash('Укажите повод для подарка', 'error')
                return redirect(url_for('cashier.gift_points'))
            
            db = get_db()
            loyalty_service = LoyaltyService(db)
            
            # Вычисляем дату сгорания
            expiry_date = None
            expiry_text = ""
            if days > 0:
                expiry_date = datetime.now() + timedelta(days=days)
                expiry_text = f"\n⏰ Баллы действительны до {expiry_date.strftime('%d.%m.%Y %H:%M')}"
            
            # Получаем всех активных зарегистрированных пользователей
            users = db.query(User).filter(User.is_active == True, User.is_registered == True).all()
            
            success_count = 0
            for user in users:
                try:
                    # Начисляем баллы
                    loyalty_service.add_bonus_points(
                        user_id=user.id,
                        points=amount,
                        description=description,
                        expiry_date=expiry_date
                    )
                    
                    # Отправляем уведомление
                    msg = f"🎁 Вам подарок!\n\n{description}\n💰 Вам начислено {amount} бонусных баллов!\n🏆 Ваш новый баланс: {user.points} баллов{expiry_text}\n\nСпасибо, что вы с нами! 🎉"
                    
                    try:
                        url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
                        requests.post(url, json={
                            "chat_id": user.telegram_id,
                            "text": msg.strip()
                        }, timeout=5)
                    except:
                        pass
                        
                    success_count += 1
                except Exception as e:
                    logger.error(f"Ошибка при подарке пользователю {user.id}: {e}")
            
            db.commit()
            db.close()
            flash(f'✅ Успешно начислено {amount} баллов {success_count} пользователям!', 'success')
            return redirect(url_for('cashier.gift_points'))
            
        except Exception as e:
            logger.error(f"Ошибка в процессе дарения баллов через веб: {e}", exc_info=True)
            flash(f'Ошибка при начислении баллов: {str(e)}', 'error')
            return redirect(url_for('cashier.gift_points'))
            
    # GET запрос: собираем статистику по кампаниям
    db = get_db()
    
    # Группируем по описанию и дате (с точностью до минуты, чтобы объединить массовое начисление)
    # В SQLite для этого используем strftime
    campaigns_query = db.query(
        PointsHistory.description,
        func.min(PointsHistory.created_date).label('start_date'),
        func.max(PointsHistory.expiry_date).label('expiry_date'),
        func.sum(PointsHistory.points_change).label('total_gifted'),
        func.count(PointsHistory.id).label('user_count')
    ).filter(
        PointsHistory.transaction_type == 'bonus',
        PointsHistory.expiry_date != None
    ).group_by(
        PointsHistory.description,
        func.strftime('%Y-%m-%d %H:%M', PointsHistory.created_date)
    ).order_by(func.min(PointsHistory.created_date).desc()).all()
    
    campaign_stats = []
    now = datetime.now()
    
    for camp in campaigns_query:
        # Получаем все записи о начислениях для этой конкретной кампании (группа по описанию и времени)
        # Нам нужно найти всех пользователей, кто получил этот подарок
        bonuses = db.query(PointsHistory).filter(
            PointsHistory.description == camp.description,
            PointsHistory.transaction_type == 'bonus',
            PointsHistory.created_date >= camp.start_date - timedelta(seconds=30),
            PointsHistory.created_date <= camp.start_date + timedelta(seconds=30)
        ).all()
        
        total_spent_from_gift = 0
        total_expired_from_gift = 0
        
        for bonus in bonuses:
            # 1. Сколько сгорело конкретно по этому начислению
            expired = db.query(func.sum(PointsHistory.points_change)).filter(
                PointsHistory.user_id == bonus.user_id,
                PointsHistory.transaction_type == 'expiry',
                PointsHistory.description.like(f"%{bonus.description}%"),
                PointsHistory.created_date > bonus.created_date
            ).scalar() or 0
            expired_abs = abs(expired)
            total_expired_from_gift += expired_abs
            
            # 2. Сколько пользователь потратил баллов ВООБЩЕ после этого подарка
            spent_after = db.query(func.sum(PointsHistory.points_change)).filter(
                PointsHistory.user_id == bonus.user_id,
                PointsHistory.transaction_type == 'redemption',
                PointsHistory.created_date > bonus.created_date
            ).scalar() or 0
            spent_abs = abs(spent_after)
            
            # Считаем, сколько из этого подарка было потрачено. 
            # Логика: подарок тратится первым (или одним из первых).
            # Потрачено из подарка = min(Сумма начисления - Сгорело, Всего потрачено после начисления)
            usable_bonus = bonus.points_change - expired_abs
            actually_spent = min(usable_bonus, spent_abs)
            total_spent_from_gift += actually_spent
            
        # "В процессе" (на руках или ждет сгорания) = Подарено - Потрачено - Сгорело
        held_now = max(0, camp.total_gifted - total_spent_from_gift - total_expired_from_gift)
        
        campaign_stats.append({
            'description': camp.description,
            'start_date': camp.start_date,
            'expiry_date': camp.expiry_date,
            'total_gifted': camp.total_gifted,
            'user_count': camp.user_count,
            'spent_sum': total_spent_from_gift,
            'expired_sum': total_expired_from_gift,
            'held_now': held_now,
            'is_active': camp.expiry_date > now if camp.expiry_date else True
        })
    
    db.close()
    return render_template('gift_points.html', campaigns=campaign_stats)

@cashier_bp.route('/history')
def purchase_history():
    if not session.get('logged_in'):
        return redirect(url_for('cashier.login'))
    
    try:
        db = get_db()
        
        page = request.args.get('page', 1, type=int)
        per_page = 50
        offset = (page - 1) * per_page
        
        total_purchases_count = db.query(Purchase).count()
        total_pages = (total_purchases_count + per_page - 1) // per_page
        
        from sqlalchemy.orm import joinedload
        recent_purchases = db.query(Purchase).options(
            joinedload(Purchase.user)
        ).order_by(Purchase.purchase_date.desc()).offset(offset).limit(per_page).all()
        
        total_purchases = db.query(Purchase).count()
        returned_purchases = db.query(Purchase).filter(Purchase.is_returned == True).count()
        
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today.replace(hour=23, minute=59, second=59)
        
        today_purchases = db.query(Purchase).filter(
            Purchase.purchase_date >= today,
            Purchase.purchase_date <= tomorrow
        ).all()
        
        today_stats = {
            'total_count': len(today_purchases),
            'total_amount': sum(p.amount for p in today_purchases if not p.is_returned),
            'returned_count': len([p for p in today_purchases if p.is_returned]),
            'returned_amount': sum(p.amount for p in today_purchases if p.is_returned),
            'active_count': len([p for p in today_purchases if not p.is_returned]),
            'points_earned': sum(p.points_earned for p in today_purchases if not p.is_returned),
            'points_returned': sum(p.points_earned for p in today_purchases if p.is_returned)
        }
        
        general_stats = {
            'total_purchases': total_purchases,
            'returned_purchases': returned_purchases,
            'return_rate': round((returned_purchases / total_purchases * 100) if total_purchases > 0 else 0, 1)
        }
        
        purchases_data = []
        for purchase in recent_purchases:
            purchases_data.append({
                'id': purchase.id,
                'amount': purchase.amount,
                'points_earned': purchase.points_earned,
                'points_used': purchase.points_used or 0,
                'purchase_date': purchase.purchase_date,
                'description': purchase.description,
                'is_returned': purchase.is_returned,
                'return_date': purchase.return_date,
                'user': {
                    'id': purchase.user.id,
                    'first_name': purchase.user.first_name,
                    'last_name': purchase.user.last_name,
                    'username': purchase.user.username,
                    'telegram_id': purchase.user.telegram_id,
                    'points': purchase.user.points
                }
            })
        
        db.close()
        
        pagination = {
            'page': page,
            'per_page': per_page,
            'total': total_purchases_count,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'prev_num': page - 1 if page > 1 else None,
            'next_num': page + 1 if page < total_pages else None
        }
        
        return render_template('history.html', 
                             purchases=purchases_data, 
                             today=today,
                             today_stats=today_stats,
                             general_stats=general_stats,
                             pagination=pagination)
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке истории: {e}")
        flash('Ошибка при загрузке истории покупок', 'error')
        return redirect(url_for('cashier.scanner'))

@cashier_bp.route('/api/user_search', methods=['GET'])
def user_search():
    if not session.get('logged_in'):
        return jsonify({'error': 'Не авторизован'}), 401

    db = None
    try:
        query = request.args.get('q', '').strip()
        if len(query) < 2:
            return jsonify({'users': []})

        db = get_db()
        query_lower = query.lower()
        query_clean = ''.join(filter(str.isdigit, query))  # Только цифры для поиска по ID/телефону

        # Получаем всех пользователей (включая неактивных для поиска)
        all_users = db.query(User).all()

        filtered_users = []
        for user in all_users:
            first_name = (user.first_name or '').lower()
            last_name = (user.last_name or '').lower()
            username = (user.username or '').lower()
            phone = (user.phone or '').lower()
            telegram_id = str(user.telegram_id or '')
            user_id = str(user.id)
            referral_code = (user.referral_code or '').lower()

            # Поиск по имени, фамилии, username
            if (query_lower in first_name or
                query_lower in last_name or
                query_lower in username or
                query_lower in referral_code):
                filtered_users.append(user)
            # Поиск по ID, телефону, telegram_id (только если запрос содержит цифры)
            elif query_clean and (query_clean in user_id or
                                  query_clean in phone or
                                  query_clean in telegram_id):
                filtered_users.append(user)

        # Сортируем: сначала активные, потом неактивные
        filtered_users.sort(key=lambda u: (not u.is_active, u.id))
        filtered_users = filtered_users[:10]

        users_data = []
        for user in filtered_users:
            users_data.append({
                'user_id': user.id,
                'telegram_id': user.telegram_id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'phone': user.phone,
                'points': user.points or 0,
                'total_spent': user.total_spent or 0.0,
                'is_active': user.is_active,
                'registration_date': user.registration_date.strftime('%d.%m.%Y') if user.registration_date else 'Не указана',
                'display_name': f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or f"ID: {user.id}"
            })

        logger.info(f"Поиск пользователей: запрос '{query}', найдено {len(users_data)} результатов")
        return jsonify({'users': users_data})

    except Exception as e:
        logger.error(f"Ошибка при поиске пользователей: {e}", exc_info=True)
        return jsonify({'error': f'Ошибка сервера: {str(e)}'}), 500
    finally:
        if db:
            try:
                db.close()
            except:
                pass

@cashier_bp.route('/api/purchase/<int:purchase_id>/return', methods=['POST'])
def return_purchase(purchase_id):
    if not session.get('logged_in'):
        return jsonify({'error': 'Не авторизован'}), 401
    
    try:
        db = get_db()
        loyalty_service = LoyaltyService(db)
        
        success, message = loyalty_service.return_purchase(purchase_id)
        
        db.close()
        
        if success:
            logger.info(f"Возврат покупки #{purchase_id} выполнен кассиром {session.get('username')}")
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'error': message}), 400
            
    except Exception as e:
        logger.error(f"Ошибка при возврате покупки: {e}")
        return jsonify({'error': 'Ошибка при обработке возврата'}), 500

@cashier_bp.route('/api/scan', methods=['POST'])
def scan_code():
    if not session.get('logged_in'):
        return jsonify({'error': 'Не авторизован'}), 401
    
    try:
        data = request.get_json()
        code = data.get('code')
        
        if not code:
            return jsonify({'error': 'Код не предоставлен'}), 400
        
        # Здесь должна быть логика обработки кода
        # Пока возвращаем заглушку
        return jsonify({
            'success': True,
            'message': f'Код {code} обработан',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Ошибка при обработке кода: {e}")
        return jsonify({'error': 'Ошибка при обработке кода'}), 500

@cashier_bp.route('/api/scan_qr', methods=['POST'])
def scan_qr():
    if not session.get('logged_in'):
        return jsonify({'error': 'Не авторизован'}), 401
    
    try:
        data = request.get_json()
        qr_data = data.get('qr_data', '').strip()
        
        if not qr_data:
            return jsonify({'error': 'QR-код пустой'}), 400
        
        match = re.match(r'^(\d+)_(\d+)$', qr_data)
        if not match:
            return jsonify({'error': 'Неверный формат QR-кода'}), 400
        
        user_id = int(match.group(1))
        telegram_id = int(match.group(2))
        
        db = get_db()
        user_service = UserService(db)
        
        user = db.query(User).filter(User.id == user_id, User.telegram_id == telegram_id).first()
        if not user:
            db.close()
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        if not user.is_active:
            db.close()
            return jsonify({'error': 'Аккаунт пользователя деактивирован'}), 400
        
        user_info = {
            'user_id': user.id,
            'telegram_id': user.telegram_id,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'username': user.username,
            'points': user.points,
            'total_spent': user.total_spent,
            'registration_date': user.registration_date.strftime('%d.%m.%Y') if user.registration_date else ''
        }
        
        db.close()
        return jsonify({'success': True, 'user': user_info})
        
    except Exception as e:
        logger.error(f"Ошибка при сканировании QR: {e}")
        return jsonify({'error': 'Ошибка сервера'}), 500

@cashier_bp.route('/api/add_purchase', methods=['POST'])
def add_purchase():
    if not session.get('logged_in'):
        return jsonify({'error': 'Не авторизован'}), 401
    
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        amount = data.get('amount')
        description = data.get('description', '')
        points_used = data.get('points_used', 0)
        
        if not user_id or amount is None:
            return jsonify({'error': 'Не указан ID пользователя или сумма'}), 400
        
        try:
            amount = float(amount)
            points_used = int(points_used) if points_used else 0
            if amount <= 0:
                return jsonify({'error': 'Сумма должна быть положительной'}), 400
            if points_used < 0:
                return jsonify({'error': 'Количество баллов не может быть отрицательным'}), 400
        except ValueError:
            return jsonify({'error': 'Некорректные данные'}), 400
        
        db = get_db()
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            db.close()
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        if points_used > amount:
            db.close()
            return jsonify({'error': 'Нельзя использовать больше баллов чем сумма покупки'}), 400
        
        loyalty_service = LoyaltyService(db)
        result = loyalty_service.add_purchase(user_id, amount, description, points_used)
        if not result:
            db.close()
            if points_used > 0:
                return jsonify({'error': f'Недостаточно баллов. Доступно: {user.points}'}), 400
            else:
                return jsonify({'error': 'Ошибка при добавлении покупки'}), 500
        
        purchase, points_earned = result
        user = db.query(User).filter(User.id == user_id).first()
        
        response_data = {
            'success': True,
            'purchase_id': purchase.id,
            'points_earned': points_earned,
            'total_points': user.points,
            'amount': amount,
            'description': description,
            'timestamp': purchase.purchase_date.strftime('%d.%m.%Y %H:%M')
        }
        if points_used > 0:
            response_data['points_used'] = points_used
            response_data['remaining_points'] = user.points
            response_data['final_amount'] = amount - points_used
        
        telegram_id = user.telegram_id
        total_points = user.points
        db.close()
        
        def send_notification():
            try:
                notification_description = description
                if points_used > 0:
                    notification_description += f" (использовано {points_used} баллов)"
                send_purchase_notification_sync(
                    telegram_id=telegram_id,
                    purchase_amount=amount,
                    points_earned=points_earned,
                    total_points=total_points,
                    description=notification_description
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления: {e}")
        
        notify_thread = threading.Thread(target=send_notification, daemon=True)
        notify_thread.start()
        
        logger.info(f"Добавлена покупка: пользователь {user_id}, сумма {amount}, баллы {points_earned}")
        return jsonify(response_data)
    
    except Exception as e:
        logger.error(f"Ошибка при добавлении покупки: {e}")
        return jsonify({'error': 'Ошибка сервера'}), 500

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 
                             'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/service-worker.js')
def service_worker():
    """Отдача service worker для PWA"""
    return send_from_directory(os.path.join(app.root_path, 'static'), 
                              'service-worker.js', mimetype='application/javascript')

@app.route('/robots.txt')
def robots_txt():
    return '''User-agent: *
Disallow: /
''', 200, {'Content-Type': 'text/plain'}

@app.route('/security.txt')
@app.route('/.well-known/security.txt')
def security_txt():
    return '''Contact: admin@example.com
Expires: 2025-12-31T23:59:59.000Z
Preferred-Languages: ru, en
''', 200, {'Content-Type': 'text/plain'}

@app.route('/.env')
def env_file():
    return '', 404

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat(), 'version': 'stable'})

# ---- РЕЗЕРВНОЕ КОПИРОВАНИЕ БД И ОТПРАВКА В TELEGRAM ----
def _get_sqlite_file_path() -> str:
    try:
        # Избегаем жёсткой зависимости: импорт локально
        from database import get_database_url
        db_url = get_database_url()
        if db_url.startswith('sqlite:///'):
            return db_url.replace('sqlite:///', '', 1)
    except Exception:
        pass
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'loyalty_bot.db')

def create_db_backup() -> str:
    src_path = _get_sqlite_file_path()
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"Файл БД не найден: {src_path}")
    backups_dir = os.path.join(os.path.dirname(src_path), 'backups')
    os.makedirs(backups_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dst_path = os.path.join(backups_dir, f'loyalty_bot_{timestamp}.db')
    shutil.copy2(src_path, dst_path)
    return dst_path

@cashier_bp.route('/admin/backup_db')
def admin_backup_db():
    if not session.get('logged_in'):
        return redirect(url_for('cashier.login'))
    try:
        backup_path = create_db_backup()
        caption = f"Резервная копия БД на {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
        from config import BACKUP_CHAT_ID
        sent = send_document_sync(BACKUP_CHAT_ID, backup_path, caption)
        if sent:
            flash('Бэкап создан и отправлен в Telegram', 'success')
        else:
            flash('Бэкап создан, но отправка в Telegram не удалась', 'warning')
    except Exception as e:
        logger.error(f"Ошибка бэкапа БД: {e}")
        flash('Ошибка при создании бэкапа', 'error')
    return redirect(url_for('cashier.scanner'))

def schedule_daily_backup():
    try:
        from config import BACKUP_HOUR, BACKUP_MINUTE, BACKUP_CHAT_ID
        def worker():
            while True:
                now = datetime.now()
                run_time = now.replace(hour=BACKUP_HOUR, minute=BACKUP_MINUTE, second=0, microsecond=0)
                if run_time <= now:
                    run_time = run_time + timedelta(days=1)
                sleep_seconds = (run_time - now).total_seconds()
                try:
                    threading.Event().wait(timeout=sleep_seconds)
                except Exception:
                    pass
                try:
                    backup_path = create_db_backup()
                    caption = f"Ночной бэкап БД на {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
                    send_document_sync(BACKUP_CHAT_ID, backup_path, caption)
                except Exception as e:
                    logger.error(f"Плановый бэкап не удался: {e}")
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        logger.info("Ежедневный бэкап БД запланирован")
    except Exception as e:
        logger.error(f"Не удалось настроить планировщик бэкапа: {e}")

def schedule_points_expiry_check():
    """Запуск фоновой проверки сгорания баллов"""
    def worker():
        while True:
            try:
                db = get_db()
                loyalty_service = LoyaltyService(db)
                processed = loyalty_service.process_expired_points()
                if processed > 0:
                    logger.info(f"🔥 Автоматически списано просроченных начислений (Web Server): {processed}")
                db.close()
            except Exception as e:
                logger.error(f"Ошибка в веб-планировщике сгорания баллов: {e}")
            
            # Проверяем каждый час
            threading.Event().wait(timeout=3600)
            
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    logger.info("Фоновая задача сгорания баллов запущена на веб-сервере")

# Регистрация Blueprint для кассовых маршрутов (после определения всех маршрутов)
app.register_blueprint(cashier_bp)

if __name__ == '__main__':
    print("Запуск СТАБИЛЬНОЙ веб-админки для кассиров...")
    
    if not WAITRESS_AVAILABLE:
        print("ОШИБКА: Waitress не установлен!")
        print("УСТАНОВИТЕ: pip install waitress")
        exit(1)
    
    # Настройка обработчиков сигналов
    setup_signal_handlers()
    
    # Поиск сертификатов от reg.ru
    cert_path, key_path = find_regru_certificates()
    
    if not cert_path or not key_path:
        print("ОШИБКА: Сертификаты от reg.ru не найдены!")
        print("\nУбедитесь, что в папке проекта есть файлы:")
        print("   - certificate.crt (основной сертификат)")
        print("   - certificate.key (приватный ключ)")
        print("   - certificate_ca.crt (сертификат CA)")
        print("\nСкачайте их из панели управления reg.ru")
        print("\nАльтернативно используйте HTTP версию:")
        print("   - python cashier_admin.py (HTTP на порту 3000)")
        exit(1)
    
        print(f"СЕРТИФИКАТЫ НАЙДЕНЫ:")
        print(f"   Сертификат: {cert_path}")
        print(f"   Ключ: {key_path}")
    
    try:
        # Настройка ngrok для публичного доступа
        ngrok_url = setup_ngrok()
        # Запускаем планировщики
        schedule_daily_backup()
        schedule_points_expiry_check()
        
        print("Запуск с профессиональным WSGI-сервером Waitress")
        print(f"HTTPS адрес: https://tyutelkavtyutelku.ru")
        print(f"Локальный адрес: https://localhost:443")
        print(f"Логин: {CASHIER_LOGIN}")
        print(f"Пароль: {CASHIER_PASSWORD}")
        print("\nСЕРВЕР ЗАПУЩЕН с профессиональным WSGI-сервером!")
        print("Браузер не будет показывать предупреждения о безопасности")
        print("Доступ по адресу: https://tyutelkavtyutelku.ru")
        print("\nWaitress обеспечивает стабильную работу и автоматическое восстановление")
        
        # Запуск через Waitress
        serve(
            app,
            host='0.0.0.0',
            port=443,
            url_scheme='https',
            threads=4,  # Многопоточность
            connection_limit=1000,  # Лимит соединений
            cleanup_interval=30,  # Интервал очистки
            channel_timeout=120,  # Таймаут канала
            log_socket_errors=True,  # Логирование ошибок сокетов
            max_request_body_size=1073741824,  # 1GB макс размер запроса
            ident='Cashier Admin Server'  # Идентификация сервера
        )
        
    except FileNotFoundError as e:
        print(f"ОШИБКА загрузки сертификата: {e}")
        print("Проверьте, что файлы certificate.crt и certificate.key существуют")
    except PermissionError:
        print("ОШИБКА: Нет прав для использования порта 443")
        print("Запустите программу от имени администратора")
        print("Альтернативно используйте: python cashier_admin.py")
    except Exception as e:
        print(f"ОШИБКА запуска: {e}")
        print("Проверьте корректность сертификатов и настройки")
    except KeyboardInterrupt:
        print("\nСервер остановлен")
